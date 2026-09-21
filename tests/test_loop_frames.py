"""agent/loop.py on real frames: the tracked evidence stills and the recorded tagrun0. Needs the perception group
(`uv run --group perception pytest tests/test_loop_frames.py`); tagrun0 is under gitignored data/ and skips where absent."""
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from agent import brain as scripted
from agent.controller import NEUTRAL
from agent.demos import Demos
from agent.loop import ALLOWED, FakePad, Loop, RunLog, RunSource, default_perception, main
from perception.scoreboard import read_scoreboard

ROOT = Path(__file__).resolve().parent.parent
L1 = ROOT / "docs" / "evidence" / "l1"
BOARD = ROOT / "docs" / "evidence" / "l4" / "scoreboard-back-native.jpg"
TAGRUN0 = ROOT / "data" / "l1" / "tagrun0"
needs_tagrun0 = pytest.mark.skipif(not (TAGRUN0 / "frames.jsonl").is_file(), reason="data/l1/tagrun0 is not on this machine")


class Frames:
    def __init__(self, items):
        self.items, self.i = list(items), 0

    def next(self):
        if self.i >= len(self.items):
            return None
        self.i += 1
        return self.items[self.i - 1]


def stream(*spans):
    """[(frame, t)] at 60 Hz from (frame, seconds) spans."""
    out, t = [], 0.0
    for frame, secs in spans:
        for _ in range(round(secs * 60)):
            out.append((frame, t))
            t += 1 / 60
    return out


def read(path):
    frame = cv2.imread(str(path))
    assert frame is not None, path
    return frame


def run(items, **kw):
    pad = FakePad()
    kw.setdefault("warmup", False)
    loop = Loop(Frames(items), pad, default_perception(), scripted.decide, **kw)
    return loop, pad, loop.run()


def test_a_real_range_frame_runs_and_the_lobby_stops_it_with_the_pad_released():
    play, lobby = read(L1 / "dxcam-frame.jpg"), read(L1 / "dropped-to-lobby.jpg")
    loop, pad, out = run(stream((play, 1.0), (lobby, 1.0)))
    assert out["stop"] == "range_lost" and pad.state == NEUTRAL and len(loop.gaps) == 1
    assert loop.last_t - 1.0 < 0.3                                       # within the grace, on real frames
    assert all(k != "scoreboard" for k, _ in pad.history)


def test_nothing_is_sent_when_the_first_real_frame_is_the_lobby():
    loop, pad, out = run(stream((read(L1 / "dropped-to-lobby.jpg"), 1.0)))
    assert out["stop"] == "no_range_hud_at_start" and [k for k, _ in pad.history if k == "send"] == []


def test_the_idle_banner_on_a_real_frame_stops_the_run():
    play = read(L1 / "dxcam-frame.jpg")
    banner, k = play.copy(), play.shape[1] / 1280.0
    banner[int(30 * k):int(90 * k), int(100 * k):int(700 * k)] = (30, 30, 230)      # the red countdown banner, BGR
    loop, pad, out = run(stream((play, 0.5), (banner, 1.0)))
    assert out["stop"] == "idle_warning" and pad.state == NEUTRAL


def test_the_scoreboard_hides_the_hud_from_the_guard_and_is_read_only_at_native_size():
    board = read(BOARD)
    p = default_perception()
    assert not p.in_range(board)                                          # why the hold is confirmed before, never during
    native = read_scoreboard(board)
    small = read_scoreboard(cv2.resize(board, (1280, 720), interpolation=cv2.INTER_AREA))
    assert native["open"] is True and "too_small" not in native
    assert small.get("too_small") == 1280 and all(v is None for k, v in small.items() if k not in ("open", "too_small"))
    play = read(L1 / "dxcam-frame.jpg")
    pad = FakePad(board=board)
    out = Loop(Frames(stream((play, 0.5))), pad, p, scripted.decide, warmup=False).run()
    got = out["scoreboards"][0]
    assert got["size"] == [2560, 1440] and got["parsed"] == native        # the native frame reaches the reader, untouched


@needs_tagrun0
def test_a_recorded_run_goes_through_the_loop_and_its_log_loads_as_a_clip(tmp_path):
    log = RunLog(tmp_path / "replay", save_fps=10.0)
    loop = Loop(RunSource(TAGRUN0, limit=120), FakePad(board=read(BOARD)), default_perception(), scripted.decide, log=log,
                warmup=False)
    out = loop.run()
    assert out["stop"] == "source_end" and out["ticks"] == 120 and out["errors"] == [] and loop.pad.state == NEUTRAL
    sent = [p for k, p in loop.pad.history if k == "send"]
    assert len(sent) == 120 and all(set(p["buttons"]) <= ALLOWED for p in sent)
    assert set(out["intents"]) >= {"search"} and out["decisions"] == 120 and out["missed_decisions"] == 0
    assert out["scoreboards"][0]["parsed"]["open"] is True and (tmp_path / "replay" / "scoreboard-end.png").is_file()
    demos = Demos.load(tmp_path / "replay", fractions=(1.0, 0.0, 0.0))
    clip, = demos.clips.values()
    assert clip.header["inputs"] == "pad" and clip.resolution == [2560, 1440] and len(clip.inputs) == 120
    assert [i.pad["buttons"] for i in clip.inputs] == [list(p["buttons"]) for p in sent]
    samples = list(demos.samples("train", hindsight=True))
    assert samples and all(s.observation.frames[-1].t == pytest.approx(s.observation.t) for s in samples)
    rows = [json.loads(line) for line in (tmp_path / "replay" / "frames.jsonl").read_text().splitlines()]
    assert sum("state" in r for r in rows) == 120 and {r["source"] for r in rows} == {"scripted"}


@needs_tagrun0
def test_a_replay_is_deterministic_and_the_real_detector_and_hud_reach_the_brain():
    def go():
        loop = Loop(RunSource(TAGRUN0, limit=160), FakePad(), default_perception(), scripted.decide, warmup=False)
        return loop, loop.run()

    (a, out_a), (b, out_b) = go(), go()
    assert a.pad.history == b.pad.history and out_a["intents"] == out_b["intents"]
    assert any(n.startswith(("engage", "combo", "swing")) for n in out_a["intents"])     # frames ~75-160 hold a bot in the crop
    assert a.decider.latest.state.hp == 250 and a.decider.latest.state.frame == (2560, 1440)


@needs_tagrun0
def test_the_threaded_loop_runs_real_perception_without_holding_a_reflex_step():
    pad = FakePad()
    loop = Loop(RunSource(TAGRUN0, limit=60), pad, default_perception(), scripted.decide, warmup=False, threaded=True)
    out = loop.run()
    assert out["stop"] == "source_end" and out["ticks"] == 60 and out["errors"] == [] and pad.state == NEUTRAL
    assert out["decisions"] >= 1 and out["decisions"] + out["missed_decisions"] >= 1


@needs_tagrun0
def test_the_dry_run_prints_tick_times_and_the_intents_chosen(capsys):
    assert main(["--dry", str(TAGRUN0), "--limit", "40", "--no-scoreboard"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ticks"] == 40 and out["stop"] == "source_end" and set(out["tick_ms"]) == {"p50", "p95", "max"} and out["intents"]
    assert np.isfinite(out["aim_ms"]["p95"]) and out["brain"] == "scripted"


@needs_tagrun0
def test_see_gets_a_read_only_view_of_the_real_frame_and_cannot_write_into_the_finders_pixels():
    calls = []

    class Brain:
        def see(self, frame, t):
            calls.append((frame.flags.writeable, frame.shape, t))
            try:
                frame[0, 0, 0] = 255
            except ValueError:
                calls.append("write refused")

        def __call__(self, state, memory):
            from agent.intents import Idle
            return Idle()

    loop = Loop(RunSource(TAGRUN0, limit=12), FakePad(), default_perception(), Brain(), warmup=False)
    loop.run()
    seen = [c for c in calls if c != "write refused"]
    assert seen and all(w is False and shape == (1440, 2560, 3) for w, shape, _ in seen)
    assert calls.count("write refused") == len(seen)
