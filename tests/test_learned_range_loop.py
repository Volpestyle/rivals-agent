"""Learned range caller checks with synthetic States and a fake pad only."""
import json
from dataclasses import asdict
from types import SimpleNamespace

import pytest

from agent import loop as runtime
from agent.human_demos import DemoError
from agent.learned_range import LearnedRangeBrain
from agent.intents import Idle
from tests.test_loop import Frames, FakePad, RunLog, jpeg, readers, sends, timeline
from tests.test_range_policy import FixedPolicy, IDENTITY
from policy.range_policy import RuntimeIdentity, DeploymentBinding, digest


def test_neutral_range_policy_disables_warmup_and_idle_attacks():
    brain = LearnedRangeBrain(FixedPolicy((.99, .01)))
    pad = FakePad()
    run = runtime.Loop(Frames(timeline(2)), pad, readers(), brain,
                       brain_name="range", max_s=2, keepalive_s=.1, scoreboard=False)
    result = run.run()
    assert result["keepalives"] == 0 and run.warmup is False
    assert sends(pad) and all(p == runtime.NEUTRAL for p in sends(pad))


@pytest.mark.parametrize("kwargs", [{"decision_hz": 20}, {"max_s": 21}, {"max_s": float("nan")}])
def test_range_contract_refuses_incompatible_loop_before_worker(kwargs):
    with pytest.raises(ValueError):
        runtime.Loop(Frames([]), FakePad(), readers(), LearnedRangeBrain(FixedPolicy()),
                     brain_name="range", **({"max_s": 20} | kwargs))


def test_decision_trace_is_a_snapshot_and_receipt_reaches_actual_recording(tmp_path):
    class Traced:
        source = "range_refusal"
        last = {"reason": "unknown", "probabilities": [0.5, 0.5]}

        def __call__(self, state, memory):
            return Idle()

    brain = Traced()
    decider = runtime.Decider(brain, readers(), 10, False)
    decider.offer(timeline(.1)[0][0], 0., (2560, 1440), [])
    brain.last["probabilities"][0] = 1
    assert decider.latest.trace["probabilities"] == [.5, .5]
    decider.close()
    out = tmp_path / "run"
    receipt = {"checkpoint_sha256": "a" * 64, "scope": "synthetic test"}
    runtime.Loop(Frames(timeline(.3)), FakePad(), readers(), brain,
                 log=RunLog(out, save_fps=0, imwrite=jpeg), warmup=False,
                 scoreboard=False, range_receipt=receipt).run()
    meta = json.loads((out / "meta.json").read_text())
    rows = [json.loads(line) for line in (out / "frames.jsonl").read_text().splitlines()]
    assert meta["range_policy"] == receipt
    assert any(row.get("decision_trace", {}).get("reason") == "unknown" for row in rows)


def range_args(tmp_path):
    identity = tmp_path / "identity.json"
    identity.write_text(json.dumps(vars(IDENTITY)))
    profile = RuntimeIdentity(IDENTITY.patch, "normal", "c" * 64, "d" * 64, "e" * 64, "f" * 64, "1" * 64)
    runtime_file, binding_file = tmp_path / "runtime.json", tmp_path / "binding.json"
    runtime_file.write_text(json.dumps(asdict(profile)))
    binding_file.write_text(json.dumps(asdict(DeploymentBinding("a" * 64, digest(asdict(IDENTITY)), profile, "2" * 64))))
    return ["--live", "--brain", "range", "--range-checkpoint", "absent.pt",
            "--range-sha256", "a" * 64, "--range-identity", str(identity), "--cooldowns", "normal",
            "--range-runtime", str(runtime_file), "--range-deployment", str(binding_file)]


def test_checkpoint_refusal_happens_before_capture_or_pad_attachment(monkeypatch, tmp_path):
    def forbidden():
        pytest.fail("hardware reached before validating the candidate")

    monkeypatch.setattr(runtime, "LiveIO", forbidden)
    monkeypatch.setattr(runtime, "default_perception", forbidden)
    def reject(*args, **kwargs):
        raise DemoError("checkpoint digest mismatch")
    monkeypatch.setattr(LearnedRangeBrain, "from_checkpoint", reject)
    with pytest.raises(SystemExit) as caught:
        runtime.main(range_args(tmp_path))
    assert caught.value.code == 2


@pytest.mark.parametrize("extra", [["--max-s", "21"], ["--max-s", "nan"], ["--cooldowns", "off"]])
def test_bad_trial_config_never_loads_a_model(monkeypatch, tmp_path, extra):
    def forbidden(*args, **kwargs):
        pytest.fail("model reached for invalid trial configuration")
    monkeypatch.setattr(LearnedRangeBrain, "from_checkpoint", forbidden)
    with pytest.raises(SystemExit) as caught:
        runtime.main(range_args(tmp_path) + extra)
    assert caught.value.code == 2


def test_mismatched_checkpoint_cadence_prevents_pad_attachment(monkeypatch, tmp_path):
    monkeypatch.setattr(LearnedRangeBrain, "from_checkpoint", lambda *a, **kw:
                        SimpleNamespace(policy=SimpleNamespace(spec=SimpleNamespace(period_s=.2))))
    monkeypatch.setattr(runtime, "LiveIO", lambda: pytest.fail("pad attached"))
    with pytest.raises(SystemExit) as caught:
        runtime.main(range_args(tmp_path))
    assert caught.value.code == 2


def test_live_requires_runtime_binding_before_loading(monkeypatch, tmp_path):
    monkeypatch.setattr(LearnedRangeBrain, "from_checkpoint", lambda *a, **kw: pytest.fail("model loaded"))
    with pytest.raises(SystemExit) as caught:
        runtime.main(range_args(tmp_path)[:-4])
    assert caught.value.code == 2


def test_scoreboard_timing_retains_board_grab_not_later_range_frame():
    from tests.test_live_pad import FakePad as Device, GameCap, GUARDS, Live, Script

    pad = Device()
    lv = Live(pad_factory=lambda: pad, capture=Script("range"), settle_s=0, **GUARDS)
    io = runtime.LiveIO(lv)
    try:
        lv.cap = GameCap(pad)
        assert io.scoreboard(.05) == "board"
        lo, hi = io.board_capture_interval
        assert 0 <= lo <= hi < lv.frame_t - io.t0
        assert lv.frame == "range" and pad.neutral()
    finally:
        io.close()


def test_loop_records_explicit_scoreboard_acquisition_interval():
    class TimedPad(FakePad):
        def scoreboard(self, hold_s):
            self.board_capture_interval = (.5, .6)
            return super().scoreboard(hold_s)

    result = runtime.Loop(Frames(timeline(.3)), TimedPad(board="SCOREBOARD"), readers(),
                          lambda state, memory: Idle(), warmup=False).run()
    board = result["scoreboards"][0]
    assert board["t"] < .5 and board["captured_t"] == .6
    assert board["capture_interval"] == [.5, .6]
    assert board["capture_clock"] == "grab_start_to_return_loop_seconds"
