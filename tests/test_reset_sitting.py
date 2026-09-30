"""Full sitting/episode/runner plumbing, recorded pixels and a fake pad only.

No model fitting, GPU, capture device or pad factory. Hardware entry points and
model/feature/update work are replaced; orchestration, perception, exploration,
reset, actuator deadline checks, recording and death continuation are real.
"""
import json
import os
from pathlib import Path
import threading
from types import SimpleNamespace as NS

import pytest

cv2 = pytest.importorskip('cv2')
np = pytest.importorskip('numpy')
torch = pytest.importorskip('torch')

from agent import controller as C, learned_runner as R, loop as L
from rl.online import data, episode, sitting, update
from tests.test_live_pad import FakePad
from tests.test_rl_online import FakeBase


ROOT = Path(__file__).parents[1]
F05 = ROOT / 'data/calibration/rl-sitting-20260930-05/ep-000-bc/000002.jpg'
DEATH = ROOT / 'data/calibration/rl-sitting-20260930-04/ep-001-rl/stop.png'


@pytest.mark.skipif(not F05.exists() or not DEATH.exists(), reason='authorized sitting04/05 frames local only')
def test_full_recorded_sitting_spawn_plaza_fall_respawn_and_bc_rl(monkeypatch, tmp_path):
    import policy.live_policy as live_policy
    from policy.bc2 import features, model
    from scripts import capture

    cv2.setNumThreads(2)
    torch.set_num_threads(2)
    out = Path(os.environ.get('RESET_SITTING_TEST_OUT', str(tmp_path / 'sitting')))
    assert not out.exists(), 'preserve previous dry evidence'
    fixture = ROOT / 'tests/fixtures/reentry'
    paths = {'spawn': fixture / 'arrival-spawn-room.jpg',
             'aligned': fixture / 'arrival-live-advance-a.jpg',
             'advance': fixture / 'arrival-live-advance-b.jpg',
             'plaza': fixture / 'arrival-plaza-bot-ahead.jpg', 'small': F05, 'death': DEATH}
    # One consistent frame size across captures; the historical arrival take is
    # 720p. Normalize retained pixels, never modify their source files.
    frames = {key: cv2.resize(cv2.imread(str(path)), (1280, 720)) for key, path in paths.items()}
    percept = L.default_perception()
    assert percept.in_range(frames['death']) is False
    contexts, dispatch, updates = [], [], []
    current = NS(io=None)

    class IO:
        def __init__(self, index):
            self.index, self.t, self.t0, self.n = index, 0., 0., 0
            self.phase, self.policy_start = 'reset', None
            self.frame = frames['spawn' if index in (0, 2) else 'small' if index == 3 else 'plaza']
            self.last_stamp, self.calls, self.expired, self.closed = None, [], False, False
            self.attach_opener = {'kind': 'mocked_no_hardware'}
            self.live = C.Live.__new__(C.Live)
            self.live.attach_opener = self.attach_opener
            self.live._pad, self.live._codes = FakePad(), {name: name for name in C.ALLOWED}
            self.live._lock, self.live._dead = threading.Lock(), False
            self.live._lease_until, self.live._closed = None, threading.Event()
            self.live.sent = dict(C.NEUTRAL)
            self.live._in_range = self.proof
        def now(self):
            return self.t
        def proof(self, frame):
            # Reproduce actual InputExpired inside Live._apply: fresh proof but
            # request's 50 ms deadline elapsed during commit work.
            self.t += .06 if self.index in (0, 3) and not self.expired and self.phase == 'reset' else .001
            if self.index in (0, 3) and self.phase == 'reset':
                self.expired = True
            return percept.in_range(frame)
        def next(self):
            self.t += .02
            self.n += 1
            if self.phase == 'reset':
                if self.index in (0, 2):
                    key = 'spawn' if self.n < 5 else 'aligned' if self.n < 13 else 'advance' if self.n < 24 else 'plaza'
                else:
                    key = 'small' if self.index == 3 and self.n < 15 else 'plaza'
            else:
                key = 'death' if self.index == 1 and self.t - self.policy_start > .6 else 'plaza'
            self.frame, self.last_stamp = frames[key], self.t
            self.live.frame, self.live.frame_t = self.frame, self.t
            if self.index == 3 and self.n <= 2:
                self.t += (.1788759, .1249515)[self.n - 1]  # sitting05 capture discards
            return self.frame, self.last_stamp
        def send_guarded(self, pad, **limits):
            self.live.send_guarded(pad, **limits)
            self.calls.append({'t': self.t, 'frame_t': self.last_stamp, 'phase': self.phase,
                               'pad': dict(pad), **limits})
        def release(self):
            self.live.release()
        def close(self):
            self.closed = True
            self.live.close()

    # The actual actor methods see the same simulated clock as their caller.
    monkeypatch.setattr(C, 'time', NS(perf_counter=lambda: current.io.t))
    monkeypatch.setattr(C, '_real_clock', lambda: current.io.t)
    monkeypatch.setattr(R, 'time', NS(perf_counter=lambda: current.io.t,
                                    sleep=lambda s: setattr(current.io, 't', current.io.t + s)))
    real_safety, real_log = L.LiveSafety, L.RunLog
    monkeypatch.setattr(L, 'LiveSafety', lambda focus, takeover, deadline:
                        real_safety(focus, takeover, deadline, clock=current.io.now))
    monkeypatch.setattr(L, 'foreground_pid_guard', lambda pid: lambda: True)
    monkeypatch.setattr(L, 'human_takeover_guard', lambda: lambda: False)
    def open_io(safety, *args, **kwargs):
        safety.bind(current.io)
        return current.io
    monkeypatch.setattr(L, '_open_live_io', open_io)
    monkeypatch.setattr(capture, 'Capture', lambda *args: NS(backend='fixture', grab=lambda: current.io.frame))
    monkeypatch.setattr(R, 'limit_cpu_threads', lambda real: None)

    class Log(real_log):
        def __init__(self, *args, **kwargs):
            # OpenCV 5 warns on RunLog's JPEG option passed to PNG. Its cached
            # stderr FD can alias pytest's recycled file handles on Windows.
            super().__init__(*args, **kwargs, imwrite=lambda p, f: cv2.imwrite(
                str(p), f, [cv2.IMWRITE_JPEG_QUALITY, 90] if p.suffix == '.jpg' else []))
        def write(self, row, frame=None):
            if row['event'] == 'policy_start':
                current.io.phase, current.io.policy_start = 'policy', row['t']
            elif row['event'] == 'policy_end':
                current.io.phase = 'settle'
            return super().write(row, frame)
        def close(self, meta, segments):
            meta['test_only'] = {'capture': 'recorded pixels', 'pad': 'FakePad',
                                 'model_and_fit': 'mocked', 'live_flag': 'exercise guarded code path only'}
            return super().close(meta, segments)
    monkeypatch.setattr(L, 'RunLog', Log)
    def base_policy(*args, **kwargs):
        base = FakeBase(.45)
        base.reset()
        return base
    monkeypatch.setattr(live_policy, 'LivePolicy', base_policy)
    monkeypatch.setattr(features, 'load_tower', lambda *args: object())
    monkeypatch.setattr(torch, 'load', lambda *args, **kwargs: {'config': {}, 'model': {}})
    monkeypatch.setattr(model, 'Policy2', lambda config: NS(load_state_dict=lambda state: None, eval=lambda: None))
    monkeypatch.setattr(data, 'featurize', lambda fs, *args:
                        (np.zeros((len(fs), 2, 1)), np.zeros((len(fs), 72, 128)), np.zeros((len(fs), 64, 64))))
    def no_fit(cur, base, buffer, **kwargs):
        updates.append(len(buffer))
        return cur, {'mocked_update': True, 'steps': 0}
    monkeypatch.setattr(update, 'update', no_fit)
    def bundle(cur, config, base, dest, **kwargs):
        dest.mkdir(parents=True)
        (dest / 'bundle.json').write_text((base / 'bundle.json').read_text())
        return dest
    monkeypatch.setattr(update, 'write_bundle', bundle)
    # In-process dispatch runs BOTH actual entry points; no child can escape the
    # mocked hardware/model boundary. Real LatestPolicy thread remains enabled.
    def call(command):
        assert command[1:3] == ['-m', 'rl.online.episode']
        index = len(dispatch)
        io = current.io = IO(index)
        dispatch.append(command)
        rc = episode.main(command[3:])
        contexts.append(io)
        assert io.closed and io.live._pad.neutral()
        return rc
    monkeypatch.setattr(sitting.subprocess, 'call', call)
    base = tmp_path / 'base'
    base.mkdir()
    (base / 'bundle.json').write_text(json.dumps({'kind': 'bc2', 'live': {'jump': True, 'spider_power': True},
        'files': {'checkpoint': {'path': 'mock.pt', 'sha256': 'mock'},
                  'vision': {'path': 'mock'}, 'vision_config': {'path': 'mock'}}}))
    rc = sitting.main(['--base-bundle', str(base), '--out', str(out), '--episodes', '5',
                       '--episode-s', '2', '--live', '--game-pid', '1',
                       '--camera-settings-match', 'alt-247-124', '--reset', '--settle-s', '.2',
                       '--yaw-scale', '1', '--device', 'cpu'])
    rows = [json.loads(line) for line in (out / 'curve.jsonl').read_text().splitlines()]
    assert rc == 0 and len(rows) == 5 and [r['arm'] for r in rows] == ['bc', 'rl', 'bc', 'rl', 'bc']
    assert all(r['reset'] == 'ready' for r in rows)
    assert rows[1]['result'] == 'range_lost' and rows[1]['death'] == 1
    assert rows[2]['reset_detail']['start_state'] == 'spawn'  # continued after observed death
    assert rows[3]['reset_detail']['start_state'] == 'plaza'
    assert updates == [1, 2]
    for i, io in enumerate(contexts):
        assert io.live._pad.neutral()
        assert all(c['t'] < c['not_after'] and c['t'] - c['frame_t'] < .1 for c in io.calls)
        reset_calls = [c for c in io.calls if c['phase'] == 'reset']
        if i in (0, 2):
            assert any(c['pad']['ly'] == 1 for c in reset_calls)
        if i == 4:
            assert not reset_calls
        assert not any(c['phase'] == 'settle' for c in io.calls)
        if i != 1:
            assert rows[i]['settle']['result'] == 'settled'
        records = [json.loads(line) for line in (out / f'ep-{i:03d}-{rows[i]["arm"]}' / 'frames.jsonl').read_text().splitlines()]
        if i in (0, 3):
            assert any(r['event'] == 'reset_discard' and r['clause'] == 'input_expired' for r in records)
        if i == 3:
            assert sum(r['event'] == 'observation_discard' for r in records) == 2
    (out / 'mock-boundary.json').write_text(json.dumps({'sources': {k: str(p) for k, p in paths.items()},
        'frame_size': [1280, 720], 'model_update': 'mocked, no fitting', 'hardware': 'FakePad only',
        'real_paths': ['sitting.main', 'episode.main', 'learned_runner.main', 'warm_perception',
                       'LatestPolicy', 'run_phases', 'ResetRunner', 'LiveSafety', 'Live._apply', 'data.episode'],
        'episodes': [{'index': io.index, 'mock_sends': len(io.calls), 'injected_actuator_expiry': io.expired,
                      'closed_neutral': io.live._pad.neutral(), 'calls': io.calls} for io in contexts]}, indent=2))
