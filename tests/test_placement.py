"""agent/placement.py: the classifier on recorded finder output, and the planner on a simulated lane.

Stdlib only. The frame table (tests/fixtures/placement/frames.json) holds the finder boxes and range proof of 84 held
frames with an operator label each (labels: tests/fixtures/placement/labelled.json, hash-pinned in provenance.json).
tests/test_placement_frames.py re-derives the boxes from pixels where the images are present. The simulated lane
(agent/placement_sim.py) reproduces the two falls of galacta-pilot-20260923 and carries the review's perturbations:
differential box-height bias (F1), the lower-plaza view (F2) and camera pitch (F3).

IN-SAMPLE: the thresholds were set on these frames. These tests show consistency, not generalisation.
"""
import hashlib
import json
import math
from pathlib import Path

import pytest

from agent import placement as P
from agent import placement_sim as sim

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests/fixtures/placement"
FRAMES = json.loads((FIX / "frames.json").read_text(encoding="utf-8"))
IDS = [f"{r['set']}:{Path(r['path']).name}" for r in FRAMES]
CONSERVATIVE = {"galacta-setup-20260922/near-02.png": "left bot cut by the frame edge",
                "galacta-pilot-20260922-03-scripted/000007.jpg": "mid-combo, the tightest margin"}
PLAZA_X19 = [[1156.7, 715, 1244.1, 804.3], [1477.8, 715, 1569.0, 806.2]]       # review F2's adversarial pair


def by_name(name):
    return next(r for r in FRAMES if Path(r["path"]).name == name)


def classify(row, pitch_ref):
    return P.classify(tuple(row["size"]), row["boxes"], row["in_range"], pitch_ref)


# --- Provenance (review F6) ----------------------------------------------------------------------------------------

def test_labels_are_committed_and_pinned():
    prov = json.loads((FIX / "provenance.json").read_text(encoding="utf-8"))
    raw = (FIX / "labelled.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == prov["labelled_json_sha256"]
    assert hashlib.sha256((FIX / "frames.json").read_bytes()).hexdigest() == prov["frames_json_sha256"]
    assert all(r["label"] in ("PAIR", "NOT_PAIR", "LOST", "NEAR_ONE") for r in FRAMES)
    assert all(r["label_source"].startswith("operator") for r in FRAMES)
    assert "label or got" not in (FIX / "build_frames.py").read_text(encoding="utf-8")


# --- The classifier on real finder output --------------------------------------------------------------------------

@pytest.mark.parametrize("row", FRAMES, ids=IDS)
def test_recorded_frame_without_the_reference_pitch_never_yields_a_pose(row):
    got = classify(row, pitch_ref=False)
    assert got.pose is None                                      # frames of unknown pitch cannot move anything
    key = "/".join(Path(row["path"]).parts[-2:])
    if row["label"] == "PAIR":
        assert got.kind == ("LOST" if key in CONSERVATIVE else "UNLEVELLED"), (row["note"], got.reason)
    elif row["label"] == "NOT_PAIR":
        assert got.kind == "LOST", row["note"]
    else:
        assert got.kind == row["label"], row["note"]


@pytest.mark.parametrize("row", FRAMES, ids=IDS)
def test_recorded_frame_at_the_reference_pitch(row):
    got = classify(row, pitch_ref=True)
    if row["label"] == "NOT_PAIR":
        assert got.kind not in ("PAIR", "TWO"), row["note"]
    elif row["label"] == "PAIR":
        if got.kind in ("PAIR", "TWO"):
            assert P.on_lane(got.pose) and got.pose.feasible
        else:                                                    # the other pitch cluster fails the level check
            assert got.kind == "LOST"
    else:
        assert got.kind == row["label"]


def test_the_level_check_separates_the_pitch_clusters_and_the_plaza():
    at_ref = [classify(r, True).kind for r in FRAMES if r["label"] == "PAIR"]
    assert at_ref.count("PAIR") + at_ref.count("TWO") >= 30 and at_ref.count("LOST") >= 20


def test_the_x19_lower_plaza_pair_is_never_pair():
    for pitch_ref in (False, True):
        assert P.classify((2560, 1440), PLAZA_X19, True, pitch_ref).kind not in ("PAIR", "TWO")
    lo, hi = P.Box(*PLAZA_X19[0]), P.Box(*PLAZA_X19[1])
    assert P.level_residual(lo) > 150 and P.level_residual(hi) > 150


@pytest.mark.parametrize("dist", [10.0, 12.5, 15.0, 17.5, 20.0])
@pytest.mark.parametrize("lateral", [-2.0, 0.0, 2.0])
def test_lower_plaza_views_at_10_to_20_m_are_never_pair(dist, lateral):
    """Synthetic: the real lower-plaza frame's level offset (+214 px) at the review's 10-20 m; the real ones are due
    from the supervised look."""
    for heading in (-15.0, 0.0, 15.0):
        boxes = sim.render(lateral, -dist, heading, fallen=True)
        for pitch_ref in (False, True):
            assert P.classify((2560, 1440), boxes, True, pitch_ref).kind not in ("PAIR", "TWO")


def test_the_design_examples():
    far = classify(by_name("p0923-e2-pos2-a.jpg"), True)
    assert far.kind == "PAIR" and P.BINS["far"][0] <= far.h <= P.BINS["far"][1] and -27 < far.pose.y < -22
    mid = classify(by_name("galacta-0923-ready-e2.png"), True)
    assert mid.kind == "PAIR" and P.BINS["mid"][0] <= mid.h <= P.BINS["mid"][1] and P.on_lane(mid.pose)
    near = classify(by_name("p0923-cdcheck-d.jpg"), True)
    assert near.kind == "NEAR_ONE" and P.BINS["near"][0] <= near.h <= P.BINS["near"][1]
    assert classify(by_name("p0923-pos04-a.jpg"), True).kind == "LOST"


def test_decide_needs_two_of_three_frames():
    row = by_name("p0923-e2-pos2-a.jpg")
    pair, one = classify(row, True), classify(by_name("p0923-scene-03.png"), True)
    assert pair.kind == "PAIR" and one.kind == "LOST"
    assert P.decide([one, pair, one]).kind == "LOST"                 # one frame is not enough (review F6)
    assert P.decide([pair, one, pair]).kind == "PAIR"
    assert P.decide([pair, pair, P.View("NOT_IN_RANGE")]).kind == "NOT_IN_RANGE"


# --- The pose (review F1) ------------------------------------------------------------------------------------------

@pytest.mark.parametrize("x, y", [(4.0, -8.0), (4.4, -8.0), (3.0, -6.0), (3.5, -4.0), (-3.0, -6.0), (0.0, -10.0)])
@pytest.mark.parametrize("bias", [(1.15, 0.85), (1.25, 0.75), (0.85, 1.15), (0.75, 1.25), (1.0, 0.8)])
def test_a_differential_bias_never_hides_the_true_pose_from_the_safety_set(x, y, bias):
    """The review's failure: x 4.4 localised at -3.3. Now the frame is rejected, or its safety set contains a pose
    within 1 m of the truth, so every move is checked against the true one."""
    heading = math.degrees(math.atan2(-x, -y))
    boxes = sim.render(x, y, heading, height_bias=bias)
    view = P.classify((2560, 1440), boxes, True, True)
    if view.pose is None:
        return
    assert min(math.hypot(fx - x, fy - y) for fx, fy, _ in view.pose.feasible) <= 1.0


def test_the_side_is_never_asserted_wrongly_under_bias():
    for x in (2.5, 3.0, 3.5, 4.0):
        for y in (-3.0, -5.0, -8.0):
            for bias in ((1.25, 0.75), (1.15, 0.85)):
                heading = math.degrees(math.atan2(-x, -y))
                view = P.classify((2560, 1440), sim.render(x, y, heading, height_bias=bias), True, True)
                assert view.pose is None or view.pose.side in (None, 1), (x, y, bias, view.pose.side)


# --- The planner on the simulated lane -----------------------------------------------------------------------------

Lane, run = sim.Lane, sim.run
GRID = [(x, y) for x in (-3.0, -1.5, 0.0, 1.5, 3.0, 3.5, 4.0) for y in (-4.0, -8.0, -12.0, -16.0, -20.0)]


def assert_disciplined(actions):
    for act, view in actions:
        assert act.kind in ("PITCH_RESET", "TURN", "STRAFE", "WALK", "READY", "HAND_BACK")   # no jump
        if act.kind in ("WALK", "STRAFE"):
            assert abs(act.value) <= P.PULSE_S + 1e-9
            assert view.kind in ("PAIR", "TWO") and view.pose is not None                 # no move without a pose


@pytest.mark.parametrize("bias", [(1.0, 1.0), (1.15, 0.85), (1.25, 0.75), (0.85, 1.15), (0.75, 1.25), (1.0, 0.8),
                                  (0.8, 1.0), (0.9, 0.9), (1.1, 1.1)])
@pytest.mark.parametrize("bin_", ["mid", "far"])
def test_zero_falls_over_the_start_grid_under_differential_bias(bias, bin_):
    """Review F1's closed-loop grid: 35 starts x 3 headings, each bias. Required: 0 falls."""
    falls = []
    for x, y in GRID:
        for off in (0.0, 30.0, -40.0):
            lane = Lane(x, y, math.degrees(math.atan2(-x, -y)) + off, height_bias=bias, seed=2)
            actions, _ = run(lane, bin_)
            assert_disciplined(actions)
            if lane.fallen:
                falls.append((x, y, off))
    assert falls == []


def test_unbiased_grid_mostly_places():
    ready = 0
    for x, y in GRID:
        for off in (0.0, 30.0, -40.0):
            actions, _ = run(Lane(x, y, math.degrees(math.atan2(-x, -y)) + off), "mid")
            ready += actions[-1][0].kind == "READY"
    assert ready >= 70                                          # 77 of 105 when written; the rest hand back


def test_the_real_back_walk_falls_off_the_lane():
    lane = Lane(x=3.0, y=-2.2, heading_deg=-35.0)
    lane.walk(-2.5)
    assert lane.fallen


def test_the_real_walk_and_jump_falls_below():
    lane = Lane(x=3.6, y=-4.5, heading_deg=80.0)
    lane.walk(0.1)
    lane.jump()
    assert lane.fallen


def test_from_the_slot3_end_the_planner_never_falls():
    """Post-KO point blank, right of the designated bot. Under the review's worst-bias safety set the side cannot be
    tracked out of the drop zone, so it hands back (READY needs a measured bias bound; see placement.md)."""
    lane = Lane(x=3.0, y=-2.2, heading_deg=-35.0)
    actions, state = run(lane, "mid")
    assert not lane.fallen and actions[-1][0].kind in ("READY", "HAND_BACK"), state.log
    assert_disciplined(actions)
    first_move = next(a for a, _ in actions if a.kind in ("WALK", "STRAFE"))
    assert first_move.kind == "STRAFE" and first_move.value < 0     # away from the drop, not back along the ray


def test_after_a_fall_to_the_lower_plaza_the_planner_never_moves():
    for heading in (0.0, 30.0, 90.0, -120.0):
        lane = Lane(x=5.5, y=-12.0, heading_deg=heading)
        lane.fallen = True
        actions, state = run(lane, "mid")
        assert actions[-1][0].kind == "HAND_BACK", state.log
        assert all(a.kind in ("PITCH_RESET", "TURN", "HAND_BACK") for a, _ in actions)
        assert lane.moves == []


@pytest.mark.parametrize("bin_", ["far", "mid"])
def test_from_the_25_m_end(bin_):
    lane = Lane(x=1.5, y=-24.5, heading_deg=4.0)
    actions, state = run(lane, bin_)
    assert actions[-1][0].kind == "READY" and not lane.fallen, state.log
    lo, hi = P.BINS[bin_]
    assert lo <= actions[-1][1].h <= hi
    assert_disciplined(actions)


def test_a_flickering_finder_still_places():
    lane = Lane(x=-1.0, y=-15.0, heading_deg=-10.0, flicker=0.2, seed=7)
    actions, state = run(lane, "mid")
    assert actions[-1][0].kind == "READY" and not lane.fallen, state.log


# --- Pitch (review F3) ---------------------------------------------------------------------------------------------

def test_the_first_action_is_a_pitch_reset():
    actions, _ = run(Lane(0.0, -20.0, 0.0, pitch_px=-60.0), "mid")
    assert actions[0][0].kind == "PITCH_RESET" and actions[0][1].kind in ("UNLEVELLED", "LOST")


@pytest.mark.parametrize("pitch_px", [-160.0, -60.0, -40.0, 40.0, 60.0, 160.0])
def test_a_pitch_error_before_the_reset_is_harmless(pitch_px):
    """Uncorrected, the shifted lane pair is UNLEVELLED (never a pose); after the reset the placement proceeds."""
    lane = Lane(0.0, -20.0, 0.0, pitch_px=pitch_px)
    assert P.classify((2560, 1440), lane.boxes(), True, False).kind == "UNLEVELLED"
    actions, state = run(lane, "mid")
    assert actions[-1][0].kind == "READY" and not lane.fallen, state.log


@pytest.mark.parametrize("residual_px", [-30.0, 30.0])
def test_a_small_residual_pitch_after_the_reset_still_places(residual_px):
    actions, state = run(Lane(0.0, -20.0, 0.0, pitch_px=100.0, pitch_after_reset=residual_px), "mid")
    assert actions[-1][0].kind == "READY", state.log


@pytest.mark.parametrize("residual_px", [-150.0, -100.0, 0.0, 100.0])
def test_the_lower_plaza_stays_rejected_within_the_reset_tolerance(residual_px):
    """The review's -155 px case admitted the plaza pair; the reference pitch must hold within ~150 px."""
    lane = Lane(x=3.0, y=-12.0, heading_deg=-14.0, pitch_after_reset=residual_px)
    lane.fallen = True
    lane.pitch_reset()
    for _ in range(5):
        assert lane.view().kind not in ("PAIR", "TWO")


def test_a_pitch_that_never_levels_hands_back():
    lane = Lane(0.0, -20.0, 0.0, pitch_px=120.0, pitch_after_reset=120.0)   # the reset does not reach the reference
    actions, state = run(lane, "mid")
    assert actions[-1][0].kind == "HAND_BACK" and lane.moves == [], state.log


# --- Near placement (review F4) ------------------------------------------------------------------------------------

def test_near_is_refused_until_the_edge_is_measured():
    assert P.EDGE_X_M is None
    act, _ = P.plan(P.PlanState("near"), P.View("LOST"))
    assert act.kind == "HAND_BACK" and "edge" in act.reason


def test_near_with_a_measured_edge_uses_short_strafes_under_the_ceiling(monkeypatch):
    monkeypatch.setattr(P, "EDGE_X_M", 4.5)
    for x, y in ((1.5, -24.5), (0.0, -15.0), (-2.0, -12.0)):
        lane = Lane(x, y, math.degrees(math.atan2(-x, -y)))
        actions, state = run(lane, "near")
        assert not lane.fallen, state.log
        for act, view in actions:
            if act.kind == "STRAFE":
                assert abs(act.value) <= P.NEAR_STRAFE_S + 1e-9
            if act.kind in ("WALK", "STRAFE"):
                assert P.safe(view.pose, act, 4.5 - P.NEAR_EDGE_CLEARANCE_M)
        assert lane.x <= 4.5 - P.NEAR_EDGE_CLEARANCE_M + 0.2


# --- Budget (review F5) --------------------------------------------------------------------------------------------

def test_alternating_pair_and_lost_at_zero_dt_hands_back_within_max_steps():
    view = P.classify((2560, 1440), sim.render(0.0, -20.0, 25.0), True, True)      # heading off: answers TURN
    assert view.kind == "PAIR"
    state, steps = P.PlanState("mid"), 0
    for i in range(5000):
        act, state = P.plan(state, view if i % 2 == 0 else P.View("LOST"), dt=0.0)
        steps += 1
        if act.kind == "HAND_BACK":
            break
    assert act.kind == "HAND_BACK" and steps <= P.MAX_STEPS + 1


def test_moves_that_do_nothing_hand_back_within_the_budget():
    lane = Lane(x=0.5, y=-20.0, heading_deg=0.0, speed=0.0)
    actions, state = run(lane, "mid", steps=400)
    assert actions[-1][0].kind == "HAND_BACK", state.log
    assert len(actions) <= P.MAX_STEPS + 1


def test_not_in_range_hands_back_at_once():
    act, _ = P.plan(P.PlanState("mid"), P.View("NOT_IN_RANGE"))
    assert act.kind == "HAND_BACK"
