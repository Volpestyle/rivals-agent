"""Opt-in collection joins: real Loop/Controller/log, synthetic frames and devices."""
import json
from types import SimpleNamespace

import pytest

from agent import loop as runtime
from tests.test_loop import BOT, F, Frames, FakePad, RunLog, jpeg, readers, timeline
from tests.test_range_skill_loop import EventBrain
from tests.test_range_cast_probe import native_entry
from tests.test_range_skill_loop import live_cli


def collection(tmp_path, *, mode="range-skill", board=True, feed=None, writer=jpeg):
    clock = SimpleNamespace(t=0.)
    class Source(Frames):
        def now(self):
            return clock.t

        def next(self):
            item = super().next()
            if item is not None:
                clock.t = item[1]
            return item
    class Pad(FakePad):
        def scoreboard(self, hold_s):
            self.board_capture_interval = (clock.t + .1, clock.t + .2)
            clock.t += .3
            return super().scoreboard(hold_s)

        def send_guarded(self, pad, **bounds):
            assert clock.t < bounds["not_after"] <= bounds["release_at"]
            self.send(pad)
    source = Source([(F(dets=[BOT]), 0.)] + [(f, t + 10) for f, t in timeline(1.2, dets=[BOT])])
    pad = Pad(board=F(board=True) if board else None)
    p = readers()
    p.scoreboard = lambda f: {"open": True, "kos": 0}
    brain = EventBrain("start") if mode == "range-skill" else runtime.scripted.decide
    out = tmp_path / "collection"
    log = RunLog(out, save_fps=0, imwrite=writer)
    try:
        run = runtime.Loop(source, pad, p, brain, brain_name=mode, max_s=1,
                           collect_episode=True, candidate_feed=feed, log=log)
    except BaseException:
        log.close({"ticks": 0}, [])
        raise
    return SimpleNamespace(run=run, pad=pad, source=source, clock=clock, out=out, brain=brain)


@pytest.mark.parametrize("mode", ["range-skill", "scripted"])
def test_baseline_then_new_acquisition_starts_actual_phase_and_history(tmp_path, mode):
    h = collection(tmp_path, mode=mode)
    result = h.run.run()
    assert result["stop"] == "max_time"
    evidence = result["episode_collection"]
    assert evidence["status"] == "phase_started"
    assert evidence["first_phase"]["t"] == h.run.t0 == 10.
    assert evidence["readiness_accepted"] is None
    baseline = result["scoreboards"][0]
    assert baseline["file"] == "scoreboard-baseline.png"
    assert baseline["capture_interval"] == [.1, .2]
    assert baseline["captured_t"] < h.run.t0
    assert h.pad.history[0][0] == "release"
    assert next(k for k, _ in h.pad.history if k != "release") == "scoreboard"
    rows = [json.loads(s) for s in (h.out / "frames.jsonl").read_text().splitlines()]
    states = [r["state"] for r in rows if "state" in r]
    assert states and min(s["t"] for s in states) == 10.
    assert all(s["t"] >= 10 for s in states)
    assert h.pad.state == runtime.NEUTRAL
    assert result["scoreboards"][-1]["file"] == "scoreboard-end.png"
    assert (h.out / evidence["first_phase"]["file"]).exists()
    if mode == "range-skill":
        assert result["decision_schedule"]["origin_t"] == 10.
        assert all(r["range_skill_trace"]["resources"]["observed_t"] >= 10
                   for r in rows if r.get("range_skill_trace", {}).get("resources"))


def test_missing_baseline_retains_refusal_and_never_calls_brain(tmp_path):
    h = collection(tmp_path, board=False)
    result = h.run.run()
    assert result["stop"] == "collection_baseline_refused"
    assert result["decisions"] == 0 and h.brain.n == 0
    assert not any(k == "send" for k, _ in h.pad.history)
    assert len(result["scoreboards"]) == 1
    assert result["episode_collection"]["first_phase"] is None
    assert (h.out / "meta.json").exists() and h.run.log.f.closed


@pytest.mark.parametrize("fault", ["unknown_kos", "negative_kos", "bool_kos", "closed", "interval", "stale_frame",
                                   "no_frame", "range", "idle", "deadline"])
def test_baseline_and_first_phase_refusals_have_no_decisions_or_offense(tmp_path, fault):
    h = collection(tmp_path)
    if fault in {"unknown_kos", "negative_kos", "bool_kos", "closed"}:
        h.run.p.scoreboard = lambda f: {"open": fault != "closed",
                                      "kos": {"unknown_kos": None, "negative_kos": -1, "bool_kos": True}.get(fault, 0)}
    elif fault == "interval":
        original = h.pad.scoreboard
        def board(hold):
            result = original(hold)
            h.pad.board_capture_interval = None
            return result
        h.pad.scoreboard = board
    elif fault == "stale_frame":
        h.source.items[1] = (F(), .2)  # baseline grab end, not a new acquisition
    elif fault == "no_frame":
        h.source.items = h.source.items[:1]
    elif fault in {"range", "idle"}:
        h.source.items[1] = (F(ok=fault != "range", idle=fault == "idle"), 10.)
    elif fault == "deadline":
        h.run.scope_not_after = 10.
    result = h.run.run()
    assert result["episode_collection"]["status"] == "refused"
    assert result["decisions"] == h.brain.n == 0 and h.run.t0 is None
    assert not any(k == "send" for k, _ in h.pad.history)
    assert h.pad.state == runtime.NEUTRAL and h.run.log.f.closed


@pytest.mark.parametrize("which", ["scoreboard-baseline", "episode-first-phase"])
@pytest.mark.parametrize("failure", ["false", "raise", "slow"])
def test_evidence_save_failure_or_delay_cannot_start_offense(tmp_path, which, failure):
    def writer(path, frame):
        if path.stem == which:
            if failure == "false":
                return False
            if failure == "raise":
                raise OSError("injected evidence writer failure")
            h.clock.t += 1.
        jpeg(path, frame)
    h = collection(tmp_path, writer=writer)
    if failure != "slow":
        with pytest.raises(OSError):
            h.run.run()
    else:
        result = h.run.run()
        if which == "episode-first-phase":
            assert result["stop"] == "collection_phase_frame_not_fresh"
        else:
            # Baseline-save latency is before a NEW acquisition; not retimed.
            assert result["episode_collection"]["first_phase"]["t"] == 10.
            return
    assert h.brain.n == 0 and not any(k == "send" for k, _ in h.pad.history)
    assert h.run.log.f.closed and h.pad.state == runtime.NEUTRAL
    meta = json.loads((h.out / "meta.json").read_text())
    assert meta["episode_collection"]["status"] == "refused"
    assert meta["scoreboards"][0]["capture_interval"] == [.1, .2]


@pytest.mark.parametrize("value", [True, None])
def test_feed_requires_explicit_no_feed_start(tmp_path, value):
    h = collection(tmp_path, feed=lambda f: value)
    result = h.run.run()
    assert result["stop"] == "collection_start_feed_not_absent"
    assert result["episode_collection"]["first_phase"]["feed_present"] is value
    assert h.brain.n == 0 and (h.out / "episode-first-phase.png").exists()


@pytest.mark.parametrize("mode", ["range-skill", "scripted"])
def test_candidate_feed_releases_before_save_then_terminal_board_without_ko_credit(tmp_path, mode):
    def writer(path, frame):
        if path.stem == "episode-candidate-feed":
            assert h.pad.state == runtime.NEUTRAL
        jpeg(path, frame)
    h = collection(tmp_path, mode=mode, feed=lambda f: getattr(f, "feed", False), writer=writer)
    h.source.items[20][0].feed = True
    result = h.run.run()
    evidence = result["episode_collection"]
    assert result["stop"] == "candidate_feed"
    assert evidence["candidate_feed"]["t"] == h.source.items[20][1]
    assert evidence["designated_completion"] is None and evidence["readiness_accepted"] is None
    assert evidence["candidate_feed"]["designated_completion"] is None
    assert result["scoreboards"][-1]["file"] == "scoreboard-end.png"
    assert result["scoreboards"][-1]["captured_t"] > evidence["candidate_feed"]["t"]
    releases = [e for e in result["executor_events"] if e["reason"] == "candidate_feed"]
    assert releases and all(e["release_returned"] for e in releases)


def test_candidate_save_exception_preserved_despite_release_log_failure(tmp_path):
    def writer(path, frame):
        if path.stem == "episode-candidate-feed":
            assert h.pad.state == runtime.NEUTRAL
            raise OSError("candidate image failure")
        jpeg(path, frame)
    h = collection(tmp_path, feed=lambda f: getattr(f, "feed", False), writer=writer)
    h.source.items[20][0].feed = True
    write = h.run.log.write
    def failed_log(row, *args):
        if row.get("reason") == "candidate_feed":
            raise RuntimeError("release log failure")
        return write(row, *args)
    h.run.log.write = failed_log
    with pytest.raises(OSError, match="candidate image failure"):
        h.run.run()
    assert h.pad.state == runtime.NEUTRAL and h.run.log.f.closed
    assert any("release log failure" in e for e in h.run.errors)
    assert len(h.run.boards) == 1  # no terminal board after an unexpected exception


@pytest.fixture
def joined(live_cli, monkeypatch):
    """Actual main/start_pose/LiveIO/Live/Controller/log; only model loader is stubbed."""
    h = live_cli
    h.argv.remove("--no-scoreboard")
    h.argv.append("--collect-episode")
    h.brain.request = "start"
    original = runtime.default_perception
    def perception():
        p = original()
        p.scoreboard = lambda f: {"open": True, "kos": 0}
        return p
    monkeypatch.setattr(runtime, "default_perception", perception)
    return h


def mode_args(h, mode):
    if mode == "range-skill":
        return h.argv
    return ["--live", "--brain", "scripted", "--collect-episode", "--game-pid", "123",
            "--cooldowns", "normal", "--max-s", "1", "--save-fps", "0", "--run", "focus-test"]


@pytest.mark.parametrize("mode", ["range-skill", "scripted"])
def test_actual_joined_main_same_device_board_then_phase_with_original_clocks(joined, mode):
    h = joined
    assert runtime.main(mode_args(h, mode)) == 0
    assert len(h.lives) == 1 and h.lives[0]._dead and h.device.neutral()
    meta = json.loads((h.out / "meta.json").read_text())
    evidence = meta["episode_collection"]
    assert evidence["status"] == "phase_started"
    baseline = meta["scoreboards"][0]
    assert baseline["file"] == "scoreboard-baseline.png"
    assert baseline["capture_interval"][1] == baseline["captured_t"] < evidence["first_phase"]["t"]
    scope = meta["start"]["live_scope"]
    assert scope["loop_perf_origin"] == h.origin
    assert scope["combined_max_s"] == 15 and scope["startup_max_s"] == 14
    assert scope["not_after_perf"] == scope["loop_perf_origin"] + scope["not_after_t"]
    first_t = evidence["first_phase"]["t"]
    before = [(b, a) for t, (b, a) in h.reports if t < h.origin + first_t]
    assert any("BACK" in b for b, _ in before)
    assert all(b <= {"BACK"} and a["lt"] == a["rt"] == 0 and a["l"] == (0., 0.) for b, a in before)
    records = [json.loads(s) for s in (h.out / "frames.jsonl").read_text().splitlines()]
    assert all(r["state"]["t"] >= first_t for r in records if "state" in r)
    assert any(a["lt"] or a["rt"] or b & {"X", "RB"} for _, (b, a) in h.reports)
    assert meta["scoreboards"][-1]["file"] == "scoreboard-end.png"
    assert meta["executor_events"][-1]["release_returned"]


@pytest.mark.parametrize("mode", ["range-skill", "scripted"])
@pytest.mark.parametrize("fault", ["unfocused", "preload", "initialization", "attached", "board_focus", "expiry", "post_start"])
def test_actual_joined_focus_and_session_refusals_never_send_offense(joined, mode, fault):
    h = joined
    h.fault = fault
    if fault == "unfocused":
        h.focus = False
    if fault in {"unfocused", "preload"}:
        with pytest.raises(SystemExit):
            runtime.main(mode_args(h, mode))
        assert not h.lives
    elif fault == "initialization":
        with pytest.raises(runtime.RangeLost):
            runtime.main(mode_args(h, mode))
    elif fault == "attached":
        assert runtime.main(mode_args(h, mode)) == 1
        assert (h.out / "start-steps.jsonl").exists()
    else:
        runtime.main(mode_args(h, mode))
    assert all(not (b & {"X", "RB", "LB"}) and a["lt"] == a["rt"] == 0 for b, a in h.device.reports)
    if h.lives:
        assert h.device.neutral() and all(live._dead for live in h.lives)


@pytest.mark.parametrize("extra", [["--stop-on-feed"], ["--collect-episode", "--no-scoreboard"],
                                   ["--collect-episode", "--scoreboard-every", "1"],
                                   ["--collect-episode", "--max-s", "21"]])
def test_cli_collection_contract_refuses_before_readers_or_hardware(monkeypatch, extra):
    monkeypatch.setattr(runtime, "default_perception", lambda: pytest.fail("opened readers"))
    with pytest.raises(SystemExit):
        runtime.main(["--live", "--brain", "scripted", "--cooldowns", "normal", *extra])


@pytest.mark.parametrize("mode", ["scripted", "range-skill"])
def test_actual_post_phase_focus_loss_releases_and_no_later_offense(joined, monkeypatch, mode):
    h = joined
    log_factory = runtime.RunLog
    def log(*args, **kwargs):
        result = log_factory(*args, **kwargs)
        save = result.save
        def saved(name, frame, **options):
            output = save(name, frame, **options)
            if name == "episode-first-phase":
                h.focus_cutoff = h.t + .4
            return output
        result.save = saved
        return result
    monkeypatch.setattr(runtime, "RunLog", log)
    focused_factory = runtime.foreground_pid_guard
    def focused(pid):
        original = focused_factory(pid)
        return lambda: original() and h.t < getattr(h, "focus_cutoff", float("inf"))
    monkeypatch.setattr(runtime, "foreground_pid_guard", focused)
    runtime.main(mode_args(h, mode))
    meta = json.loads((h.out / "meta.json").read_text())
    assert meta["stop"] == "range_lost" and meta["decisions"] > 0
    assert all(not b and a["lt"] == a["rt"] == 0 and a["l"] == (0., 0.) and a["r"] == (0., 0.)
               for t, (b, a) in h.reports if t > h.focus_cutoff)
    assert h.device.neutral() and len(meta["scoreboards"]) == 1


@pytest.mark.parametrize("mode", ["scripted", "range-skill"])
def test_actual_optional_feed_hook_is_only_candidate_then_real_terminal_board(joined, monkeypatch, mode):
    h = joined
    calls = []
    def reader(frame):
        calls.append(h.t)
        return h.t > calls[0] + .4
    monkeypatch.setattr(runtime, "_killfeed_reader", lambda: reader)
    runtime.main([*mode_args(h, mode), "--stop-on-feed"])
    meta = json.loads((h.out / "meta.json").read_text())
    assert meta["stop"] == "candidate_feed"
    evidence = meta["episode_collection"]
    assert evidence["first_phase"]["feed_present"] is False
    assert evidence["candidate_feed"]["designated_completion"] is None
    assert evidence["candidate_feed"]["t"] > evidence["first_phase"]["t"]
    assert meta["scoreboards"][-1]["file"] == "scoreboard-end.png"
    assert h.device.neutral() and len(h.lives) == 1


@pytest.mark.parametrize("mode", ["scripted", "range-skill"])
def test_terminal_board_refusal_is_retained_without_deadline_extension(joined, monkeypatch, mode):
    h = joined
    original = runtime.LiveIO.scoreboard
    calls = []
    def board(io, hold):
        calls.append(h.t)
        if len(calls) == 2:
            h.t += 100.  # existing Live session proof must refuse BACK
        return original(io, hold)
    monkeypatch.setattr(runtime.LiveIO, "scoreboard", board)
    runtime.main(mode_args(h, mode))
    meta = json.loads((h.out / "meta.json").read_text())
    assert meta["stop"] == "max_time" and len(calls) == 2
    assert meta["scoreboards"][-1]["file"] is None
    assert meta["scoreboards"][-1]["skipped"] == "range_lost"
    assert meta["start"]["live_scope"]["combined_max_s"] == 15
    assert all(not b and a["lt"] == a["rt"] == 0 for t, (b, a) in h.reports if t > calls[1])
    assert h.device.neutral()


@pytest.mark.parametrize("mode", ["scripted", "range-skill"])
def test_actual_unreadable_native_baseline_is_saved_and_aborts(joined, monkeypatch, mode):
    h = joined
    original = runtime.default_perception
    def perception():
        p = original()
        p.scoreboard = lambda f: {"open": True, "kos": None}
        return p
    monkeypatch.setattr(runtime, "default_perception", perception)
    assert runtime.main(mode_args(h, mode)) == 1
    meta = json.loads((h.out / "meta.json").read_text())
    assert meta["stop"] == "collection_baseline_refused" and meta["decisions"] == 0
    assert meta["scoreboards"][0]["parsed"]["kos"] is None
    assert (h.out / meta["scoreboards"][0]["file"]).exists()
    assert meta["episode_collection"]["first_phase"] is None
    assert h.device.neutral()
    assert all(not (b & {"X", "RB", "LB"}) and a["lt"] == a["rt"] == 0 for b, a in h.device.reports)


@pytest.mark.parametrize("mode", ["scripted", "range-skill"])
def test_collection_range_loss_is_terminal_even_if_next_frame_recovers(tmp_path, mode):
    h = collection(tmp_path, mode=mode)
    h.source.items[20][0].ok = False
    result = h.run.run()
    assert result["stop"] == "range_lost" and h.run.last_t == h.source.items[20][1]
    assert h.source.i == 21 and h.pad.state == runtime.NEUTRAL
    assert len(result["scoreboards"]) == 1


@pytest.mark.parametrize("seconds,combined", [(10, 24), (None, 34)])
def test_scripted_collection_explicit_and_default_budget_stays_14_plus_phase(joined, monkeypatch, seconds, combined):
    h = joined
    args = mode_args(h, "scripted")
    index = args.index("--max-s")
    if seconds is None:
        del args[index:index + 2]
    else:
        args[index + 1] = str(seconds)
    # Refuse the board after constructing the genuine caller, to inspect the
    # fixed deadline without running another long synthetic gameplay loop.
    original = runtime.default_perception
    def perception():
        p = original()
        p.scoreboard = lambda f: {"open": True, "kos": None}
        return p
    monkeypatch.setattr(runtime, "default_perception", perception)
    runtime.main(args)
    meta = json.loads((h.out / "meta.json").read_text())
    assert meta["start"]["live_scope"]["combined_max_s"] == combined
    assert meta["start"]["live_scope"]["phase_max_s"] == (seconds or 20)
    assert meta["decisions"] == 0 and h.device.neutral()


def test_first_phase_save_cost_does_not_reset_fallback_execution_clock(tmp_path, monkeypatch):
    def writer(path, frame):
        if path.stem == "episode-first-phase":
            h.clock.t += .1
        jpeg(path, frame)
    h = collection(tmp_path, writer=writer)
    h.source.items = h.source.items[:2]
    h.run.execution_clock = None  # Exercise the existing exact elapsed-work converter.
    monkeypatch.setattr(runtime, "time", SimpleNamespace(perf_counter=lambda: h.clock.t))
    h.run.run()
    rows = [json.loads(s) for s in (h.out / "frames.jsonl").read_text().splitlines()]
    step = next(r for r in rows if r.get("range_skill_trace", {}).get("resources"))
    assert step["range_skill_trace"]["observation_t"] == 10.
    assert step["range_skill_trace"]["resources"]["observed_t"] == 10.
    assert step["range_skill_trace"]["execution_t"] == pytest.approx(10.1)


@pytest.mark.parametrize("mode", ["scripted", "range-skill"])
def test_actual_actuator_refuses_offensive_delivery_delayed_past_phase(joined, monkeypatch, mode):
    h = joined
    original = runtime.LiveIO.send_guarded
    delayed = []
    def send(io, pad, **bounds):
        if not delayed and (pad["lt"] or pad["rt"] or pad["buttons"]):
            delayed.append(bounds.copy())
            h.t += 2.
        return original(io, pad, **bounds)
    monkeypatch.setattr(runtime.LiveIO, "send_guarded", send)
    runtime.main(mode_args(h, mode))
    assert delayed
    assert all(a["lt"] == a["rt"] == 0 and not b & {"X", "RB", "LB"} for b, a in h.device.reports)
    meta = json.loads((h.out / "meta.json").read_text())
    phase_end = meta["episode_collection"]["first_phase"]["t"] + 1.
    assert delayed[0]["not_after"] <= phase_end
    assert h.device.neutral()
