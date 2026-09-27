"""Synthetic only: no desktop, pad driver, checkpoints or recordings under data/."""
import hashlib
import json
from pathlib import Path
import shutil
import threading
import time
from types import SimpleNamespace

import pytest

from agent import live_range_bc as h
from agent.controller import Cal, Live, NEUTRAL, RangeLost
from policy.range_bc import executor, vocab


class FakePad:
    def __init__(self):
        self.reports = []
        self.reset()

    def reset(self):
        self.state = dict(NEUTRAL)

    def press_button(self, button):
        self.state["buttons"] += (button,)

    def left_joystick_float(self, x, y):
        self.state.update(lx=x, ly=y)

    def right_joystick_float(self, x, y):
        self.state.update(rx=x, ry=y)

    def left_trigger_float(self, v):
        self.state["lt"] = v

    def right_trigger_float(self, v):
        self.state["rt"] = v

    def update(self):
        self.reports.append((time.perf_counter(), self.state.copy()))


class MemoryJournal:
    def __init__(self):
        self.events, self.frames, self.documents = [], [], {}
        self.closed = False

    def event(self, **value):
        self.events.append(value)

    def frame(self, frame, captured, role):
        self.frames.append((frame, captured, role))

    def write(self, name, value):
        self.documents[name] = value

    def close(self):
        self.closed = True

    def finish_frames(self):
        return {"dropped_frames": 0}


def outputs(action="web_cluster"):
    actions = [[0.] * vocab.N for _ in range(3)]
    actions[0][vocab.INDEX[action]] = 1.
    camera = [[0.] * vocab.CAMERA_CLASSES for _ in range(2)]
    camera[0][vocab.ZERO_CLASS] = camera[1][vocab.ZERO_CLASS] = 1.
    return actions, camera


def setup_live():
    pad = FakePad()
    cap = SimpleNamespace(screen=True)
    cap.grab = lambda: [cap.screen]
    guard = lambda frame: frame[0]
    live = Live(pad_factory=lambda: pad, capture=cap, guard=guard, settle_s=0)
    return live, cap, pad, guard


def run_options(guard, **extra):
    return dict(mask=vocab.live_mask([50] * vocab.N), levels=(.5,) * vocab.N, cal=None,
                duration=.12, stop_requested=lambda: False, range_guard=guard,
                feed_reader=lambda f: None, **extra)


def test_decode_matches_executor_masks_taps_and_per_action_thresholds():
    actions, cameras = outputs()
    actions[0][vocab.INDEX["ultimate"]] = 1
    actions[0][vocab.INDEX["goh_targeting"]] = 1
    actions[0][vocab.INDEX["jump"]] = .4
    actions[1][vocab.INDEX["get_over_here"]] = .7
    actions[2][vocab.INDEX["get_over_here"]] = .7
    levels = [.5] * vocab.N
    levels[vocab.INDEX["jump"]] = .3
    decision = h.decode(actions, cameras, None, vocab.live_mask([50] * vocab.N), levels, None)
    assert decision.held[vocab.INDEX["jump"]] == 1
    assert decision.press[vocab.INDEX["get_over_here"]] == decision.release[vocab.INDEX["get_over_here"]] == 1
    assert not decision.held[vocab.INDEX["ultimate"]]
    assert not decision.held[vocab.INDEX["goh_targeting"]]
    assert decision.pad["buttons"] == ("LB", "RB")
    assert decision.pad["lt"] == 1 and decision.pad["rx"] == decision.pad["ry"] == 0


def test_x_ban_is_independent_of_decoder_and_nonfinite_is_refused(monkeypatch):
    mask = vocab.live_mask([50] * vocab.N)
    actions, cameras = outputs()
    monkeypatch.setattr(executor, "pad_state", lambda *a, **kw: {**NEUTRAL, "buttons": ("X",)})
    with pytest.raises(ValueError, match="X is banned"):
        h.decode(actions, cameras, None, mask, (.5,) * vocab.N, None)
    actions[0][0] = float("nan")
    with pytest.raises(ValueError, match="nonfinite"):
        h.decode(actions, cameras, None, mask, (.5,) * vocab.N, None)


def test_checkpoint_pinned_thresholds_and_support_cannot_enable_unsendable():
    digest = "f" * 64
    artifact = {"checkpoint_sha256": digest, "actions": {n: {"threshold": .2} for n in vocab.NAMES}}
    assert h.thresholds(artifact, digest) == (.2,) * vocab.N
    with pytest.raises(ValueError, match="checkpoint mismatch"):
        h.thresholds(artifact, "0" * 64)
    with pytest.raises(ValueError):
        h.thresholds(float("nan"), digest)
    counts = [50] * vocab.N
    counts[vocab.INDEX["jump"]] = 49
    mask = vocab.live_mask(counts, None)
    support = dict(checkpoint_sha256=digest, press=counts, swing_mode=None, live_mask=list(mask))
    assert h.support_mask(support, digest) == mask
    assert not mask[vocab.INDEX["jump"]] and not mask[vocab.INDEX["web_swing"]]
    support["live_mask"][vocab.INDEX["ultimate"]] = True
    with pytest.raises(ValueError, match="differs"):
        h.support_mask(support, digest)


def test_calibration_never_silently_uses_historical_maps():
    settings = dict(binding_profile=h.PROFILE, swing_mode=vocab.PAD_SWING_MODE, cooldowns="normal", patch="synthetic")
    assert h.calibration(settings, camera_disabled=True) is None
    with pytest.raises(KeyError):
        h.calibration(settings, camera_disabled=False)
    settings["calibration"] = dict(evidence="synthetic-only", yaw_map=[[0, 0], [1, 100]],
                                   pitch_map=[[0, 0], [1, 80]], yaw_deadzone=.05, pitch_deadzone=.05)
    cal = h.calibration(settings, camera_disabled=False)
    assert cal.yaw_map[-1][1] == 100
    settings["calibration"]["yaw_map"][1][1] = float("nan")
    with pytest.raises(ValueError):
        h.calibration(settings, camera_disabled=False)


def test_live_success_uses_existing_guarded_actuator_and_retains_proof():
    live, cap, pad, guard = setup_live()
    journal = MemoryJournal()
    result = h.run(live, lambda f, p: outputs(), journal, **run_options(guard))
    assert result["stop_reason"] == "duration", result
    assert result["scorecard"]["successful_sends"] > 0
    assert any(s["lt"] for _, s in pad.reports)
    assert all("X" not in s["buttons"] for _, s in pad.reports)
    assert pad.reports[-1][1] == NEUTRAL
    assert any(role == "send-proof" for _, _, role in journal.frames)
    assert journal.closed


def test_hud_loss_stops_even_an_idle_policy():
    live, cap, pad, guard = setup_live()
    cap.screen = False
    result = h.run(live, lambda f, p: outputs(), MemoryJournal(), **run_options(guard))
    assert result["stop_reason"] == "range_lost"
    assert not any(s != NEUTRAL for _, s in pad.reports)


@pytest.mark.parametrize("cause", ["duration", "keypress", "focus_lost"])
def test_stalled_inference_cannot_block_hard_stops(cause):
    live, cap, pad, guard = setup_live()
    entered, unblock = threading.Event(), threading.Event()
    def predict(frame, previous):
        entered.set()
        unblock.wait(2)
        return outputs()
    options = run_options(guard)
    if cause == "keypress":
        options["stop_requested"] = entered.is_set
    if cause == "focus_lost":
        options["focused"] = lambda: not entered.is_set()
    started = time.perf_counter()
    try:
        result = h.run(live, predict, MemoryJournal(), **options)
        assert result["stop_reason"] == cause
        assert time.perf_counter() - started < .7
        assert pad.reports[-1][1] == NEUTRAL
    finally:
        unblock.set()


def test_stop_monitor_neutralizes_during_blocked_capture():
    live, cap, pad, guard = setup_live()
    live.send(lt=1.)
    entered, unblock = threading.Event(), threading.Event()
    def grab():
        entered.set()
        unblock.wait(2)
        return [True]
    cap.grab = grab
    journal = MemoryJournal()
    options = run_options(guard)
    options["duration"] = .06
    thread = threading.Thread(target=h.run, args=(live, lambda f, p: outputs(), journal), kwargs=options)
    thread.start()
    try:
        assert entered.wait(.5)
        deadline = time.perf_counter() + .4
        while not live._dead and time.perf_counter() < deadline:
            time.sleep(.005)
        assert live._dead and pad.reports[-1][1] == NEUTRAL
        time.sleep(.1)  # Delayed capture return is not part of the supervised denominator.
    finally:
        unblock.set()
        thread.join(1)
    assert not thread.is_alive()
    report = journal.documents["result.json"]
    assert report["scorecard"]["supervised_seconds"] < .12
    assert report["loop_returned"] - report["stopped"] >= .09


def test_expired_prediction_is_not_sent_and_exception_closes():
    for broken in (False, True):
        live, cap, pad, guard = setup_live()
        def predict(frame, previous):
            if broken:
                raise RuntimeError("synthetic inference failure")
            time.sleep(.03)
            return outputs()
        result = h.run(live, predict, MemoryJournal(), **run_options(guard, max_prediction_age=.01))
        assert result["stop_reason"] == ("error" if broken else "prediction_expired")
        assert not any(s != NEUTRAL for _, s in pad.reports)
        assert pad.reports[-1][1] == NEUTRAL


def test_disk_failure_after_send_closes_pad_and_marks_error():
    live, cap, pad, guard = setup_live()
    class FailingJournal(MemoryJournal):
        def event(self, **value):
            if value["kind"] == "send":
                raise OSError("synthetic disk full")
            super().event(**value)
    journal = FailingJournal()
    result = h.run(live, lambda f, p: outputs(), journal, **run_options(guard))
    assert result["stop_reason"] == "error" and "disk full" in result["error"]
    assert any(s["lt"] for _, s in pad.reports)
    assert pad.reports[-1][1] == NEUTRAL and journal.closed


def test_first_history_is_unknown_then_successful_history_and_requests_at_most_30hz():
    live, cap, pad, guard = setup_live()
    journal = MemoryJournal()
    histories = []
    def predict(frame, previous):
        histories.append(previous)
        return outputs()
    h.run(live, predict, journal, **run_options(guard))
    assert histories[0] is None
    requests = [e for e in journal.events if e["kind"] == "inference"]
    assert len(requests) >= 2
    assert all(b["observation_t"] - a["observation_t"] >= executor.STEP_S for a, b in zip(requests, requests[1:]))
    assert histories[1]["held"][vocab.INDEX["web_cluster"]] == 1


def test_camera_uses_median_saturation_and_pitch_sign():
    actions, cameras = outputs()
    for axis in cameras:
        axis[vocab.ZERO_CLASS] = 0.
        axis[-1] = 1.
    decision = h.decode(actions, cameras, None, vocab.live_mask([50] * vocab.N), (.5,) * vocab.N, Cal())
    assert (decision.yaw, decision.pitch) == executor.max_step_degrees(Cal())
    assert decision.pad["rx"] == 1 and decision.pad["ry"] == -1


def test_scorecard_deduplicates_feed_and_keeps_unknown_separate():
    score = h.Scorecard()
    assert score.report(60)["ko_feed_appearances"] is None
    for value in (True, True, None, False, True, True, None, True, False, True):
        score.observe_feed(value)
    decision = h.decode(*outputs(), None, vocab.live_mask([50] * vocab.N), (.5,) * vocab.N, Cal())
    score.sent(decision)
    score.interval({**NEUTRAL, "rx": 1.}, 2., Cal())
    report = score.report(60)
    assert report["ko_feed_appearances"] == 2
    assert report["feed_unknown_frames"] == 2
    assert report["commanded_presses_per_minute"]["web_cluster"] == 1
    assert report["command_idle_seconds"] == 58
    assert report["commanded_camera_abs_degrees"]["yaw"] == 830


@pytest.mark.parametrize("kind", ["legacy", "I", "H", "W"])
def test_cpu_checkpoint_reload_and_step(kind, tmp_path):
    torch = pytest.importorskip("torch")
    np = pytest.importorskip("numpy")
    from policy.range_bc import cm3, cm3_train, model, train
    torch.set_num_threads(1)
    if kind == "legacy":
        original = model.Policy(model.Config(frames=False, hidden=8, history_embed=4, embed=4, hud_embed=4))
        raw = train.checkpoint_bytes(original, {})
    else:
        original = cm3.Policy(cm3.Config(arm=kind))
        raw = cm3_train.checkpoint_bytes(original, purpose="fit")
    path = tmp_path / "checkpoint.pt"
    path.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    restored, meta = h.load_checkpoint(path, digest)
    assert not restored.training and next(restored.parameters()).device.type == "cpu"
    assert all(torch.equal(t, restored.state_dict()[n]) for n, t in original.state_dict().items())
    views = (np.zeros((144, 256, 3), np.uint8), np.zeros((128, 128, 3), np.uint8), np.zeros((80, 200, 3), np.uint8))
    class FakeBackbone:
        def __call__(self, pixels):
            assert pixels.shape == (1, 3, 224, 224)
            return torch.zeros(1, cm3.FEATURE_DIM)
    predictor = h.Predictor(restored, lambda f: views, cooldowns="normal",
                            backbone=FakeBackbone() if kind in ("H", "W") else None)
    acts, cameras = predictor(None, None)
    assert len(acts) == 3 and len(acts[0]) == vocab.N
    assert len(cameras) == 2 and abs(sum(cameras[0]) - 1) < 1e-5
    assert predictor.regime == 0
    with pytest.raises(ValueError, match="hash mismatch"):
        h.load_checkpoint(path, "0" * 64)


def test_smoke_cm3_refused(tmp_path):
    pytest.importorskip("torch")
    from policy.range_bc import cm3, cm3_train
    raw = cm3_train.checkpoint_bytes(cm3.Policy(cm3.Config("I")), purpose="smoke")
    path = tmp_path / "smoke.pt"
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="smoke checkpoint"):
        h.load_checkpoint(path, hashlib.sha256(raw).hexdigest())


def test_ffmpeg_preprocessing_is_byte_identical_to_training_cache(tmp_path):
    np = pytest.importorskip("numpy")
    cv2 = pytest.importorskip("cv2")
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg unavailable")
    from policy.range_bc import cache
    # Native synthetic colour/geometry texture, never an evidence or corpus image.
    frame = np.random.default_rng(7).integers(0, 256, (720, 1280, 3), dtype=np.uint8)
    source = tmp_path / "frame.png"
    assert cv2.imwrite(str(source), frame)
    sinks = [[], [], []]
    cache._decode(source, [0], [v.append for v in sinks], "ffmpeg")
    actual = h.CachePreprocessor()(frame)
    assert [v.tobytes() for v in actual] == [v[0] for v in sinks]


def test_native_retention_is_lossless_and_refuses_overwrite(tmp_path):
    np = pytest.importorskip("numpy")
    cv2 = pytest.importorskip("cv2")
    output = tmp_path / "run"
    journal = h.Journal(output, {"format": "synthetic"})
    frame = np.random.default_rng(3).integers(0, 256, (64, 96, 3), dtype=np.uint8)
    journal.frame(frame, 1., "guard")
    journal.close()
    event = json.loads((output / "frames.jsonl").read_text())
    assert event["shape"] == [64, 96, 3]
    assert np.array_equal(cv2.imread(str(output / event["path"])), frame)
    assert h.sha256(output / event["path"]) == event["sha256"]
    with pytest.raises(FileExistsError):
        h.Journal(output, {})


@pytest.mark.parametrize("device,preprocessor", [("cpu", "subprocess"), ("cpu", "inprocess"),
                                                ("cpu", "compact-bgr"), ("cuda", "compact-bgr")])
def test_cli_prepare_has_no_live_object(tmp_path, monkeypatch, device, preprocessor):
    torch = pytest.importorskip("torch")
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    if preprocessor != "subprocess":
        pytest.importorskip("av")
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg unavailable")
    from policy.range_bc import model, train
    from scripts import run_range_bc_live as cli
    monkeypatch.setattr(cli, "Live", lambda **kw: pytest.fail("prepare opened a pad"))
    raw = train.checkpoint_bytes(model.Policy(model.Config(frames=False, hud=False)), {"regimes": ["normal"]})
    checkpoint = tmp_path / "checkpoint.pt"
    checkpoint.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    support = tmp_path / "support.json"
    support.write_text(json.dumps(dict(checkpoint_sha256=digest, press=[50] * vocab.N,
                                      swing_mode=vocab.PAD_SWING_MODE, live_mask=list(vocab.live_mask([50] * vocab.N)))))
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps(dict(binding_profile=h.PROFILE, swing_mode=vocab.PAD_SWING_MODE,
                                       cooldowns="normal", patch="synthetic")))
    out = tmp_path / "prepared"
    assert cli.main(["--checkpoint", str(checkpoint), "--checkpoint-sha256", digest,
                     "--support-json", str(support), "--settings-json", str(settings), "--camera-disabled",
                     "--output", str(out), "--threshold", ".3", "--device", device,
                     "--preprocessor", preprocessor]) == 0
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["checkpoint_sha256"] == digest
    assert manifest["thresholds"]["web_cluster"] == .3
    assert manifest["device"] == device and manifest["preprocessor"] == preprocessor
    assert manifest["code"]["files"]["agent/live_range_bc.py"] == h.sha256(Path(h.__file__))
    assert json.loads((out / "result.json").read_text())["pad_opened"] is False


def test_bounded_writer_drops_without_blocking_or_reusing_capture_buffer(tmp_path):
    np = pytest.importorskip("numpy")
    entered, unblock = threading.Event(), threading.Event()
    retained = []
    class SlowJournal(h.Journal):
        def _save_frame(self, index, frame, captured, role):
            entered.set()
            unblock.wait(2.)
            retained.append(frame.copy())
            super()._save_frame(index, frame, captured, role)
    journal = SlowJournal(tmp_path / "run", {}, queue_size=1)
    frame = np.zeros((32, 32, 3), np.uint8)
    try:
        assert journal.frame(frame, 0., "policy")
        assert entered.wait(.5)
        assert journal.frame(frame, 1., "send-proof")
        assert not journal.frame(frame, 2., "policy")
        frame[:] = 255
    finally:
        unblock.set()
        stats = journal.finish_frames()
        journal.close()
    assert stats["queue_capacity"] == 1 and stats["dropped_frames"] == 1
    assert stats["dropped_by_role"] == {"policy": 1}
    assert stats["drain_complete"] and stats["accepted_not_written"] == 0
    assert len(retained) == 2 and not any(x.any() for x in retained)


def test_control_sends_and_stops_while_png_writer_is_blocked(tmp_path):
    np = pytest.importorskip("numpy")
    live, cap, pad, _ = setup_live()
    frame = np.zeros((32, 32, 3), np.uint8)
    cap.grab = lambda: frame
    live._in_range = lambda f: True
    live.fresh()
    entered, unblock = threading.Event(), threading.Event()
    class SlowJournal(h.Journal):
        def _save_frame(self, *args):
            entered.set()
            unblock.wait(2.)
            super()._save_frame(*args)
    journal = SlowJournal(tmp_path / "run", {}, queue_size=1)
    options = run_options(lambda f: True)
    options["duration"] = .2
    thread = threading.Thread(target=h.run, args=(live, lambda f, p: outputs(), journal), kwargs=options)
    thread.start()
    try:
        assert entered.wait(.5)
        deadline = time.perf_counter() + .8
        while not live._dead and time.perf_counter() < deadline:
            time.sleep(.005)
        assert live._dead and pad.reports[-1][1] == NEUTRAL
        assert any(s["lt"] for _, s in pad.reports), "control waited for the PNG writer"
    finally:
        unblock.set()
        thread.join(2)
    assert not thread.is_alive()
    report = json.loads((journal.output / "result.json").read_text())
    assert report["frame_retention"]["dropped_frames"] > 0
    assert report["scorecard"]["sent_prediction_age_seconds"]["count"] > 0


def test_writer_failure_and_guard_throttle_are_reported(tmp_path):
    np = pytest.importorskip("numpy")
    journal = h.Journal(tmp_path / "run", {})
    failed = threading.Event()
    def fail(*args):
        failed.set()
        raise OSError("synthetic encoder disk failure")
    journal._save_frame = fail
    frame = np.zeros((8, 8, 3), np.uint8)
    journal.frame(frame, 0., "guard")
    assert failed.wait(.5)
    stats = journal.finish_frames()
    journal.close()
    assert "disk failure" in stats["writer_error"]
    assert not stats["drain_complete"] and stats["accepted_not_written"] == 1
    journal = h.Journal(tmp_path / "throttle", {})
    try:
        assert journal.frame(frame, 0., "guard")
        assert not journal.frame(frame, .5, "guard")
        assert journal.throttled_guards == 1
    finally:
        journal.close()


def test_settle_default_and_excluded_interval(monkeypatch):
    from scripts import run_range_bc_live as cli
    calls = []
    ticks = iter((10., 13.4))
    fake_live = object()
    monkeypatch.setattr(cli, "Live", lambda **kw: calls.append(kw) or fake_live)
    live, excluded = cli.attach_live(None, None, clock=lambda: next(ticks))
    assert live is fake_live and calls[0]["settle_s"] == 3.
    assert excluded == {"reason": "pad_enumeration_and_neutral_settle", "started": 10., "stopped": 13.4,
                        "requested_settle_seconds": 3., "commands_sent": False}
    with pytest.raises(ValueError, match="settling"):
        cli.attach_live(None, None, settle_seconds=0)
    actual, cap, pad, guard = setup_live()
    result = h.run(actual, lambda f, p: outputs(), MemoryJournal(),
                   **run_options(guard), excluded_intervals=[excluded])
    assert result["excluded_intervals"] == [excluded]
    assert result["scorecard"]["supervised_seconds"] < .5


@pytest.mark.parametrize("kind,hud,regimes,cooldowns,allowed", [
    ("legacy", False, ["normal"], "normal", True),
    ("legacy", False, ["normal"], "off", False),
    ("legacy", False, ["normal", "no_ability_cooldown"], "off", True),
    ("legacy", False, [], "normal", False),
    ("legacy", True, ["normal"], "normal", False),
    ("cm3", False, [], "off", False),
    ("cm3", False, [], "normal", True),
])
def test_out_of_distribution_inputs_refused(kind, hud, regimes, cooldowns, allowed):
    metadata = {"format": "range-bc-cm3-checkpoint-v1" if kind == "cm3" else "rivals-range-bc-v2",
                "config": {"hud": hud, "regime_bit": True}, "meta": {"regimes": regimes}}
    if allowed:
        assert h.validate_distribution(metadata, cooldowns)["pad_hud_input"] is False
    else:
        with pytest.raises(ValueError):
            h.validate_distribution(metadata, cooldowns)


def test_gap_distribution_duty_and_gap_retrigger_counts():
    score = h.Scorecard()
    decision = h.decode(*outputs(), None, vocab.live_mask([50] * vocab.N), (.5,) * vocab.N, None)
    score.interval(NEUTRAL, .2, None)
    score.interval(decision.pad, .1, None)
    score.interval(NEUTRAL, .3, None)
    score.interval(decision.pad, .1, None)
    score.interval(NEUTRAL, .3, None)
    retriggers = [int(n == "web_cluster") for n in vocab.NAMES]
    score.sent(decision, prediction_age=.05)
    score.sent(decision, retriggers=retriggers, prediction_age=.08)
    result = score.report(1.)
    assert result["commanded_seconds"] == pytest.approx(.2)
    assert result["command_duty_cycle"] == pytest.approx(.2)
    assert result["neutral_gap_seconds"]["count"] == 3
    assert result["neutral_gap_seconds"]["total"] == pytest.approx(.8)
    assert result["gap_retriggered_presses"]["web_cluster"] == 1
    assert result["presses_excluding_gap_retriggers"]["web_cluster"] == 1
    assert result["sent_prediction_age_seconds"]["max"] == .08


def test_loop_classifies_latency_retriggers_separately():
    live, cap, pad, guard = setup_live()
    journal = MemoryJournal()
    options = run_options(guard)
    options["duration"] = .3
    def slow_held(frame, previous):
        time.sleep(.045)  # Exceeds the 1/30 second lease on every step.
        return outputs()
    result = h.run(live, slow_held, journal, **options)
    score = result["scorecard"]
    assert score["commanded_presses"]["web_cluster"] >= 2
    assert score["gap_retriggered_presses"]["web_cluster"] == score["commanded_presses"]["web_cluster"] - 1
    assert score["presses_excluding_gap_retriggers"]["web_cluster"] == 1
    assert score["commanded_seconds"] + score["neutral_gap_seconds"]["total"] == pytest.approx(score["supervised_seconds"])


def test_review_receipt_must_match_all_loaded_and_running_files(tmp_path, monkeypatch):
    from scripts import run_range_bc_live as cli
    for name in cli.REVIEWED_FILES:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((cli.ROOT / name).read_bytes())
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    receipt = {"format": cli.REVIEW_FORMAT, "files": dict(cli.LOADED_HASHES)}
    path = tmp_path / "review.json"
    path.write_text(json.dumps(receipt))
    assert cli.verify_review_receipt(path)["files"] == cli.LOADED_HASHES
    victim = tmp_path / cli.REVIEWED_FILES[0]
    victim.write_bytes(victim.read_bytes() + b"\n# changed after import\n")
    with pytest.raises(ValueError, match="stale review"):
        cli.verify_review_receipt(path)
    # Even an updated receipt cannot cover code that differs from this process's import snapshot.
    receipt["files"][cli.REVIEWED_FILES[0]] = h.sha256(victim)
    path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="loaded source differs"):
        cli.verify_review_receipt(path)
    receipt["files"].pop(cli.REVIEWED_FILES[-1])
    path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="all required"):
        cli.verify_review_receipt(path)


def test_cli_defaults_remain_cpu_and_original_preprocessor():
    from scripts import run_range_bc_live as cli
    args = cli.parser().parse_args(["--checkpoint", "unused", "--checkpoint-sha256", "unused",
                                   "--support-json", "unused", "--settings-json", "unused", "--output", "unused"])
    assert args.device == "cpu" and args.preprocessor == "subprocess"


def test_v1_review_cannot_authorize_new_inference_dependency(tmp_path):
    from scripts import run_range_bc_live as cli
    path = tmp_path / "review.json"
    path.write_text(json.dumps({"format": "range-bc-live-review-v1", "files": dict(cli.LOADED_HASHES)}))
    with pytest.raises(ValueError, match="unsupported live review"):
        cli.verify_review_receipt(path)
    assert "policy/range_bc/live_inference.py" in cli.REVIEWED_FILES


def test_cuda_request_never_silently_falls_back_to_cpu(monkeypatch):
    torch = pytest.importorskip("torch")
    from policy.range_bc.live_inference import DevicePredictor
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    model = SimpleNamespace(config=SimpleNamespace(arm="I"))
    with pytest.raises(RuntimeError, match="no silent fallback"):
        DevicePredictor(model, None, cooldowns="normal", device="cuda")
