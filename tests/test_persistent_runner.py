"""Persistent lifecycle, real guards/runner with injected pad/capture/model."""
import json
import os
import time
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from agent import persistent_runner as P
from agent import learned_runner as R
from agent.controller import NEUTRAL, RangeLost
from rl.online import persistent_sitting as S


class Log:
    def __init__(self, out):
        self.out = Path(out)
        self.out.mkdir(parents=True)
        self.rows = []
    def write(self, row, frame=None):
        self.rows.append(row)
    def save(self, *args, **kwargs):
        return 'stop.png'
    def close(self, result, segments):
        (self.out/'frames.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in self.rows))


@pytest.fixture
def session():
    state = NS(t=10., closed=0, model_closed=0, capture_closed=0, raw_closed=0,
               takeover=False, focused=True, scopes=[], sends=[])
    policy = NS(reset=lambda: None, close=lambda: setattr(state, 'model_closed', state.model_closed+1),
                step=lambda f, t=None: NS(held={}, press={}, release={}, yaw_deg=0., pitch_deg=0.))
    class Takeover:
        def __call__(self):
            return state.takeover
        def close(self):
            state.raw_closed += 1
    capture = NS(cam=NS(release=lambda: setattr(state, 'capture_closed', state.capture_closed+1)))
    def opener(safety):
        state.scopes.append(safety)
        io = NS(t0=state.t, now=lambda: state.t-io.t0,
                release=lambda: state.sends.append(dict(NEUTRAL)))
        def close():
            state.closed += 1
        io.close = close
        safety.bind(io)
        return io
    class Runner:
        def __init__(self, io, percept, guard, policy, deadline, **kwargs):
            self.io, self.percept, self.guard, self.policy = io, percept, guard, policy
            self.deadline, self.log = deadline, kwargs['log']
            self.last_frame = self.worker = None
        def write(self, row):
            self.log.write(row)
        def run(self):
            self.policy.reset()
            state.t = self.io.t0+self.deadline
            return {'result': 'deadline'}
    percept = NS(in_range=lambda f: True, idle=lambda f: False)
    result = P.Session(policy, percept, capture, lambda: state.focused, Takeover(),
                       io_factory=opener, clock=lambda: state.t,
                       sleep=lambda s: setattr(state, 't', state.t+s),
                       runner_factory=Runner, log_factory=Log)
    yield result, state
    result.close()


def test_multiple_episodes_keep_resources_and_close_each_pad(session, tmp_path):
    s, state = session
    for index in range(3):
        result = s.run_episode(tmp_path/str(index), P.BorrowedPolicy(s.policy), max_s=45, settle_s=0)
        assert result['result'] == 'deadline'
        assert not s.active and state.raw_closed == state.capture_closed == state.model_closed == 0
        assert state.scopes[-1].status['close_returned']
    assert len(state.scopes) == 3
    assert all(scope.deadline == 55+45*i for i, scope in enumerate(state.scopes))
    s.close()
    assert state.raw_closed == state.capture_closed == state.model_closed == 1


def test_takeover_between_episodes_forbids_new_attach(session, tmp_path):
    s, state = session
    s.run_episode(tmp_path/'a', P.BorrowedPolicy(s.policy), max_s=1, settle_s=0)
    state.takeover = True
    with pytest.raises(RangeLost, match='between_episodes'):
        s.run_episode(tmp_path/'b', P.BorrowedPolicy(s.policy), max_s=1, settle_s=0)
    assert len(state.scopes) == 1


def test_active_scope_and_unfinished_worker_forbid_swap(session):
    s, state = session
    def forbidden(*args):
        pytest.fail('no weight mutation')
    s.active = True
    with pytest.raises(RuntimeError):
        s.swap('bundle', forbidden)
    s.active, s.poisoned = False, True
    with pytest.raises(RuntimeError):
        s.swap('bundle', forbidden)


def test_worker_join_failure_prevents_any_later_scope(session, tmp_path):
    s, state = session
    original = s.runner_factory
    class Stuck(original):
        def run(self):
            result = super().run()
            self.worker = NS(close=lambda: False)
            return result
    s.runner_factory = Stuck
    result = s.run_episode(tmp_path/'first', P.BorrowedPolicy(s.policy), max_s=1, settle_s=0)
    assert result['result'] == 'policy_worker_did_not_stop'
    assert result['safety']['close_returned'] and s.poisoned
    with pytest.raises(RuntimeError):
        s.run_episode(tmp_path/'second', P.BorrowedPolicy(s.policy), max_s=1, settle_s=0)
    assert len(state.scopes) == 1


def test_borrow_restores_camera_sampling_intercept_and_keeps_model():
    original = lambda f: 'original'
    owner = NS(_bc2_predict=original, close=lambda: pytest.fail('owner close'))
    borrowed = P.BorrowedPolicy(owner)
    borrowed._bc2_predict = lambda f: 'intercepted'
    assert owner._bc2_predict(None) == 'intercepted'
    borrowed.close()
    assert owner._bc2_predict is original


@pytest.mark.parametrize('episode,settle', [(60, 1), (0, 0), (float('nan'), 0), (45, -1)])
def test_scope_budget_rejected_before_attach(session, tmp_path, episode, settle):
    s, state = session
    with pytest.raises(ValueError):
        s.run_episode(tmp_path/'x', P.BorrowedPolicy(s.policy), max_s=episode, settle_s=settle)
    assert not state.scopes


def test_defaults_initial_bc_then_rl():
    assert [S.arm_for(i) for i in range(5)] == ['bc', 'rl', 'rl', 'rl', 'rl']
    assert [S.arm_for(i, 2) for i in range(5)] == ['bc', 'rl', 'bc', 'rl', 'bc']


def test_reset_has_separate_bounded_scope(session, tmp_path):
    s, state = session
    class Reset:
        def __init__(self, io, *args, **kwargs):
            self.io, self.last_frame, self.worker = io, None, None
        def reset(self):
            state.t += 4
            return {'result': 'ready', 'status': 'ready'}
    result = s.run_episode(tmp_path/'ep', P.BorrowedPolicy(s.policy), max_s=55., settle_s=0.,
                           reset_before=True, reset_factory=Reset)
    assert result['reset']['status'] == 'ready'
    assert len(state.scopes) == 2 and all(x.status['close_returned'] for x in state.scopes)
    assert state.scopes[0].deadline == 40 and state.scopes[1].deadline == 69
    assert result['policy_end_t']-result['policy_start_t'] == 55
    assert (tmp_path/'resets/ep/result.json').exists()


def test_frame_label_hook_cannot_change_pixels_or_returned_action():
    np = pytest.importorskip('numpy')
    frame = np.ones((2, 3, 3), np.uint8)
    step = object()
    def label(pixels, stamp):
        assert stamp == 7 and not pixels.flags.writeable
        with pytest.raises(ValueError):
            pixels[:] = 0
        return 'ignored label'
    owner = NS(step=lambda f, t=None: step)
    borrowed = P.BorrowedPolicy(owner, label)
    assert borrowed.step(frame, t=7) is step
    assert frame.sum() == 18


def test_native_lifecycle_uses_explicit_detach_and_native_button_codes(monkeypatch, tmp_path):
    import sys
    from agent import camera_calibration, pad_bindings
    from tests.test_live_pad import FakePad, Cap
    codes = {name: index+1 for index, name in enumerate(pad_bindings.XUSB_NAMES.values())}
    monkeypatch.setitem(sys.modules, 'vgamepad', NS(XUSB_BUTTON=NS(**codes)))
    pads = []
    class Pad(FakePad):
        def __init__(self):
            super().__init__()
            self.detached = False
        def detach(self):
            assert self.neutral()
            self.detached = True
    def factory():
        pad = Pad()
        pads.append(pad)
        return pad
    monkeypatch.setattr(camera_calibration, 'native_pad', factory)
    class Takeover:
        def __call__(self):
            return False
        def close(self):
            pass
    cap = Cap()
    cap.cam = NS(release=lambda: None)
    percept = NS(in_range=lambda f: f == 'range', idle=lambda f: False, size=lambda f: (2560, 1440))
    s = P.Session(R.StubPolicy(), percept, cap, lambda: True, Takeover(), log_factory=Log)
    try:
        for index in range(2):
            result = s.run_episode(tmp_path/str(index), P.BorrowedPolicy(s.policy), max_s=.3, settle_s=0.)
            assert result['result'] == 'deadline'
            assert pads[-1].detached and s.pad is None
        assert len(pads) == 2
        assert all(isinstance(button, int) for pad in pads for buttons, _ in pad.reports for button in buttons)
    finally:
        s.close()


def test_async_results_are_only_applied_at_boundaries(session, tmp_path, monkeypatch):
    s, state = session
    swaps = []
    s.warm = lambda: None
    class Update:
        pending = []
        def submit(self, job):
            i, arm, directory, result = job
            self.pending += [{'kind': 'episode', 'row': {'episode': i, 'arm': arm, 'go_on': True}},
                             {'kind': 'update', 'episode': i, 'bundle': f'updated-{i}', 'summary': {}},
                             {'kind': 'done', 'episode': i}]
        def poll(self):
            rows, self.pending = self.pending, []
            return rows
        def close(self):
            pass
    def swap(policy, bundle):
        assert not s.active and all(scope.status['close_returned'] for scope in state.scopes)
        swaps.append(str(bundle))
    monkeypatch.setattr(S, 'plot', lambda *a: None)
    result = S.run_sitting(s, Update(), tmp_path/'sitting', 'base', episodes=3, settle_s=0, reset=False,
                           policy_factory=lambda s, *a: P.BorrowedPolicy(s.policy), swap=swap,
                           clock=lambda: state.t, sleep=lambda t: setattr(state, 't', state.t+t))
    assert result['stop'] is None and result['episodes'] == 3
    assert swaps == ['updated-0', 'updated-1']
    assert result['live_time_utilization'] > .8


@pytest.mark.parametrize('reason,died,expected', [('range_lost', True, 2), ('range_lost', False, 1),
                                               ('human_takeover', True, 1), ('focus_lost', True, 1)])
def test_death_continuation_uses_pixel_verdict_and_never_retries_safety(reason, died, expected,
                                                                    tmp_path, monkeypatch):
    state = NS(t=0., closed=False, episodes=0)
    class Session:
        def boundary(self):
            pass
        def run_episode(self, *args, **kwargs):
            state.episodes += 1
            state.t += 45
            return {'result': reason if state.episodes == 1 else 'deadline',
                    'reset': {'status': 'ready'}, 'policy_start_t': 0., 'policy_end_t': 45.}
        def close(self):
            state.closed = True
    class Update:
        pending = []
        def submit(self, job):
            index, arm, _, result = job
            go_on, message = S.after_episode(result['result'], died, 'ready')
            self.pending += [{'kind': 'episode', 'row': {'episode': index, 'arm': arm, 'go_on': go_on,
                                                         'stop_reason': message}}, {'kind': 'done', 'episode': index}]
        def poll(self):
            rows, self.pending = self.pending, []
            return rows
        def close(self):
            pass
    monkeypatch.setattr(S, 'plot', lambda *a: None)
    result = S.run_sitting(Session(), Update(), tmp_path/'death', 'base', episodes=2,
                           policy_factory=lambda *a: None, swap=lambda *a: None,
                           clock=lambda: state.t, sleep=lambda t: setattr(state, 't', state.t+t))
    assert result['episodes'] == expected and state.closed
    assert (result['stop'] is None) == (expected == 2)


def test_background_worker_uses_completed_episodes_and_never_updates_safety_stop(tmp_path, monkeypatch):
    import queue
    torch = pytest.importorskip('torch')
    from policy.bc2 import model, features
    from rl.online import data, update
    monkeypatch.setattr(torch, 'set_num_interop_threads', lambda n: None)
    monkeypatch.setattr(torch, 'load', lambda *a, **k: {'config': {}, 'model': {}})
    monkeypatch.setattr(model, 'Policy2', lambda *a: NS(load_state_dict=lambda *a: None, eval=lambda: None))
    monkeypatch.setattr(features, 'load_tower', lambda *a: object())
    checkpoint = tmp_path/'base.pt'
    checkpoint.write_bytes(b'mocked weights')
    files = {'checkpoint': {'path': 'base.pt', 'sha256': update._sha256(checkpoint)},
             'vision': {'path': 'unused'}, 'vision_config': {'path': 'unused'}}
    (tmp_path/'bundle.json').write_text(json.dumps({'files': files, 'live': {}}))
    ep = {'events': {'death': 0, 'hit': 0, 'ko': 0}, 'seconds': 45,
          'reward': __import__('numpy').zeros(2)}
    monkeypatch.setattr(data, 'episode', lambda *a, **k: ep)
    calls = []
    def fit(cur, base, buffer, **kwargs):
        calls.append(len(buffer))
        return cur, {'steps': 0, 'mocked': True}
    monkeypatch.setattr(update, 'update', fit)
    monkeypatch.setattr(update, 'write_bundle', lambda *a, **k: tmp_path/'updated')
    jobs, results = queue.Queue(), queue.Queue()
    for i, reason in enumerate(('deadline', 'human_takeover')):
        jobs.put((i, 'rl', 'mocked', {'result': reason, 'reset': {'status': 'skipped'}, 'policy_start_t': 0}))
    jobs.put(None)
    S.update_worker(tmp_path, tmp_path, jobs, results, 'cpu', 1., 1., 0)
    rows = []
    while not results.empty():
        rows.append(results.get())
    assert calls == [1]
    assert [r['kind'] for r in rows] == ['episode', 'update', 'done', 'episode', 'done']


@pytest.mark.skipif(not os.environ.get('PERSISTENT_SITTING_TEST_OUT'),
                    reason='opt-in timing check; set a new PERSISTENT_SITTING_TEST_OUT directory')
def test_recorded_frames_real_runner_mock_pad_utilization(tmp_path, monkeypatch):
    cv2 = pytest.importorskip('cv2')
    cv2.setNumThreads(2)
    from agent import loop as L
    frame = cv2.imread(str(Path(__file__).parent/'fixtures/reentry/arrival-plaza-bot-ahead.jpg'))
    percept = L.default_perception()
    assert percept.in_range(frame)
    state = NS(opens=0, closes=0, sends=[], policy_closed=0, raw_closed=0, cap_closed=0)
    class Policy(R.StubPolicy):
        def close(self):
            state.policy_closed += 1
    class Takeover:
        def __call__(self):
            return False
        def close(self):
            state.raw_closed += 1
    class IO:
        def __init__(self, safety):
            state.opens += 1
            self.t0, self.closed, self.safety = time.perf_counter(), False, safety
            safety.bind(self)
        def now(self):
            return time.perf_counter()-self.t0
        def next(self):
            time.sleep(.01)
            return frame, self.now()
        def release(self):
            pass
        def send_guarded(self, pad, **bounds):
            assert not self.closed and self.safety.check()
            assert self.now() <= bounds['not_after']
            assert bounds['scope_not_after'] <= self.safety.deadline-self.t0
            state.sends.append(pad)
        def close(self):
            if not self.closed:
                state.closes += 1
                self.closed = True
    class NativeLog(L.RunLog):
        def __init__(self, out):
            super().__init__(out, save_fps=2., imwrite=lambda p, f: cv2.imwrite(str(p), f))
    model = Policy()
    s = P.Session(model, percept, NS(grab=lambda: frame, cam=NS(release=lambda: setattr(state, 'cap_closed', state.cap_closed+1))),
                  lambda: True, Takeover(), io_factory=IO, log_factory=NativeLog)
    class Update:
        def __init__(self):
            import queue
            self.pending, self.threads = queue.Queue(), []
        def submit(self, job):
            import threading
            i, arm, directory, result = job
            self.pending.put({'kind': 'episode', 'row': {'episode': i, 'arm': arm, 'go_on': True}})
            def finish():
                if arm == 'rl':
                    time.sleep(2.)  # mock a two-second AWR update overlapping the next episode
                    self.pending.put({'kind': 'update', 'episode': i, 'bundle': f'mocked-{i}', 'summary': {'mocked': True}})
                self.pending.put({'kind': 'done', 'episode': i})
            thread = threading.Thread(target=finish)
            self.threads.append(thread)
            thread.start()
        def poll(self):
            import queue
            rows = []
            while True:
                try:
                    rows.append(self.pending.get_nowait())
                except queue.Empty:
                    break
            return rows
        def close(self):
            for thread in self.threads:
                thread.join()
    monkeypatch.setattr(S, 'plot', lambda *a: None)
    out = Path(os.environ['PERSISTENT_SITTING_TEST_OUT'])
    swaps = []
    def swap(policy, bundle):
        assert not s.active
        swaps.append(str(bundle))
    result = S.run_sitting(s, Update(), out, 'stub', episodes=4, episode_s=5., settle_s=0, reset=False,
                           policy_factory=lambda s, *a: P.BorrowedPolicy(s.policy), swap=swap)
    assert result['stop'] is None and result['live_time_utilization'] > .8
    assert state.opens == state.closes == 4 and state.sends and swaps == ['mocked-1']
    assert state.policy_closed == state.cap_closed == state.raw_closed == 1
    for ep in out.glob('ep-*'):
        assert (ep/'stop.png').exists() and (ep/'frames.jsonl').stat().st_size > 0
    print('mocked persistent utilization', result['live_time_utilization'], 'elapsed', result['elapsed_s'])
