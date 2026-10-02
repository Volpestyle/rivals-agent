"""Persistent supervised range sitting; model/capture stay loaded between scopes.

One initial BC control, then RL; --bc-every N optionally repeats the BC control.
Episode reward extraction/AWR happen in one background process. Completed bundles
are consumed only at a pad-free boundary. Use only after the lead's safety read
and takeover verification. Importing this module starts no worker or hardware.
"""
import argparse
import json
import math
import multiprocessing as mp
from pathlib import Path
import queue
import time

from rl.online.sitting import after_episode, plot


def arm_for(index, bc_every=0):
    return 'bc' if index == 0 or bc_every and index % bc_every == 0 else 'rl'


def update_worker(base_bundle, out, jobs, results, device, beta, kl, steps, aim_weight=0.):
    """Own model copies, a snapshot of completed episode files, and no pad API."""
    try:
        import os
        for name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
            os.environ[name] = '2'
        if __import__('sys').platform == 'win32':
            import ctypes
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x4000)  # BELOW_NORMAL_PRIORITY_CLASS
        import torch
        torch.set_num_threads(2)
        torch.set_num_interop_threads(2)
        import cv2
        cv2.setNumThreads(2)
        from policy.bc2.features import load_tower
        from policy.bc2.model import Config, Policy2
        from rl.online import data, update
        base_bundle, out = Path(base_bundle), Path(out)
        spec = json.loads((base_bundle/'bundle.json').read_text())
        files = spec['files']
        checkpoint = base_bundle/files['checkpoint']['path']
        if update._sha256(checkpoint) != files['checkpoint']['sha256']:
            raise ValueError('base checkpoint hash mismatch')
        payload = torch.load(checkpoint, map_location='cpu', weights_only=True)
        config = payload['config']
        if config.get('use_green') or config.get('hires'):
            raise ValueError('online updater does not support green/hires configs')
        base = Policy2(Config(**config))
        base.load_state_dict(payload['model'])
        base.eval()
        tower = load_tower(base_bundle/files['vision']['path'], base_bundle/files['vision_config']['path'], device)
        current, buffer = base, []
        live_names = {name for name, on in spec['live'].items() if on}
        while (job := jobs.get()) is not None:
            index, arm, directory, result = job
            reset = result.get('reset', {}).get('status')
            reset = None if reset == 'skipped' else reset
            policy_ran = result.get('policy_start_t') is not None
            ep = data.episode(directory, live_names, tower=tower, device=device) if policy_ran else None
            died = bool(ep and ep['events']['death'])
            go_on, reason = after_episode(result['result'], died, reset)
            row = {'episode': index, 'arm': arm, 'result': result['result'], 'reset': reset,
                   'bundle': result.get('policy_bundle'),
                   'reset_detail': result.get('reset'), 'settle': result.get('settle'),
                   'go_on': go_on, 'stop_reason': reason}
            if ep is not None:
                minutes = max(ep['seconds'], 1e-6)/60
                row.update(seconds=ep['seconds'], **ep['events'],
                           hits_per_min=ep['events']['hit']/minutes, kos_per_min=ep['events']['ko']/minutes,
                           return_sum=float(ep['reward'].sum()))
                if 'reward_aim' in ep:
                    row.update(aim_sum=float(ep['reward_aim'].sum()), aim_known=float(ep['aim_known'].mean()))
            results.put({'kind': 'episode', 'row': row})
            # Safety/human-contaminated episodes never enter an update.
            if go_on and arm == 'rl' and ep is not None:
                buffer.append(ep)
                current, summary = update.update(current, base, buffer, beta=beta, kl=kl,
                                                 steps=steps, device=device, seed=index, aim_weight=aim_weight)
                bundle = update.write_bundle(current, config, base_bundle, out/'bundles'/f'rl-{index:03d}',
                                             name=f'rl-{index:03d}')
                results.put({'kind': 'update', 'episode': index, 'bundle': str(bundle), 'summary': summary})
            results.put({'kind': 'done', 'episode': index})
    except BaseException as exc:
        results.put({'kind': 'error', 'error': repr(exc)})


class BackgroundUpdate:
    def __init__(self, base, out, *, device, beta, kl, steps, aim_weight=0.):
        self.closed = False
        context = mp.get_context('spawn')
        self.jobs, self.results = context.Queue(maxsize=2), context.Queue()
        self.process = context.Process(target=update_worker,
                                       args=(str(base), str(out), self.jobs, self.results, device, beta, kl, steps,
                                             aim_weight),
                                       daemon=True, name='rivals-persistent-update')
        self.process.start()

    def submit(self, job):
        self.jobs.put(job, timeout=5.)  # bounded pad-free backpressure

    def poll(self):
        rows = []
        while True:
            try:
                rows.append(self.results.get_nowait())
            except queue.Empty:
                break
        if not self.process.is_alive() and not rows:
            raise RuntimeError('background updater exited')
        return rows

    def close(self):
        if self.closed:
            return
        self.closed = True
        # Only this sitting's own child; no unrelated GPU process is touched.
        if self.process.is_alive():
            try:
                self.jobs.put(None, timeout=.1)
            except queue.Full:
                pass
            self.process.join(timeout=2.)
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(timeout=2.)
        self.jobs.close()
        self.results.close()


def run_sitting(session, updater, out, base_bundle, *, episodes=20, episode_s=45., bc_every=0,
                settle_s=1.5, reset=True, policy_factory, swap, clock=time.perf_counter,
                sleep=time.sleep, frame_hook=None):
    """Injectable orchestration; tests use recorded pixels and mocked pad/model/update."""
    out, base_bundle = Path(out), Path(base_bundle)
    out.mkdir(parents=True, exist_ok=False)
    started, policy_seconds = clock(), 0.
    curve, results, updates, completed = {}, {}, [], set()
    current_bundle = loaded = base_bundle
    stop = None

    def consume():
        nonlocal current_bundle
        messages = updater.poll()
        for message in messages:
            if message['kind'] == 'error':
                raise RuntimeError(message['error'])
            if message['kind'] == 'episode':
                row = message['row']
                curve[row['episode']] = row
                if not row['go_on']:
                    raise RangeError(row['stop_reason'])
            elif message['kind'] == 'update':
                current_bundle = Path(message['bundle'])
                updates.append(message)
                if message['episode'] in curve:
                    curve[message['episode']]['update'] = message['summary']
            elif message['kind'] == 'done':
                completed.add(message['episode'])
        if messages:
            (out/'curve.jsonl').write_text(''.join(json.dumps(curve[i])+'\n' for i in sorted(curve)))

    try:
        for index in range(episodes):
            session.boundary()
            consume()
            arm = arm_for(index, bc_every)
            selected = base_bundle if arm == 'bc' else current_bundle
            if selected != loaded:
                session.swap(selected, swap)
                loaded = selected
            episode_out = out/f'ep-{index:03d}-{arm}'
            print(f'episode {index} ({arm}) bundle={selected}', flush=True)
            policy = policy_factory(session, arm, index, episode_out, frame_hook)
            result = session.run_episode(episode_out, policy, max_s=episode_s, settle_s=settle_s,
                                         reset_before=reset, policy_bundle=selected)
            print(f'episode {index}: {result["result"]}', flush=True)
            results[index] = result
            policy_seconds += max(0., result.get('policy_end_t', 0)-result.get('policy_start_t', 0))
            updater.submit((index, arm, str(episode_out), result))
            # Normal completed episodes can start the next scope immediately.
            # Death continuation must wait for this episode's pixel verdict.
            if result['result'] not in ('deadline', 'replay_complete'):
                if result['result'] != 'range_lost':
                    stop = f'episode {index}: {result["result"]}'
                    break
                end = clock()+30.
                while index not in curve:
                    session.boundary()
                    consume()
                    if clock() >= end:
                        raise RuntimeError('death evidence timed out; no retry')
                    sleep(.02)
            consume()
        # Pad is closed while final update/analysis drains; include this in utilization.
        end = clock()+30.
        while len(completed) < len(results) and clock() < end:
            consume()
            sleep(.02)
        if len(completed) < len(results):
            raise RuntimeError('episode analysis/update did not finish')
    except Exception as exc:
        stop = repr(exc)
    finally:
        try:
            session.close()
        finally:
            updater.close()
        elapsed = clock()-started
        ordered = [curve[i] for i in sorted(curve)]
        (out/'curve.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in ordered))
        meta = {'stop': stop, 'episodes': len(results), 'policy_s': policy_seconds, 'elapsed_s': elapsed,
                'live_time_utilization': policy_seconds/elapsed if elapsed else 0.,
                'updates': updates, 'completed_analysis': len(curve), 'persistent': True}
        (out/'sitting.json').write_text(json.dumps(meta, indent=2)+'\n')
        if ordered:
            plot(ordered, out/'curve.png')
    return meta


class RangeError(RuntimeError):
    pass


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base-bundle', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--game-pid', type=int, required=True)
    ap.add_argument('--live', action='store_true', required=True)
    ap.add_argument('--camera-settings-match', choices=['alt-247-124'], required=True)
    ap.add_argument('--episodes', type=int, default=20)
    ap.add_argument('--episode-s', type=float, default=45.)
    ap.add_argument('--settle-s', type=float, default=1.5)
    ap.add_argument('--bc-every', type=int, default=0)
    ap.add_argument('--no-reset', action='store_true')
    ap.add_argument('--device', default='cuda')
    ap.add_argument('--aim-weight', type=float, default=0.,
                    help='weight of the dense aim advantage in the update (rl.aim.reward; 0 = sparse rewards only)')
    a = ap.parse_args(argv)
    if (not 1 <= a.episodes <= 20 or a.bc_every < 0 or not math.isfinite(a.episode_s)
            or not 0 < a.episode_s or not math.isfinite(a.settle_s) or a.settle_s < 0
            or a.episode_s+a.settle_s > 60 or not 0 < a.game_pid <= 0xffffffff
            or not (math.isfinite(a.aim_weight) and 0 <= a.aim_weight <= 2)):
        ap.error('1-20 episodes, nonnegative bc-every, positive episode+settle <=60s, valid game PID and aim weight 0-2 '
                 'required')
    if a.out.exists():
        ap.error('output exists')
    spec = json.loads((a.base_bundle/'bundle.json').read_text())
    if spec.get('kind') != 'bc2' or 'buttons' in spec['files']:
        ap.error('plain bc2 bundle required')
    from agent import loop as L
    from agent.learned_runner import limit_cpu_threads
    from agent.persistent_runner import BorrowedPolicy, Session
    from policy.live_policy import LivePolicy
    from rl.online.explore import ExploringPolicy
    from rl.online.update import load_weights
    from scripts.capture import Capture
    limit_cpu_threads(True)
    takeover = L.human_takeover_guard()
    session = worker = None
    try:
        focus = L.foreground_pid_guard(a.game_pid)
        if focus() is not True or takeover():
            raise RuntimeError('focus/takeover preflight')
        policy = LivePolicy(a.base_bundle, device=a.device)
        session = Session(policy, L.default_perception(), Capture('dxcam'), focus, takeover)
        session.warm()
        worker = BackgroundUpdate(a.base_bundle, a.out, device=a.device, beta=1., kl=1., steps=40,
                                  aim_weight=a.aim_weight)
        def make_policy(session, arm, index, directory, hook):
            return ExploringPolicy(BorrowedPolicy(session.policy, hook), temperature=1. if arm == 'rl' else 0.,
                                   option_rate_hz=.5 if arm == 'rl' else 0., cam_temperature=1. if arm == 'rl' else 0.,
                                   turn_rate_hz=.5 if arm == 'rl' else 0., seed=index,
                                   log_path=str(directory)+'.explore.jsonl')
        result = run_sitting(session, worker, a.out, a.base_bundle, episodes=a.episodes,
                             episode_s=a.episode_s, settle_s=a.settle_s, bc_every=a.bc_every,
                             reset=not a.no_reset, policy_factory=make_policy, swap=load_weights)
        return 0 if result['stop'] is None else 1
    finally:
        try:
            if session is not None:
                session.close()
            else:
                takeover.close()
        finally:
            if worker is not None:
                worker.close()


if __name__ == '__main__':
    raise SystemExit(main())
