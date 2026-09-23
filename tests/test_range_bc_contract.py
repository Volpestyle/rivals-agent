"""The intake -> fit contract, end to end (fit code review K2; lead decision: intake owns the writer, the fit lane owns
this test). Intake's importer dataset -> `agent.human_intake.write_steps` -> `policy.range_bc.steps.load`, built from
intake's own test helpers (`tests/human_intake_fixtures.py`). Intake derives the binding table (with Mouse 5 as a
second melee id), swing mode, settings hash, patch and accel_on from the reviewed provenance. Stdlib only."""
import json

import pytest

from agent import human_intake as hi
from policy.range_bc import steps, vocab
from tests.human_intake_fixtures import BASE, MS, build_dataset, session_payload, steps_payload

STEP_NS = 33_333_333
CALIBRATION = {"kind": "slow_turn_constant", "yaw_deg_per_count": .0330738, "pitch_deg_per_count": .0330738,
               "pitch": {"kind": "derived_equal_sensitivity"}, "source": "calibration take 2026-09-23"}


def _segments(data, split_at_ms=2000):
    end = data["metadata"]["end_ns"]
    seg = lambda sid, a, b, s: dict(segment_id=sid, start_ns=a, end_ns=b, reviewed_gameplay=True,
                                    imitation_suitability=s, suitability_reason="r", evidence="e")
    return [seg("a", BASE, BASE + split_at_ms * MS, "accepted"), seg("b", BASE + split_at_ms * MS, end, "rejected")]


def _write(tmp_path, data, segments, name, **kw):
    out = tmp_path / f"{name}.jsonl"
    args = dict(sitting="sitting-1", calibration=CALIBRATION, denylist=steps.load_denylist(), step_ns=STEP_NS,
                actions=vocab.NAMES)
    args.update(kw)
    hi.write_steps(build_dataset(data, segments), out, **args)
    return out


def test_intakes_writer_output_loads_in_the_fit(tmp_path):
    data = steps_payload(tmp_path)
    s = steps.load(_write(tmp_path, data, _segments(data), "plain"), denylist=steps.load_denylist())
    h = s.header
    assert s.session_id == h["session_group"] == "s1" and h["actions"] == list(vocab.NAMES)
    assert h["bindings"] == vocab.DEFAULT_BINDINGS                  # melee on V and Mouse 5, goh_targeting on X1
    assert h["accel_on"] is True and h["swing_mode"] == vocab.PAD_SWING_MODE
    assert h["calibration"]["pitch"]["kind"] == "derived_equal_sensitivity"
    # James's C (team-up) is an action, not an unsupported control; W's repeated make is not a second press
    team, fwd = vocab.INDEX["team_up"], vocab.INDEX["move_forward"]
    assert sum(r["press"][team] for r in s.rows) == 1 and sum(r["press"][fwd] for r in s.rows) == 1
    assert all("key:46:0" not in r["unsupported"] and "mouse:4" not in r["unsupported"] for r in s.rows)
    assert {r["suitability"] for r in s.rows} == {"accepted", "rejected"}
    t = steps.target(s.rows[0], s.calibration)
    assert t["yaw"] is not None and t["pitch"] is not None                   # derived pitch gain: usable


def test_a_capture_gap_ends_the_run_and_the_recording_still_loads(tmp_path):
    data = session_payload(tmp_path, esc_at_ms=2900)
    for p in data["packets"][100:]:
        p["composition_ns"] += 100 * MS               # a 110 ms capture gap after frame 99
    data["metadata"]["end_ns"] += 100 * MS
    seg = [dict(segment_id="a", start_ns=BASE, end_ns=data["metadata"]["end_ns"], reviewed_gameplay=True,
                imitation_suitability="accepted", suitability_reason="r", evidence="e")]
    s = steps.load(_write(tmp_path, data, seg, "gap"), denylist=steps.load_denylist())
    assert len({r["run"] for r in s.rows}) == 2
    assert all(r["anchor_ns"] - r["frame"]["composition_ns"] <= 2 * s.header["frame_period_ns"] for r in s.rows)


def test_the_fit_refuses_a_sealed_recording_and_a_pending_yaw_gain(tmp_path):
    data = steps_payload(tmp_path)
    path = _write(tmp_path, data, _segments(data), "sealed")
    lines = path.read_text(encoding="utf-8").splitlines()
    header = json.loads(lines[0])
    header["media_sha256"] = steps.load_denylist()["sessions"][0]["media_sha256"]
    sealed = tmp_path / "renamed.jsonl"
    sealed.write_text("\n".join([json.dumps(header)] + lines[1:]) + "\n", encoding="utf-8")
    with pytest.raises(steps.StepError, match="sealed by the denylist"):
        steps.load(sealed, denylist=steps.load_denylist())
    pending = _write(tmp_path, data, _segments(data), "pending",
                     calibration={"kind": "slow_turn_constant", "yaw_deg_per_count": None,
                                  "pitch_deg_per_count": None, "source": "pending"})
    with pytest.raises(steps.StepError, match="calibration"):
        steps.load(pending)                            # no fit before the 360-degree yaw take exists


def test_intakes_default_action_list_is_the_fit_vocabulary():
    # intake appended team_up and goh_targeting on 2026-09-23 (each was a strict xfail here until it did)
    assert list(hi.FIT_ACTIONS) == list(vocab.NAMES)
