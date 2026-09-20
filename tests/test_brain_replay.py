"""Replay over a synthetic run: the timeline hits every mode and the metrics see the dropouts."""
import random

from agent import replay
from agent.state import State


def _synth(tmp_path):
    path = tmp_path / "run.jsonl"
    replay.main([str(path), "--synth", "--json"])
    return path


def test_synthetic_run_walks_every_mode_and_the_tracer_branch(tmp_path):
    states = replay.load(_synth(tmp_path))
    assert {s.frame for s in states} == {(1280, 720)}  # the size L1 records and perception processes
    rows = replay.run(states)
    segs = replay.timeline(rows)
    m = replay.metrics(rows, segs)

    labels = [lab for lab, _, _ in segs]
    kinds = [lab.split(":")[0] for lab in labels]
    assert {"search", "swingto", "engage", "webstrike", "pull", "combo", "disengage", "idle"} <= set(kinds)
    # tag unknown -> engage; tag seen -> web strike; untagged and out of ammo -> pull; untagged and ready -> burst
    first_fight = kinds[kinds.index("engage"):]
    assert first_fight[:5] == ["engage", "webstrike", "engage", "pull", "combo"]
    assert {lab for lab in labels if lab.startswith("combo")} == {"combo:burst"}
    assert m["segments_by_intent"]["disengage"] == 1  # one retreat, no flapping
    assert m["unknown_frac"]["hp"] > 0 and m["unknown_frac"]["detections"] > 0 and m["unknown_frac"]["on_target"] > 0
    assert m["decisions_per_s"] == 10.0 and m["max_gap_s"] == 0.1


def test_replay_decimates_to_the_brain_rate(tmp_path):
    states = replay.load(_synth(tmp_path))  # 10 Hz on disk
    assert abs(2 * len(replay.run(states, hz=5)) - len(states)) <= 2


def _stream(n, gap):
    """n States spaced by gap() seconds; only t matters to decimation."""
    t, out = 0.0, []
    for _ in range(n):
        out.append(State(t=t, frame=(1280, 720)))
        t += gap()
    return out


def test_jittered_10_fps_recording_is_not_decimated_at_10_hz():
    rng = random.Random(1)
    states = _stream(1000, lambda: rng.uniform(0.092, 0.108))  # L1's spacing: near 0.1 s, never exactly
    kept = len(replay.run(states, hz=10))
    old = 0  # the rule this replaced: s.t - last >= 1/hz - 1e-9
    last = None
    for s in states:
        if last is None or s.t - last >= 1 / 10 - 1e-9:
            old += 1
            last = s.t
    assert kept == len(states)
    assert old < 0.75 * len(states)  # it dropped a third of a real 10 fps run


def test_decimation_still_thins_faster_streams():
    fast = _stream(600, lambda: 1 / 60)
    assert abs(len(replay.run(fast, hz=10)) - 100) <= 2  # one in six
    close = _stream(200, lambda: 0.05)
    assert abs(len(replay.run(close, hz=10)) - 100) <= 2  # every other one
