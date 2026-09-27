"""Synthetic-only tests; never open corpus, media, checkpoint or GPU."""
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import replay_live_fallback_train as replay
from policy.range_bc import steps, vocab


def probabilities(action=None, yaw=0., pitch=0.):
    actions = [[0.] * vocab.N for _ in range(3)]
    if action is not None:
        actions[0][action] = .5
    cameras = []
    for degree in (yaw, pitch):
        p = [0.] * vocab.CAMERA_CLASSES
        p[vocab.camera_class(degree)] = 1.
        cameras.append(p)
    return actions, cameras


def test_raw_camera_survives_unknown_execution_calibration_and_mask_is_preserved():
    index = vocab.INDEX["web_cluster"]
    mask = [True] * vocab.N
    decoded = replay.raw_decode(*probabilities(index, 2.5, -.6), None, mask)
    assert decoded["yaw"] == 2.5 and decoded["pitch"] == -.6
    assert decoded["press"][index] == decoded["held"][index] == 1
    repeated = replay.raw_decode(*probabilities(index, 2.5, -.6), decoded, mask)
    assert repeated["press"][index] == 0
    mask[index] = False
    masked = replay.raw_decode(*probabilities(index, 2.5, -.6), None, mask)
    assert not any(masked["held"]) and not any(masked["press"])
    assert masked["yaw"] == 2.5


def test_metrics_distinguish_action_only_total_neutral_and_supported_human_actions():
    mask = [False] * vocab.N
    index = vocab.INDEX["web_cluster"]
    mask[index] = True
    targets = [replay.raw_decode(*probabilities(None, 2.5, 0), None, mask),
               replay.raw_decode(*probabilities(index, 0, 0), None, mask),
               replay.raw_decode(*probabilities(), None, mask)]
    # An unsupported human action remains in all-human comparisons.
    targets[2]["press"][vocab.INDEX["melee"]] = 1
    result = replay.metrics(targets, mask, .1)
    assert result["all_press_steps"] == 2 and result["supported_press_steps"] == 1
    assert result["neutral"]["supported"]["action_only_fraction"] == pytest.approx(2 / 3)
    assert result["neutral"]["supported"]["action_and_raw_camera_fraction"] == pytest.approx(1 / 3)
    assert result["camera"]["yaw"]["abs_total_deg"] == 2.5
    assert result["camera"]["yaw"]["abs_mean_deg"] == pytest.approx(2.5 / 3)
    assert result["camera"]["yaw"]["abs_p95_deg"] == pytest.approx(2.25)


def test_unknown_camera_is_not_zero_or_in_neutral_denominator():
    target = replay.raw_decode(*probabilities(), None, [True] * vocab.N)
    target["pitch"] = target["cp"] = None
    result = replay.metrics([target], [True] * vocab.N, 1.)
    assert result["camera"]["pitch"]["known_steps"] == 0
    assert result["camera"]["pitch"]["abs_mean_deg"] is None
    assert result["neutral"]["all"]["action_and_raw_camera_fraction"] is None


@pytest.mark.parametrize("shown", [(1, 30, (1, 1000)), (0, 31, (1, 1000)), (0, 30, (1, 120))])
def test_wrong_ordinal_pts_or_timebase_refused(shown):
    row = {"i": 7, "frame": {"pts": 30, "timebase": [1, 1000]}}
    with pytest.raises(ValueError, match="mismatch"):
        replay.check_frame_identity(0, shown, row)
    replay.check_frame_identity(0, (0, 30, (1, 1000)), row)


def test_existing_sealed_guard_failure_prevents_step_or_media_access(monkeypatch):
    def denied():
        raise steps.StepError("sealed denylist refused")
    monkeypatch.setattr(steps, "load_denylist", denied)
    monkeypatch.setattr(steps, "load", lambda *a, **kw: pytest.fail("steps opened after refusal"))
    with pytest.raises(steps.StepError):
        replay.fixed_selection()


@pytest.mark.parametrize("mismatch", ["sha", "split", "session", "media", "run", "path"])
def test_fixed_source_contract_refuses_changed_identity_before_media(monkeypatch, mismatch):
    rows = [{"gap_free": True, "frame": {"video_path": str(replay.VIDEO), "frame_index": i}}
            for i in range(3607)]
    session = SimpleNamespace(sha256=replay.STEPS_SHA, session_id=replay.SESSION, split="train", rows=rows,
                             header={"media_sha256": replay.VIDEO_SHA, "video_size": [2560, 1440]})
    sentinel = object()
    monkeypatch.setattr(steps, "load_denylist", lambda: sentinel)
    def load(path, *, denylist):
        assert path == replay.STEPS and denylist is sentinel
        return session
    monkeypatch.setattr(steps, "load", load)
    monkeypatch.setattr(steps, "runs", lambda *a, **kw: [(7, 12557)])
    assert len(replay.fixed_selection()[1]) == 3600
    if mismatch == "sha":
        session.sha256 = "changed"
    elif mismatch == "split":
        session.split = "val"
    elif mismatch == "session":
        session.session_id = "another"
    elif mismatch == "media":
        session.header["media_sha256"] = "other"
    elif mismatch == "run":
        monkeypatch.setattr(steps, "runs", lambda *a, **kw: [(8, 12557)])
    else:
        rows[7]["frame"]["video_path"] = "arbitrary.mkv"
    with pytest.raises(ValueError):
        replay.fixed_selection()


def test_streamed_replay_self_feeds_raw_camera_and_never_human_history(monkeypatch):
    rows = [{"i": i, "anchor_ns": i, "frame": {}, "press": [0] * vocab.N} for i in range(3)]
    human = replay.raw_decode(*probabilities(vocab.INDEX["move_left"], 40, 40), None, [True] * vocab.N)
    monkeypatch.setattr(steps, "target", lambda row, cal: human)
    previous_values = []
    def predict(frame, previous):
        previous_values.append(previous)
        return probabilities(None, 2.5, -.6)
    frames = ((object(), (i, i, (1, 1000))) for i in range(3))
    stream = io.StringIO()
    _, predicted, _ = replay.replay(rows, {}, frames, predict, [True] * vocab.N, stream)
    assert previous_values[0] is None
    assert previous_values[1:] == predicted[:2]
    assert previous_values[1]["yaw"] == 2.5 and previous_values[1]["pitch"] == -.6
    assert previous_values[1] != human
    assert len([json.loads(line) for line in stream.getvalue().splitlines()]) == 3


def test_no_arbitrary_source_or_capture_cli():
    text = Path(replay.__file__).read_text()
    assert 'p.add_argument("--video"' not in text
    assert 'p.add_argument("--steps"' not in text
    assert "from agent.controller import Live" not in text
    assert "import vgamepad" not in text


def test_status_timestamp_matches_helper_resolution_and_guard_refuses_before_media(tmp_path, monkeypatch):
    from scripts import profile_range_bc_live, job_status
    monkeypatch.setattr(replay, "EVIDENCE", tmp_path)
    writes = []
    monkeypatch.setattr(job_status, "write", lambda name, **kw: writes.append(kw))
    def refused(output):
        raise RuntimeError("game/OBS present")
    monkeypatch.setattr(profile_range_bc_live, "PCGuard", refused)
    monkeypatch.setattr(replay, "fixed_selection", lambda: pytest.fail("source opened after process refusal"))
    with pytest.raises(RuntimeError, match="game/OBS"):
        replay.main(["inspect"])
    assert type(writes[0]["started"]) is int
    assert writes[-1]["stage"] == "failed"
    assert (tmp_path / "inspect/ERROR.json").is_file()
    with pytest.raises(ValueError, match="preserve prior evidence"):
        replay.main(["inspect"])


def test_replay_manifest_preserves_contract_and_does_not_claim_fps_or_discarded_decode():
    prepared = {"format": "range-bc-inference-fps-v1", "checkpoint_sha256": "pin", "live_mask": [True],
                "thresholds": [.5], "device": "cuda", "phases": ["A1", "B", "A2"], "capture_hz": 30,
                "decoder": "outputs discarded", "comparison": "active-inference cost", "fps_cap": None}
    manifest = replay.replay_manifest(prepared)
    assert manifest["checkpoint_sha256"] == "pin" and manifest["live_mask"] == [True]
    assert manifest["thresholds"] == [.5] and manifest["device"] == "cuda"
    assert manifest["format"] == "range-bc-fallback-train-replay-v1"
    assert "phases" not in manifest and "capture_hz" not in manifest and "fps_cap" not in manifest
    assert "raw median camera" in manifest["decoder"]
    assert prepared["phases"] == ["A1", "B", "A2"]  # original evidence stays unchanged
