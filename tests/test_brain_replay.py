"""Replay over a synthetic run: the timeline hits every mode and the metrics see the dropouts."""
from agent import replay


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
