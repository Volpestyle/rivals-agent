"""The end-to-end range fit's stdlib pieces: vocabulary, step-table contract, windows, baselines, metrics, gates,
executor mapping, report, and (with ffmpeg on PATH) the frame cache. Torch pieces: test_range_bc_torch.py."""
import copy
import dataclasses
import json
import shutil

import pytest

from agent.controller import Cal, stick_for
from policy.range_bc import baselines, cache, executor, fixture, gates, metrics, report, steps, vocab

CAL = fixture.CALIBRATION


def write_session(tmp_path, name="a", **kw):
    header, rows = fixture.session(name, **kw)
    return fixture.write(tmp_path / f"{name}.jsonl", header, rows)


def rewrite(tmp_path, name, mutate, **kw):
    header, rows = fixture.session(name, **kw)
    mutate(header, rows)
    return fixture.write(tmp_path / f"{name}.jsonl", header, rows)


# ---- vocabulary ---------------------------------------------------------------------------------------------------------

def test_actions_are_semantic_and_the_pad_cannot_send_stick_clicks_y_x1_or_simple_swing():
    assert vocab.N == 15 and len(set(vocab.NAMES)) == 15
    assert vocab.NAMES[-3:] == ("team_up", "goh_targeting", "simple_swing")     # appended: earlier indices unchanged
    assert set(vocab.DEFAULT_BINDINGS) == set(vocab.NAMES) and vocab.DEFAULT_BINDINGS["goh_targeting"] == "mouse:4"
    assert vocab.DEFAULT_BINDINGS["simple_swing"] == "key:58:0"                 # Caps Lock's scan code
    for name in ("ultimate", "melee", "team_up", "goh_targeting", "simple_swing"):
        assert not vocab.PAD_SENDABLE[vocab.INDEX[name]]
    assert not vocab.live_mask([1000] * vocab.N)[vocab.INDEX["simple_swing"]]  # masked live whatever its count
    mask = vocab.live_mask([1000] * vocab.N)
    assert not mask[vocab.INDEX["ultimate"]] and not mask[vocab.INDEX["team_up"]] and mask[vocab.INDEX["spider_power"]]
    presses = [1000] * vocab.N
    presses[vocab.INDEX["amazing_combo"]] = 49
    assert not vocab.live_mask(presses)[vocab.INDEX["amazing_combo"]]


def test_camera_classes_round_trip_and_are_monotone():
    assert vocab.camera_class(0.) == vocab.ZERO_CLASS and vocab.camera_class(.01) == vocab.ZERO_CLASS
    for r in vocab.REPS:
        assert vocab.class_degrees(vocab.camera_class(r)) == r
        assert vocab.class_degrees(vocab.camera_class(-r)) == -r
    assert vocab.camera_class(500.) == vocab.CAMERA_CLASSES - 1 and vocab.camera_class(-500.) == 0
    classes = [vocab.camera_class(v / 100) for v in range(-6000, 6001)]
    assert classes == sorted(classes)


def test_median_class_is_the_distribution_median_not_the_argmax():
    probs = [0.] * vocab.CAMERA_CLASSES
    probs[5], probs[20], probs[25] = .4, .15, .45
    assert vocab.median_class(probs) == 20        # the argmax would be 25


# ---- the step-table contract --------------------------------------------------------------------------------------------

def test_fixture_satisfies_the_contract(tmp_path):
    s = steps.load(write_session(tmp_path))
    assert len(s.rows) == 210 and s.split == "train" and len(s.sha256) == 64 and s.calibration == CAL


SEALED_ID = "20260923T053616-779Z-33696-2"
SEALED_MEDIA = "ea49d523bddf86b97c4307aae99198a374e011a4ef1eb5df8d4b90de6b6053bf"


def test_the_real_denylist_is_read_by_intakes_reader_with_its_pin():
    deny = steps.load_denylist()                 # data/human/sealed-denylist.json, pinned
    assert [r["session_id"] for r in deny["sessions"]] == [SEALED_ID]
    assert deny["sessions"][0]["media_sha256"] == SEALED_MEDIA
    with pytest.raises(steps.StepError, match="pinned"):
        steps.load_denylist(steps.DENYLIST, "0" * 64)


def test_test_split_and_denylist_are_refused_before_any_row_is_read(tmp_path):
    deny = steps.load_denylist()
    header = fixture.header_for("sealed-x", split="test")
    path = tmp_path / "sealed.jsonl"
    path.write_text(json.dumps(header) + "\nthis is not json\n", encoding="utf-8")
    with pytest.raises(steps.StepError, match="sealed"):
        steps.load(path, denylist=deny)
    with pytest.raises(steps.StepError, match="sealed"):
        steps.load_cohort([path], splits=("train", "test"))
    # a train-labelled header naming the sealed id, or only its media hash: refused before any row
    for name, patch in (("by-id", {"session_id": SEALED_ID, "session_group": SEALED_ID}),
                        ("by-media", {"media_sha256": SEALED_MEDIA})):
        other = tmp_path / f"{name}.jsonl"
        other.write_text(json.dumps({**fixture.header_for("x"), **patch}) + "\nthis is not json\n", encoding="utf-8")
        with pytest.raises(steps.StepError, match="sealed by the denylist"):
            steps.load(other, denylist=deny)
    with pytest.raises(steps.StepError, match="named for a sealed session"):
        steps.load(tmp_path / f"{SEALED_ID}.jsonl", denylist=deny)     # refused by exact name before opening
    # exact match only: a substring of the sealed id is not a match
    near = tmp_path / "053616.jsonl"
    header, rows = fixture.session("053616")
    fixture.write(near, header, rows)
    assert steps.load(near, denylist=deny).session_id == "053616"


@pytest.mark.parametrize("mutate, message", [
    (lambda h, r: h.update(actions=list(reversed(h["actions"]))), "vocabulary"),
    (lambda h, r: h["bindings"].pop("melee"), "bind every action"),
    (lambda h, r: h["bindings"].update(melee="key:17:0"), "distinct"),
    (lambda h, r: h.update(calibration={"yaw_deg_per_count": 0, "pitch_deg_per_count": .01, "source": "x"}),
     "calibration"),
    (lambda h, r: h.update(session_group="sitting-1"), "one recording"),
    (lambda h, r: h.update(hud_layout="pad"), "mouse-and-keyboard"),
    (lambda h, r: h.update(injected_events=3), "injected"),
    (lambda h, r: h.update(device_scope="multi"), "device scope"),
    (lambda h, r: h.update(video_size=[2560, 1600]), "16:9"),
    (lambda h, r: h.pop("sitting"), "lacks"),
    (lambda h, r: h.update(media_sha256="abc"), "media_sha256"),
    (lambda h, r: h.update(swing_mode={"hold_to_swing": True}), "swing_mode"),
    (lambda h, r: h.update(swing_mode={"automatic_swing": "off", "hold_to_swing": True}), "swing_mode"),
    (lambda h, r: h.pop("accel_on"), "lacks"),
    (lambda h, r: h.update(accel_on="on"), "accel_on"),
    (lambda h, r: h["calibration"].update(kind="guess"), "calibration kind"),
    (lambda h, r: h["calibration"].update(kind="speed_curve"), "not implemented"),
    (lambda h, r: h["calibration"].pop("pitch"), "pitch.kind"),
    (lambda h, r: h["calibration"].update(pitch={"kind": "assumed"}), "pitch.kind"),
])
def test_header_violations_are_refused(tmp_path, mutate, message):
    with pytest.raises(steps.StepError, match=message):
        steps.load(rewrite(tmp_path, "bad", mutate))


def _repeat_counted_as_press(h, r):
    w = vocab.INDEX["move_forward"]
    row = next(x for x in r if x["held_start"][w] and x["held_end"][w] and x["held_known"][w])
    row["press"][w] += 1          # a repeated make of a held key counted as a press


def _stride(h, r):
    r[5]["anchor_ns"] += 1
    r[5]["frame"]["composition_ns"] += 1


def _reappear(h, r):
    for x in r[150:]:
        x["run"] = "run0"          # run0 again after run1


def _hold_break(h, r):
    w = vocab.INDEX["move_forward"]
    k = next(i for i in range(1, 100) if r[i]["held_start"][w] == 0 and r[i]["press"][w] == 0
             and r[i]["held_end"][w] == 0)
    r[k]["held_start"][w] = r[k]["held_end"][w] = 1     # continuous within the row, not with the row before


@pytest.mark.parametrize("mutate, message", [
    (_repeat_counted_as_press, "edges do not account"),
    (_stride, "anchor stride"),
    (_reappear, "reappears"),
    (_hold_break, "hold discontinuous"),
    (lambda h, r: r[3]["frame"].update(composition_ns=r[3]["anchor_ns"] - 3 * fixture.PERIOD_NS), "frame age"),
    (lambda h, r: r[3].update(relative_known=True, mouse_dx=None), "relative_known with null"),
    (lambda h, r: r[3].update(unsupported={"key:17:0": 1}), "unbound"),      # W is bound: not unsupported
    (lambda h, r: r[3].update(tag_source="untagged", tags=["near"]), "untagged"),
    (lambda h, r: r[3].pop("held_known"), "lacks"),
    (lambda h, r: r[3].update(hud=[1]), "hud"),
    (lambda h, r: r[3].update(i=7), "i is"),
])
def test_row_violations_are_refused(tmp_path, mutate, message):
    with pytest.raises(steps.StepError, match=message):
        steps.load(rewrite(tmp_path, "bad", mutate))


def test_unknown_holds_are_not_checked_for_edges_or_continuity(tmp_path):
    def mutate(h, r):
        w = vocab.INDEX["move_forward"]
        k = next(i for i, x in enumerate(r) if not x["held_known"][w])
        r[k]["press"][w] = 1                    # an edge the unknown start state cannot account for
    steps.load(rewrite(tmp_path, "u", mutate))


def test_cohort_refuses_duplicates_and_mixed_identity(tmp_path):
    a = write_session(tmp_path, "a")
    with pytest.raises(steps.StepError, match="twice"):
        steps.load_cohort([a, a])
    for key, value in (("settings_hash", "other"), ("calibration", {**CAL, "yaw_deg_per_count": .02}),
                       ("bindings", {**vocab.DEFAULT_BINDINGS, "melee": "key:48:0"}),
                       ("swing_mode", {"automatic_swing": False, "hold_to_swing": False})):
        b = rewrite(tmp_path, f"b-{key}", lambda h, r, key=key, value=value: h.update({key: value}))
        with pytest.raises(steps.StepError, match=key):
            steps.load_cohort([a, b])
    assert len(steps.load_cohort([a, write_session(tmp_path, "d", split="val")])) == 2
    same = rewrite(tmp_path, "e", lambda h, r: h.update(media_sha256=fixture.media_sha256("a")))
    with pytest.raises(steps.StepError, match="same recording media"):
        steps.load_cohort([a, same])


def test_the_live_mask_drops_web_swing_unless_the_swing_mode_is_the_pads():
    presses = [1000] * vocab.N
    swing = vocab.INDEX["web_swing"]
    assert vocab.live_mask(presses, dict(vocab.PAD_SWING_MODE))[swing]
    assert not vocab.live_mask(presses, {"automatic_swing": False, "hold_to_swing": False})[swing]
    assert not vocab.live_mask(presses, {"automatic_swing": None, "hold_to_swing": True})[swing]


# ---- runs, windows, records ---------------------------------------------------------------------------------------------

def test_runs_drop_rejected_segments_and_other_regimes(tmp_path):
    s = steps.load(write_session(tmp_path, runs=(100, 50, 40), reject_run=1, regime_every=3))
    assert steps.runs(s) == [(0, 100)]                                  # run1 rejected, run2 no-cooldown
    assert steps.runs(s, regimes=steps.REGIMES) == [(0, 100), (150, 190)]


def test_tiling_drops_short_runs_and_aligns_the_remainder():
    assert steps.tile(0, 47) is None
    assert steps.tile(0, 60) == [(0, 60)]
    assert steps.tile(0, 96) == [(0, 96)]
    assert steps.tile(10, 210) == [(10, 96), (58, 96), (106, 96), (114, 96)]


def test_windows_and_train_minutes_count_what_they_drop(tmp_path):
    s = steps.load(write_session(tmp_path, runs=(200, 30)))
    wins, dropped = steps.windows([s])
    assert dropped == {"dropped_runs": 1, "dropped_steps": 30}
    assert all(0 <= st and st + n <= 200 and a == 0 for _, st, n, a in wins)
    minutes = steps.train_minutes([s])
    assert minutes["total"] == pytest.approx(199 * fixture.STEP_NS / 60e9)     # run0's last step touches the gap


def test_loss_skips_burn_in_except_at_the_run_start():
    assert steps.loss_mask_start(0, 0) == 0
    assert steps.loss_mask_start(48, 0) == steps.BURN_IN


def test_step_records_are_causal(tmp_path):
    s = steps.load(write_session(tmp_path, runs=(100, 60)))
    recs = steps.step_records(s, 0, 100)
    assert recs[0]["prev"] is None and recs[1]["prev"] == steps.target(s.rows[0], CAL) and recs[1]["prev2"] is None
    assert recs[2]["prev2"] == steps.target(s.rows[0], CAL) and recs[0]["sitting"] == "sitting-1"
    inner = steps.step_records(s, 0, 100, start=50, stop=60)
    assert inner[0]["prev"] == steps.target(s.rows[49], CAL)            # a window start is not a run start
    for lag in (1, 2):
        lagged = steps.step_records(s, 0, 100, lag=lag)
        assert lagged[0]["target"] == steps.target(s.rows[lag], CAL)
        assert lagged[0]["prev"] == steps.target(s.rows[lag - 1], CAL)
        assert not lagged[-1]["valid"] and lagged[-1]["target"] is None
    assert not recs[-1]["valid"]                                         # the fixture's run end touches a gap


def test_targets_are_semantic_and_in_degrees():
    row = {"held_start": [0] * vocab.N, "held_end": [0] * vocab.N, "held_known": [True] * vocab.N,
           "press": [0] * vocab.N, "release": [0] * vocab.N, "relative_known": True, "mouse_dx": 5000,
           "mouse_dy": -20, "unsupported": {"key:56:0": 2}}
    e, lmb = vocab.INDEX["get_over_here"], vocab.INDEX["spider_power"]
    row["press"][e] = row["release"][e] = 1
    row["press"][lmb] = row["release"][lmb] = 2
    t = steps.target(row, CAL)
    assert t["press"][e] == t["release"][e] == 1 and t["held"][e] == 0 and not t["multi"][e]
    assert t["press"][lmb] == 1 and t["multi"][lmb] == 1
    assert t["yaw"] == pytest.approx(66.) and t["clamped"] and t["cy"] == vocab.CAMERA_CLASSES - 1
    assert t["pitch"] == pytest.approx(-.264) and t["cp"] == vocab.camera_class(-.264)
    assert t["unsupported"] == 2 and t["presses"] == 3


def test_prev_vector_layout():
    assert steps.prev_vector(None) == [0.] * steps.PREV_DIM
    t = {"held": [1] + [0] * (vocab.N - 1), "press": [0] * vocab.N, "release": [0] * vocab.N, "known": [True] * vocab.N,
         "camera_known": True, "cy": 0, "cp": vocab.CAMERA_CLASSES - 1}
    v = steps.prev_vector(t)
    assert v[0] == 1. and v[3 * vocab.N] == 1. and v[3 * vocab.N + 2 * vocab.CAMERA_CLASSES - 1] == 1. and v[-1] == 1.
    assert sum(v) == 4.


def test_train_statistics(tmp_path):
    s = steps.load(write_session(tmp_path, runs=(700, 400)))
    stats = steps.train_statistics([s])
    assert stats["steps"] > 0 and stats["press"][vocab.INDEX["ultimate"]] == 0
    assert not stats["live_mask"][vocab.INDEX["ultimate"]]
    assert all(stats["longest_hold"][vocab.INDEX[n]] > 0 for n in fixture.HOLDERS)
    lo, hi = stats["drift"]["yaw"]
    assert lo is not None and lo <= hi
    v = steps.load(write_session(tmp_path, "v", split="val"))
    with pytest.raises(steps.StepError, match="train split only"):
        steps.train_statistics([v])
    assert steps.pos_weight(0, 100) == 1. and steps.pos_weight(1, 100) == 20. and steps.pos_weight(25, 100) == 3.


# ---- baselines and metrics ----------------------------------------------------------------------------------------------

def oracle(rec):
    t = rec["target"]
    if t is None:
        return {"held": [0.] * vocab.N, "press": [0.] * vocab.N, "release": [0.] * vocab.N, "yaw": 0., "pitch": 0.}
    return {"held": [float(v) for v in t["held"]], "press": [float(v) for v in t["press"]],
            "release": [float(v) for v in t["release"]], "yaw": t["yaw"] or 0., "pitch": t["pitch"] or 0.}


def val_runs(tmp_path, name="v", seed=3, runs=(300, 200)):
    s = steps.load(write_session(tmp_path, name, split="val", runs=runs, seed=seed))
    return [steps.step_records(s, a, b) for a, b in steps.runs(s)]


def test_matching_windows():
    assert metrics.match_window([5, 10], [4, 6, 11]) == 2
    assert metrics.match_window([5], [7]) == 0
    assert metrics.match_window([1, 2, 3], [2]) == 1
    assert metrics.match_window([5], [6], early=1, late=0) == 0     # late: the edge was already in the input
    assert metrics.match_window([5], [4], early=1, late=0) == 1     # early is fine
    assert metrics.f1(0, 0, 0) is None and metrics.f1(1, 1, 0) == 2 / 3


def test_average_precision():
    assert metrics.average_precision([.9, .8, .1], [1, 0, 1]) == pytest.approx((1 + 2 / 3) / 2)
    assert metrics.average_precision([.1], [0]) is None


def test_oracle_is_perfect(tmp_path):
    m = metrics.evaluate(metrics.predict_runs(val_runs(tmp_path), oracle), **metrics.TEACHER)
    for name in ("spider_power", "web_cluster", "get_over_here", "jump"):
        a = m["actions"][name]
        assert a["press_f1"] == a["press_f1_tol"] == a["held_balanced_accuracy"] == 1.
    assert m["camera"]["yaw"]["mae_deg"] == 0 and m["macro_press_f1_tol"] == 1.
    assert m["camera"]["yaw"]["onset_sign_agreement"] == 1. and m["camera"]["yaw"]["onset_steps"] > 0
    assert 0 < m["unsupported_share"] < .2


def test_echo_is_credited_only_by_the_leaky_window(tmp_path):
    """F2: echoing the previous true edge maxes a symmetric +-1 window and scores ~0 on [t-1, t]."""
    runs = metrics.predict_runs(val_runs(tmp_path), baselines.echo)
    leaky = metrics.evaluate(runs, early=1, late=1)["macro_press_f1_tol"]
    fair = metrics.evaluate(runs, **metrics.TEACHER)["macro_press_f1_tol"]
    assert leaky > .95 and fair < .05


def test_baselines(tmp_path):
    runs = val_runs(tmp_path)
    p = metrics.evaluate(metrics.predict_runs(runs, baselines.persistence), **metrics.TEACHER)
    assert all(a["press_f1"] is None or a["press_f1"] == 0 for a in p["actions"].values())
    assert p["actions"]["move_forward"]["held_balanced_accuracy"] > .8        # persistence is strong on holds
    rec = runs[0][5]
    assert baselines.persistence(rec)["yaw"] == rec["prev"]["yaw"] and baselines.zero_motion(rec)["yaw"] == 0
    train = steps.load(write_session(tmp_path, runs=(800, 600)))
    stats = steps.train_statistics([train])
    prior = baselines.prior(stats)(rec)
    assert 0 < prior["press"][vocab.INDEX["spider_power"]] < .5 and prior["press"][vocab.INDEX["ultimate"]] == 0
    coef = baselines.fit_ar2([train])
    assert coef["yaw"][0] == pytest.approx(1.35, abs=.1) and coef["yaw"][1] == pytest.approx(-.42, abs=.1)
    ar = metrics.evaluate(metrics.predict_runs(runs, baselines.ar2(coef)), **metrics.TEACHER)
    assert ar["camera"]["yaw"]["mae_deg"] < p["camera"]["yaw"]["mae_deg"]      # the fixture's camera is AR(2)
    with pytest.raises(steps.StepError):
        baselines.fit_ar2([steps.load(write_session(tmp_path, "vv", split="val"))])


def test_stratification_by_tag_regime_sitting_and_resource(tmp_path):
    s = steps.load(write_session(tmp_path, "v", split="val", runs=(100, 100, 100), regime_every=3, hud=True))
    runs = [steps.step_records(s, a, b) for a, b in steps.runs(s, regimes=steps.REGIMES)]
    out = metrics.stratified(metrics.predict_runs(runs, oracle))
    assert set(out["by_tag"]) == {"near", "foot", "untagged"} and set(out["by_regime"]) == set(steps.REGIMES)
    assert set(out["by_sitting"]) == {"sitting-1"} and any(k.startswith("webs=") for k in out["by_resource"])
    assert out["by_tag"]["near"]["valid_steps"] + out["by_tag"]["untagged"]["valid_steps"] == out["all"]["valid_steps"]


def test_sanity_measures_stuck_holds_and_drift():
    rec = {"valid": True}
    held = [0.] * vocab.N
    held[vocab.INDEX["move_forward"]] = 1.
    run = [(rec, {"held": held, "press": [0.] * vocab.N, "release": [0.] * vocab.N, "yaw": 2., "pitch": 0.})] * 600
    s = metrics.sanity([run])
    assert s["longest_hold"]["move_forward"] == 600 and s["longest_hold"]["jump"] == 0
    assert s["drift"]["yaw"] == [2., 2.]


# ---- gates --------------------------------------------------------------------------------------------------------------

def gate_inputs(tmp_path):
    runs = val_runs(tmp_path)
    train = steps.load(write_session(tmp_path, runs=(800, 600)))
    stats = steps.train_statistics([train])
    coef = baselines.fit_ar2([train])
    ev = lambda f, w=metrics.TEACHER: metrics.evaluate(metrics.predict_runs(runs, f), **w)
    good_tf, good_sf = ev(oracle), ev(oracle, metrics.SELF)
    tf = {"model": {s: good_tf for s in gates.SEEDS}, "history_only": {s: ev(baselines.persistence)
                                                                       for s in gates.SEEDS},
          "persistence": ev(baselines.persistence), "zero_motion": ev(baselines.zero_motion),
          "prior": ev(baselines.prior(stats)), "echo": ev(baselines.echo), "ar2": ev(baselines.ar2(coef))}
    sf = {"model": {s: good_sf for s in gates.SEEDS},
          "history_only": {s: ev(baselines.persistence, metrics.SELF) for s in gates.SEEDS}}
    sane = {s: metrics.sanity(metrics.predict_runs(runs, oracle)) for s in gates.SEEDS}
    stats["live_mask"] = list(vocab.live_mask([1000] * vocab.N))
    human = metrics.sanity(metrics.predict_runs(runs, metrics.truth))
    return tf, sf, sane, stats, human


def test_an_oracle_passes_every_gate(tmp_path):
    tf, sf, sane, stats, human = gate_inputs(tmp_path)
    v = gates.evaluate(tf, sf, sane, stats, human)
    assert v["pilot_worthy"], {k: v[k]["pass"] for k in ("G0", "G1", "G2", "G3", "G4", "G5", "G6")}
    assert v["headline_self_fed_macro_press_f1"] == 1.
    json.dumps(v)


def test_no_frame_gain_fails_g1_and_one_bad_seed_fails_g6(tmp_path):
    tf, sf, sane, stats, human = gate_inputs(tmp_path)
    same = {**tf, "history_only": dict(tf["model"])}
    v = gates.evaluate(same, sf, sane, stats, human)
    assert not v["G1"]["pass"] and not v["pilot_worthy"]
    bad = {**sf, "model": {**sf["model"], 2: tf["persistence"]}}
    v = gates.evaluate(tf, bad, sane, stats, human)
    assert v["G2"]["pass"] and not v["G6"]["pass"] and not v["pilot_worthy"]


def test_a_leaky_metric_invalidates_the_gates(tmp_path):
    tf, sf, sane, stats, human = gate_inputs(tmp_path)
    leaky = copy.deepcopy(tf["echo"])
    leaky["macro_press_f1_tol"] = .99
    v = gates.evaluate({**tf, "echo": leaky}, sf, sane, stats, human)
    assert not v["G0"]["pass"] and not v["pilot_worthy"]


def test_onset_sign_must_beat_the_references(tmp_path):
    tf, sf, sane, stats, human = gate_inputs(tmp_path)
    weak = copy.deepcopy(tf["model"][0])
    weak["camera"]["yaw"]["onset_sign_agreement"] = tf["persistence"]["camera"]["yaw"]["onset_sign_agreement"]
    assert not gates.g3(weak, tf["persistence"], tf["zero_motion"], tf["ar2"], tf["history_only"][0])["pass"]


def test_spam_stuck_and_drift_fail_g5_and_missing_seeds_are_incomplete(tmp_path):
    tf, sf, sane, stats, human = gate_inputs(tmp_path)
    ref = gates.human_reference(stats, human)
    assert gates.g5(sf["model"][0], sane[0], ref)["pass"]
    spam = copy.deepcopy(sf["model"][0])
    spam["actions"]["get_over_here"]["pred_press_rate"] = 3 * spam["actions"]["get_over_here"]["human_press_rate"]
    assert not gates.g5(spam, sane[0], ref)["pass"]
    stuck = copy.deepcopy(sane[0])
    stuck["longest_hold"]["move_forward"] = ref["longest_hold"][vocab.INDEX["move_forward"]] + 1
    assert not gates.g5(sf["model"][0], stuck, ref)["pass"]
    drift = copy.deepcopy(sane[0])
    drift["drift"]["yaw"] = [0., 99.]
    assert not gates.g5(sf["model"][0], drift, ref)["pass"]
    v = gates.evaluate({**tf, "model": {0: tf["model"][0]}}, sf, sane, stats, human)
    assert not v["complete"] and not v["pilot_worthy"] and v["missing_seeds"] == [1, 2]


# ---- executor mapping ---------------------------------------------------------------------------------------------------

def test_decode_step_is_consistent_and_masked():
    live = list(vocab.live_mask([1000] * vocab.N))
    p0 = [0.] * vocab.N
    e, ult, fwd = vocab.INDEX["get_over_here"], vocab.INDEX["ultimate"], vocab.INDEX["move_forward"]
    press, release = list(p0), list(p0)
    press[e] = release[e] = .9
    held = list(p0)
    held[fwd] = held[ult] = .9
    h, p, r = executor.decode_step(held, press, release, [0] * vocab.N, live)
    assert p[e] == r[e] == 1 and h[e] == 0                  # a tap
    assert h[fwd] == 1 and p[fwd] == 1 and r[fwd] == 0      # a hold starts with its press
    assert h[ult] == p[ult] == 0                            # never sent: the pad cannot click sticks
    h2, p2, r2 = executor.decode_step(p0, p0, p0, h, live)
    assert r2[fwd] == 1 and p2[fwd] == 0


def test_pad_state_maps_actions_and_degrees_through_the_measured_maps():
    cal = Cal()
    held = [0] * vocab.N
    for n in ("move_forward", "move_right", "web_swing", "spider_power", "web_cluster"):
        held[vocab.INDEX[n]] = 1
    press = [0] * vocab.N
    press[vocab.INDEX["jump"]] = 1                          # a tap is held for the whole step
    pad = executor.pad_state(held, press, 172. / 30, -43. / 30, cal=cal)
    assert pad["lx"] == pytest.approx(2 ** -.5) and pad["ly"] == pytest.approx(2 ** -.5)
    assert pad["buttons"] == ("A", "LB") and pad["rt"] == 1. and pad["lt"] == 1.
    assert pad["rx"] == pytest.approx(.45) and pad["ry"] == pytest.approx(.5)    # pitch -1.43 deg (up) -> ry +0.5
    assert set(pad) == set(executor.NEUTRAL)


def test_saturation_tracking_error_and_feasibility():
    my, mp = executor.max_step_degrees()
    assert my == pytest.approx(415 / 30) and mp == pytest.approx(99 / 30)
    assert executor.saturate(100., -100.) == (pytest.approx(my), pytest.approx(-mp))
    req = [(1., .5), (20., 0.), (-2., 0.)]
    got = [(1.2, .5), (my, None), (-2., 0.)]
    t = executor.tracking_error(req, got)
    assert t["yaw"]["steps"] == 3 and t["yaw"]["saturated_share"] == pytest.approx(1 / 3)
    assert t["yaw"]["unsaturated_mae"] == pytest.approx(.1) and t["pitch"]["steps"] == 2
    f = executor.human_feasibility([1., 20., -30.], [0., 5.])
    assert f["yaw_over_cap"] == pytest.approx(2 / 3) and f["pitch_over_cap"] == .5


def test_tracker_integrates_measured_error_only():
    tr = executor.Tracker(k=2.)
    assert tr.update((1., 0.), (.5, None)) == (1., -0.)
    assert tr.error == [.5, 0.]


# ---- report -------------------------------------------------------------------------------------------------------------

def test_report_requires_every_field_and_writes_once(tmp_path):
    fields = {k: None for k in report.REQUIRED}
    fields.update(scope="smoke", test_opened=False)
    path = report.write(tmp_path / "r.json", **fields)
    assert json.loads(path.read_text())["format"] == report.FORMAT
    with pytest.raises(FileExistsError):
        report.write(path, **fields)
    with pytest.raises(report.ReportError, match="lacks"):
        report.write(tmp_path / "s.json", scope="smoke")
    with pytest.raises(report.ReportError, match="final-test"):
        report.write(tmp_path / "t.json", **{**fields, "test_opened": True})


# ---- frame cache (ffmpeg) -----------------------------------------------------------------------------------------------

needs_ffmpeg = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
                                  reason="ffmpeg/ffprobe not on PATH")


def test_progressions_compress_the_anchor_grid():
    assert cache.progressions([0, 4, 8, 12, 13, 20]) == [(0, 12, 4), (13, 20, 7)]
    assert cache.select_expression([5]) == "select=eq(n\\,5)"


def _cached_session(tmp_path, frames=140, pts_shift=0, size=(640, 360), video=None, media=None, timebase=None):
    video = video or fixture.write_video(tmp_path / "v.mkv", frames)
    tb, pts = fixture.probe_pts(video)
    header, rows = fixture.session("c", runs=(12, 10), video_path=str(video), timebase=timebase or tb,
                                   pts_of=lambda n: pts[n + pts_shift])
    header["video_size"] = list(size)
    header["media_sha256"] = media or cache.file_sha256(video)
    return fixture.write(tmp_path / "c.jsonl", header, rows), rows


@needs_ffmpeg
def test_cache_holds_each_rows_exact_frame(tmp_path):
    path, rows = _cached_session(tmp_path)
    session = steps.load(path)
    import platform
    if platform.system() != "Darwin":
        with pytest.raises(cache.CacheError, match="Mac only"):
            cache.build(session, tmp_path / "refused")
    m = cache.build(session, tmp_path / "cache", any_platform=True)
    assert m["frames"] == len({r["frame"]["frame_index"] for r in rows}) and m["steps_sha256"] == session.sha256
    assert m["videos"][0]["timebase"] == [1, 1000] and "bitexact" in m["graph"] and "in_color_matrix=bt709" in m["graph"]
    data = {k: (tmp_path / "cache" / f"{k}.u8").read_bytes() for k in ("global", "crop", "hud")}
    size = {"global": 144 * 256 * 3, "crop": 128 * 128 * 3, "hud": 80 * 200 * 3}
    assert all(len(data[k]) == m["frames"] * size[k] for k in data)
    for k, r in enumerate(rows):
        bg, fg = fixture.frame_colours(r["frame"]["frame_index"])
        pos = m["row_frame"][k]

        def px(stream, y, x, width):
            at = pos * size[stream] + (y * width + x) * 3
            return list(data[stream][at:at + 3])
        close = lambda a, b: all(abs(u - v) <= 2 for u, v in zip(a, b))
        assert close(px("global", 0, 0, 256), bg) and close(px("crop", 64, 64, 128), fg)
        assert close(px("hud", 10, 100, 200), bg) and close(px("hud", 60, 20, 200), bg)   # ability row; webs box
        assert px("hud", 60, 150, 200) == [0, 0, 0]                                      # padding
    assert steps.sha256(tmp_path / "cache" / "hud.u8") == m["hud_sha256"]


@needs_ffmpeg
def test_cache_refuses_a_pts_that_disagrees_with_the_step_table(tmp_path):
    path, _ = _cached_session(tmp_path, pts_shift=1)          # the importer's ordinal would be off by one
    with pytest.raises(cache.CacheError, match="pts"):
        cache.build(steps.load(path), tmp_path / "cache", any_platform=True)


@needs_ffmpeg
def test_cache_refuses_a_video_of_another_size(tmp_path):
    path, _ = _cached_session(tmp_path, size=(1280, 720))
    with pytest.raises(cache.CacheError, match="size"):
        cache.build(steps.load(path), tmp_path / "cache", any_platform=True)


@needs_ffmpeg
def test_cache_refuses_other_media_another_timebase_and_unpinned_colour(tmp_path):
    path, _ = _cached_session(tmp_path, media="0" * 64)
    with pytest.raises(cache.CacheError, match="differs from the session's original"):
        cache.build(steps.load(path), tmp_path / "c1", any_platform=True)
    (tmp_path / "c.jsonl").unlink()
    path, _ = _cached_session(tmp_path, video=tmp_path / "v.mkv", timebase=(1, 90000))
    with pytest.raises(cache.CacheError, match="timebase"):
        cache.build(steps.load(path), tmp_path / "c2", any_platform=True)
    import subprocess
    pc = tmp_path / "pc.mkv"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=120:d=1.2", "-c:v", "libx264",
                    "-pix_fmt", "yuvj420p", "-color_range", "pc", str(pc)], check=True)
    (tmp_path / "c.jsonl").unlink()
    path, _ = _cached_session(tmp_path, video=pc)
    with pytest.raises(cache.CacheError, match="colour"):
        cache.build(steps.load(path), tmp_path / "c3", any_platform=True)
    assert cache.check_colour({"pix_fmt": "yuv420p", "color_range": "tv", "color_space": "bt709"}) is None


# ---- unknown pitch gain (lead decision: no pitch gain is assumed until the pitch take exists) ------------------------

def test_an_unknown_pitch_gain_masks_pitch_everywhere(tmp_path):
    s = steps.load(write_session(tmp_path, "np", pitch_gain=None, runs=(700, 400)))
    t = steps.target(s.rows[5], s.calibration)
    assert t["yaw"] is not None and t["pitch"] is None and t["cp"] is None
    v = steps.prev_vector(t)
    m = vocab.CAMERA_CLASSES
    assert sum(v[3 * vocab.N + m: 3 * vocab.N + 2 * m]) == 0 and sum(v[3 * vocab.N: 3 * vocab.N + m]) == 1
    stats = steps.train_statistics([s])
    assert not stats["pitch_gain_known"] and sum(stats["camera"]["pitch"]) == 0 and stats["drift"]["pitch"] == [None, None]
    assert baselines.fit_ar2([s])["pitch"] == (0., 0.)
    runs = [steps.step_records(s, a, b) for a, b in steps.runs(s)]
    block = metrics.evaluate(metrics.predict_runs(runs, oracle), **metrics.TEACHER)
    assert block["camera_axes"] == ["yaw"] and block["camera"]["pitch"]["steps"] == 0
    assert block["camera_mae_mean"] == block["camera"]["yaw"]["mae_deg"]


def test_an_unknown_pitch_gain_blocks_the_pilot_but_not_the_gates(tmp_path):
    train = steps.load(write_session(tmp_path, "np", pitch_gain=None, runs=(800, 600)))
    val = steps.load(write_session(tmp_path, "npv", split="val", pitch_gain=None, runs=(300, 200), seed=3))
    runs = [steps.step_records(val, a, b) for a, b in steps.runs(val)]
    stats = steps.train_statistics([train])
    stats["live_mask"] = list(vocab.live_mask([1000] * vocab.N))
    ev = lambda f, w=metrics.TEACHER: metrics.evaluate(metrics.predict_runs(runs, f), **w)
    tf = {"model": {s: ev(oracle) for s in gates.SEEDS},
          "history_only": {s: ev(baselines.persistence) for s in gates.SEEDS},
          "persistence": ev(baselines.persistence), "zero_motion": ev(baselines.zero_motion),
          "prior": ev(baselines.prior(stats)), "echo": ev(baselines.echo),
          "ar2": ev(baselines.ar2(baselines.fit_ar2([train])))}
    sf = {"model": {s: ev(oracle, metrics.SELF) for s in gates.SEEDS},
          "history_only": {s: ev(baselines.persistence, metrics.SELF) for s in gates.SEEDS}}
    sane = {s: metrics.sanity(metrics.predict_runs(runs, oracle)) for s in gates.SEEDS}
    human = metrics.sanity(metrics.predict_runs(runs, metrics.truth))
    v = gates.evaluate(tf, sf, sane, stats, human)
    assert all(v[g]["pass"] for g in ("G0", "G1", "G2", "G3", "G4", "G5", "G6"))
    assert list(v["G3"]["axes"]) == ["yaw"] and set(v["G5"]["drift"]) == {"yaw"}
    assert v["pitch_gain_known"] is False and v["pilot_worthy"] is False


def test_calibration_accepts_null_pitch_but_not_zero(tmp_path):
    steps.load(rewrite(tmp_path, "ok", lambda h, r: h["calibration"].update(pitch_deg_per_count=None)))
    with pytest.raises(steps.StepError, match="calibration"):
        steps.load(rewrite(tmp_path, "bad", lambda h, r: h["calibration"].update(pitch_deg_per_count=0)))
    with pytest.raises(steps.StepError, match="calibration"):
        steps.load(rewrite(tmp_path, "bad2", lambda h, r: h["calibration"].pop("pitch_deg_per_count")))


def test_default_bindings_follow_james_hud():
    assert vocab.DEFAULT_BINDINGS["amazing_combo"] == "key:18:0"      # E, the fist on his HUD
    assert vocab.DEFAULT_BINDINGS["get_over_here"] == "key:33:0"      # F, the arrow
    assert vocab.DEFAULT_BINDINGS["team_up"] == "key:46:0"             # C: his team-up, which fires in the range


# ---- review round 2: K3 executor low end, K4 self-fed change --------------------------------------------------------

def test_stick_for_moves_the_zero_rate_point_to_a_measured_deadzone():
    yaw = Cal().yaw_map
    assert stick_for(9., yaw) == pytest.approx(.0486, abs=1e-3)              # unchanged without a deadzone
    assert stick_for(.01, yaw, .05) == pytest.approx(.05, abs=1e-3)          # just past the deadzone
    assert stick_for(9., yaw, .05) == pytest.approx(.05 + .05 * 9 / 18.5, abs=1e-3)
    assert stick_for(18.5, yaw, .05) == pytest.approx(.1) and stick_for(0., yaw, .05) == 0.
    assert stick_for(-172., yaw, .05) == pytest.approx(-.45)
    from dataclasses import replace
    pad = executor.pad_state([0] * vocab.N, [0] * vocab.N, .3, None, cal=replace(Cal(), yaw_deadzone=.05))
    assert pad["rx"] == pytest.approx(stick_for(9., yaw, .05)) and pad["ry"] == 0.


def test_minimum_rotation_rate_bands_and_train_only_profiles(tmp_path):
    low = executor.min_step_degrees()
    assert low["yaw"] == pytest.approx(18.5 / 30) and low["pitch"] == pytest.approx(43 / 30)
    assert not low["deadzone_measured"]
    t = executor.tracking_error([(.1, 0.), (1., 0.), (20., 0.)], [(0., 0.), (1., 0.), (13., 0.)])
    bands = t["yaw"]["by_requested_rate_deg_s"]
    assert set(bands) == {"0-9", "18.5-61.5", "saturated"} and bands["0-9"]["mae"] == pytest.approx(.1)
    f = executor.human_feasibility([.1, 0., 5.], [0., .2])
    assert f["yaw_moving_below_min"] == pytest.approx(.5)
    train = steps.load(write_session(tmp_path))
    profiles = executor.replay_profiles([train])
    assert profiles and all(isinstance(y, float) for run in profiles for y, _ in run)
    with pytest.raises(steps.StepError, match="train or dev"):
        executor.replay_profiles([steps.load(write_session(tmp_path, "v", split="val"))])


def test_self_fed_change_counts_from_the_models_own_previous_hold():
    def rec(start, end):
        held_start, held = [0] * vocab.N, [0] * vocab.N
        held_start[0], held[0] = start, end
        t = {"held": held, "held_start": held_start, "press": [0] * vocab.N, "release": [0] * vocab.N,
             "known": [True] * vocab.N, "multi": [0] * vocab.N, "camera_known": False, "yaw": None, "pitch": None,
             "presses": 0, "unsupported": 0}
        return {"valid": True, "target": t, "prev": None, "tags": [], "regime": "normal", "sitting": "s", "hud": {}}
    held = [0.] * vocab.N
    held[0] = 1.
    pred = {"held": held, "press": [0.] * vocab.N, "release": [0.] * vocab.N, "yaw": 0., "pitch": 0.}
    # the human presses W at step 1; the model holds W from step 0 (one step early)
    run = [(rec(0, 0), pred), (rec(0, 1), pred)]
    tf = metrics.evaluate([run], **metrics.TEACHER)["actions"]["move_forward"]["held_change_f1"]
    sf = metrics.evaluate([run], **metrics.SELF)["actions"]["move_forward"]["held_change_f1"]
    # teacher-forced: the model "changes" at both steps against the human's start (1 TP, 1 FP);
    # self-fed: it changed at step 0 from its own released start and kept holding at step 1 (0 TP, 1 FP, 1 FN)
    assert tf == pytest.approx(2 / 3) and sf == 0.


def test_g4_compares_with_the_self_fed_twin(tmp_path):
    tf, sf, sane, stats, human = gate_inputs(tmp_path)
    assert gates.g4(sf["model"][0], sf["history_only"][0])["pass"]
    assert not gates.g4(sf["history_only"][0], sf["history_only"][0])["pass"]     # no better than the twin


def test_an_action_may_have_several_bindings_but_no_id_twice(tmp_path):
    s = steps.load(write_session(tmp_path))
    assert s.header["bindings"]["melee"] == ["key:47:0", "mouse:5"]
    assert "mouse:5" in steps.bound_ids(s.header["bindings"])
    with pytest.raises(steps.StepError, match="distinct"):
        steps.load(rewrite(tmp_path, "dup", lambda h, r: h["bindings"].update(ultimate="mouse:5")))
    with pytest.raises(steps.StepError, match="distinct"):
        steps.load(rewrite(tmp_path, "empty", lambda h, r: h["bindings"].update(melee=[])))
    with pytest.raises(steps.StepError, match="unbound"):
        steps.load(rewrite(tmp_path, "m5", lambda h, r: r[3].update(unsupported={"mouse:5": 1})))


# ---- round 3 and the calibration take ----------------------------------------------------------------------------

def test_tracking_bands_are_per_axis_and_every_degree_number_carries_the_caveat():
    t = executor.tracking_error([(0., .1), (0., 1.)], [(0., 0.), (0., 1.)])      # pitch 3 and 30 deg/s requested
    assert set(t["pitch"]["by_requested_rate_deg_s"]) == {"0-9", "9-43"}
    assert t["caveat"] == vocab.DEGREE_CAVEAT and "unverified above slow speed" in vocab.DEGREE_CAVEAT
    assert executor.human_feasibility([1.], [0.])["caveat"] == vocab.DEGREE_CAVEAT
    assert executor.min_step_degrees()["caveat"] == vocab.DEGREE_CAVEAT


def test_the_derived_pitch_gain_is_usable_and_recorded(tmp_path):
    s = steps.load(write_session(tmp_path, runs=(700, 400)))
    assert s.calibration["pitch"]["kind"] == "derived_equal_sensitivity"
    stats = steps.train_statistics([s])
    assert stats["pitch_gain_known"] and stats["pitch_gain_kind"] == ["derived_equal_sensitivity"]
    assert steps.target(s.rows[5], s.calibration)["pitch"] is not None
    null = steps.train_statistics([steps.load(write_session(tmp_path, "n", pitch_gain=None))])
    assert not null["pitch_gain_known"]


# ---- D2: a recorded transcode is accepted, anything else refused (intake's check_media contract) --------------------

def _transcoded(tmp_path, original, name="t.mkv"):
    """A lossless re-encode of the fixture video: different bytes, the same frames and pts."""
    import subprocess
    out = tmp_path / name
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(original), "-map", "0:v:0", "-c:v", "ffv1", "-level", "3",
                    "-slices", "4", "-pix_fmt", "bgr0", str(out)], check=True)
    return out


def _relocation(tmp_path, session, original, transcode, *, identity=None):
    from agent import human_intake as hi
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps({
        "kind": hi.TRANSCODE_KIND, "session_id": session.session_id,
        "original": {"path": str(original), "sha256": identity or session.header["media_sha256"]},
        "output": {"path": str(transcode), "sha256": cache.file_sha256(transcode)},
        "verification": {"ok": True, "decoded_frames": 140, "decoded_pts_sha256": "e" * 64, "packets": {"n": 140},
                         "frames_csv": {"matched_frames": 140}},
        "original_deleted": False}), encoding="utf-8")
    rec = hi.relocation_record(receipt, session_id=session.session_id,
                               identity_sha256=identity or session.header["media_sha256"])
    path = tmp_path / "media-relocation.json"
    path.write_text(json.dumps(rec), encoding="utf-8")
    return path, hashlib_sha(path)


def hashlib_sha(path):
    import hashlib
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


@needs_ffmpeg
def test_cache_accepts_the_recorded_transcode_and_decodes_it(tmp_path):
    path, rows = _cached_session(tmp_path)
    session = steps.load(path)
    original = tmp_path / "v.mkv"
    m0 = cache.build(session, tmp_path / "c-original", any_platform=True)
    assert m0["videos"][0]["media_kind"] == "original" and m0["media_relocation"] is None
    transcode = _transcoded(tmp_path, original)
    assert cache.file_sha256(transcode) != session.header["media_sha256"]
    reloc_path, pin = _relocation(tmp_path, session, original, transcode)
    relocation = cache.load_relocation(reloc_path, pin)
    original.rename(tmp_path / "gone.mkv")                  # only the transcode remains
    m1 = cache.build(session, tmp_path / "c-transcode", any_platform=True, relocation=relocation)
    assert m1["videos"][0]["media_kind"] == "transcode"
    assert m1["media_relocation"]["transcoded_sha256"] == cache.file_sha256(transcode)
    assert all(m1[f"{k}_sha256"] == m0[f"{k}_sha256"] for k in ("global", "crop", "hud"))   # the same pixels


@needs_ffmpeg
def test_cache_refuses_media_that_is_neither_the_original_nor_its_recorded_transcode(tmp_path):
    path, _ = _cached_session(tmp_path)
    session = steps.load(path)
    original = tmp_path / "v.mkv"
    transcode = _transcoded(tmp_path, original)
    # a transcode with no relocation
    with pytest.raises(cache.CacheError, match="no relocation"):
        cache.check_media(transcode, session, None)
    # a relocation recorded for another original
    other, pin = _relocation(tmp_path, session, original, transcode, identity="f" * 64)
    with pytest.raises(cache.CacheError, match="another original"):
        cache.check_media(transcode, session, cache.load_relocation(other, pin))
    # a third file, neither the original nor the recorded transcode
    reloc_path, pin = _relocation(tmp_path, session, original, transcode)
    relocation = cache.load_relocation(reloc_path, pin)
    third = _transcoded(tmp_path, original, name="third.mkv")
    import subprocess
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(original), "-c:v", "ffv1", "-level", "1",
                    "-pix_fmt", "bgr0", str(third)], check=True)
    with pytest.raises(cache.CacheError, match="neither the original nor its recorded transcode"):
        cache.check_media(third, session, relocation)
    # the relocation's pin, and its receipt, are checked
    with pytest.raises(cache.CacheError, match="pinned"):
        cache.load_relocation(reloc_path, "0" * 64)
    receipt = tmp_path / "receipt.json"
    receipt.write_text(receipt.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(cache.CacheError, match="receipt changed"):
        cache.check_media(transcode, session, relocation)
    assert cache.check_media(original, session, None) == "original"


# ---- replay source contract (expert replay labels) -------------------------------------------------------------------

def write_replay(tmp_path, name="rp", **kw):
    header, rows = fixture.replay_session(name, **kw)
    return fixture.write(tmp_path / f"{name}.jsonl", header, rows)


def rewrite_replay(tmp_path, name, mutate, **kw):
    header, rows = fixture.replay_session(name, **kw)
    mutate(header, rows)
    return fixture.write(tmp_path / f"{name}.jsonl", header, rows)


def test_a_replay_step_table_loads_with_per_channel_unknowns(tmp_path):
    s = steps.load(write_replay(tmp_path), denylist=steps.load_denylist())
    assert steps.is_replay(s.header) and s.calibration["kind"] == "replay_degrees"
    fwd, goh, ult = (vocab.INDEX[n] for n in ("move_forward", "get_over_here", "ultimate"))
    unknown_move = [r for r in s.rows if not r["held_known"][fwd]]
    assert unknown_move and all(r["held_start"][fwd] is None and r["press"][fwd] is None for r in unknown_move)
    t = steps.target(unknown_move[0], s.calibration)
    assert not t["known"][fwd] and not t["press_known"][fwd] and not t["release_known"][fwd]
    assert t["yaw"] is not None and t["unsupported"] == 0
    assert all(not r["held_known"][ult] and not r["press_known"][ult] for r in s.rows)        # never labelled
    assert all(not r["release_known"][goh] for r in s.rows)                                    # onsets only
    with pytest.raises(steps.StepError, match="train split only"):              # replay rows are never train
        steps.train_statistics([s])
    # the per-channel counting a future pre-registered replay arm would use, on an explicitly relabelled copy
    stats = steps.train_statistics([dataclasses.replace(s, header={**s.header, "split": "train"})])
    assert stats["known"][fwd] == len(s.rows) - len(unknown_move) and stats["press_known"][ult] == 0
    assert stats["pitch_gain_kind"] == ["replay_degrees"] and stats["pitch_gain_known"]


@pytest.mark.parametrize("mutate, message", [
    (lambda h, r: h.update(bindings=dict(vocab.DEFAULT_BINDINGS)), "must not carry"),
    (lambda h, r: h.update(settings_hash="x"), "must not carry"),
    (lambda h, r: h.update(media_relocation={"x": 1}), "must not carry"),
    (lambda h, r: h["calibration"].update(kind="slow_turn_constant"), "replay_degrees"),
    (lambda h, r: h["calibration"]["label_sources"].pop("edges"), "label_sources"),
    (lambda h, r: h["expert_context"].pop("viewer_fov_assumption"), "expert_context"),
    (lambda h, r: h["expert_context"].update(player=""), "expert_context"),
    (lambda h, r: h.update(source_kind="stream"), "source_kind"),
])
def test_replay_header_violations_are_refused(tmp_path, mutate, message):
    with pytest.raises(steps.StepError, match=message):
        steps.load(rewrite_replay(tmp_path, "bad", mutate))


def _unknown_but_marked_known(h, r):
    c = vocab.INDEX["move_forward"]
    row = next(x for x in r if not x["held_known"][c])
    row["held_known"][c] = True                                   # the values are still null


def _conservation(h, r):
    c = vocab.INDEX["jump"]
    row = next(x for x in r if x["held_known"][c] and x["held_start"][c] == x["held_end"][c] == 0)
    row["press"][c] = 1                                           # a press with no hold change and a known release 0


@pytest.mark.parametrize("mutate, message", [
    (lambda h, r: r[3].update(mouse_dx=4), "must not carry"),
    (lambda h, r: r[3].update(unsupported={}), "must not carry"),
    (lambda h, r: r[3].pop("press_known"), "lacks"),
    (_unknown_but_marked_known, "held_known disagrees"),
    (lambda h, r: r[3]["press_known"].__setitem__(vocab.INDEX["ultimate"], True), "press_known disagrees"),
    (lambda h, r: r[3]["press"].__setitem__(vocab.INDEX["get_over_here"], 2), "0 | 1 | null"),
    (_conservation, "edges do not account"),
    (lambda h, r: r[3].update(yaw_deg="1.0"), "float|null"),
    (lambda h, r: r[3].update(beyond_pad_envelope=None), "beyond_pad_envelope"),
])
def test_replay_row_violations_are_refused(tmp_path, mutate, message):
    with pytest.raises(steps.StepError, match=message):
        steps.load(rewrite_replay(tmp_path, "bad", mutate))


def test_a_cohort_holds_one_source_kind_and_replays_take_no_relocation(tmp_path):
    human, replay = write_session(tmp_path, "h"), write_replay(tmp_path, "r")
    with pytest.raises(steps.StepError, match="one source kind"):
        steps.load_cohort([human, replay])
    assert len(steps.load_cohort([replay, write_replay(tmp_path, "r2", seed=4)], splits=("replay",),
                                 allow_replay=True)) == 2
    with pytest.raises(cache.CacheError, match="no media relocation"):
        cache.build(steps.load(replay), tmp_path / "c", any_platform=True, relocation={"kind": "x"})


def test_the_replay_split_is_never_train_val_or_test(tmp_path):
    """Lead decision 2026-09-23: replay rows are never train; split "replay" is excluded by the loader and usable only
    by a pre-registered arm (allow_replay)."""
    replay = write_replay(tmp_path, "r")
    for splits in (("train",), ("val",), ("train", "val")):
        with pytest.raises(steps.StepError, match="replay-split recording is never train"):
            steps.load_cohort([replay], splits=splits)
    with pytest.raises(steps.StepError, match="pre-registered arm"):
        steps.load_cohort([replay], splits=("replay",))
    assert len(steps.load_cohort([replay], splits=("replay",), allow_replay=True)) == 1
    with pytest.raises(steps.StepError, match="must be 'replay'"):                  # a replay source cannot be train
        steps.load(rewrite_replay(tmp_path, "t", lambda h, r: h.update(split="train")))
    with pytest.raises(steps.StepError, match="replay split is for replay sources only"):
        steps.load(write_session(tmp_path, "h", split="replay"))


def test_unknown_replay_channels_are_never_scored_or_fed_back(tmp_path):
    s = steps.load(write_replay(tmp_path, runs=(300,)))
    recs = [steps.step_records(s, a, b) for a, b in steps.runs(s)]
    fwd, goh = vocab.INDEX["move_forward"], vocab.INDEX["get_over_here"]
    everything_on = lambda rec: {"held": [1.] * vocab.N, "press": [1.] * vocab.N, "release": [1.] * vocab.N,
                                 "yaw": 0., "pitch": 0.}
    m = metrics.evaluate(metrics.predict_runs(recs, everything_on), **metrics.TEACHER)
    known_move = sum(r["held_known"][fwd] for r in s.rows if r["gap_free"])
    assert m["actions"]["move_forward"]["steps"] == known_move < len(s.rows)
    assert m["actions"]["ultimate"]["steps"] == 0 and m["actions"]["ultimate"]["pred_presses"] == 0
    assert m["actions"]["get_over_here"]["release_f1"] is None                    # no release is ever labelled
    t = steps.target(next(r for r in s.rows if not r["held_known"][fwd]), s.calibration)
    v = steps.prev_vector({**t, "held": [1] * vocab.N, "press": [1] * vocab.N, "release": [1] * vocab.N})
    n = vocab.N
    assert v[fwd] == v[n + fwd] == v[2 * n + fwd] == 0.                          # unknown: no bit, whatever the value
    assert v[n + goh] == (1. if t["press_known"][goh] else 0.)


# ---- replay press windows (the window-level loss; lane doc "Replay window-level loss") -------------------------------

def write_windows(tmp_path, name="rw", mutate=None, **kw):
    header, rows, doc = fixture.replay_windows_session(name, **kw)
    if mutate:
        mutate(header, rows, doc)
    return fixture.write_replay_windows(tmp_path, name, header=header, rows=rows, doc=doc)


def test_press_windows_load_with_complete_partial_flagged_and_overlapping_windows(tmp_path):
    s = steps.load(write_windows(tmp_path))
    w = steps.load_windows(s)
    wc, goh, combo = (vocab.INDEX[n] for n in ("web_cluster", "get_over_here", "amazing_combo"))
    assert w.report["web_cluster"] == {"records": 4, "cast": 4, "flagged": 0, "complete": 3, "partial": 1,
                                       "too_long": 0, "counted": 3, "overlap_pairs": 1, "largest_group": 2}
    assert w.report["get_over_here"]["flagged"] == 1 and w.report["get_over_here"]["counted"] == 2
    assert w.report["amazing_combo"]["too_long"] == 1 and w.report["amazing_combo"]["counted"] == 1
    # complete cast windows <= 64 rows enter the term; the partial, flagged and 70-row ones do not
    assert w.counted == [(wc, 10, 25), (wc, 20, 35), (goh, 40, 50), (wc, 60, 75), (goh, 84, 99), (combo, 200, 210)]
    assert (combo, 78, 147) in w.complete and (combo, 78, 147) not in w.counted
    # no step inside any window (cast, flagged or partial) is a 0 or a 1 for its action; the table holds no cast 1
    doc = json.loads(steps.windows_path(s).read_text(encoding="utf-8"))
    for rec in doc["windows"]:
        c = vocab.INDEX[rec["action"]]
        assert all(s.rows[k]["press"][c] is None for k in range(rec["rows"][0], rec["rows"][1] + 1))
    assert not any(r["press"][c] == 1 for r in s.rows for c in (wc, goh, combo))


def _set(path_keys, value):
    def mutate(header, rows, doc):
        target = doc
        for k in path_keys[:-1]:
            target = target[k]
        target[path_keys[-1]] = value
    return mutate


def _dup(header, rows, doc):
    doc["windows"].append(dict(doc["windows"][0]))


def _fill(header, rows, doc):
    first = doc["windows"][0]
    c = vocab.INDEX[first["action"]]
    rows[first["rows"][0]]["press"][c], rows[first["rows"][0]]["press_known"][c] = 0, True


@pytest.mark.parametrize("mutate, message", [
    (_fill, "non-null web_cluster press"),                       # a cast is never both a window and a step 0
    (_set(["windows", 0, "complete"], False), "complete is False"),
    (_set(["windows", 0, "rows"], [11, 25]), "differ from the steps overlapping"),
    (_dup, "exact duplicate"),
    (_set(["windows", 0, "count"], 0), "count must be"),
    (_set(["windows", 0, "action"], "fireball"), "not in the vocabulary"),
    (_set(["windows", 0, "cast"], 1), "are bools"),
    (_set(["windows", 0, "lo_ns"], 10 ** 18), "lo_ns <= hi_ns"),
    (_set(["format"], "rivals-replay-press-windows-v0"), "not rivals-replay-press-windows-v1"),
    (_set(["session_id"], "other"), "names another session"),
    (_set(["step_ns"], 1), "step_ns differs"),
])
def test_malformed_press_windows_are_refused(tmp_path, mutate, message):
    s = steps.load(write_windows(tmp_path, mutate=mutate))
    with pytest.raises(steps.StepError, match=message):
        steps.load_windows(s)


def test_a_windows_file_must_be_the_pinned_one_and_never_sits_beside_a_human_table(tmp_path):
    s = steps.load(write_windows(tmp_path))
    path = steps.windows_path(s)
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(steps.StepError, match="sha256 differs"):
        steps.load_windows(s)
    unpinned = steps.load(write_replay(tmp_path, "plain"))                        # a replay table pinning none
    assert steps.load_windows(unpinned) is None
    steps.windows_path(unpinned).write_text("{}", encoding="utf-8")
    with pytest.raises(steps.StepError, match="does not pin"):
        steps.load_windows(unpinned)
    human = steps.load(write_session(tmp_path, "h"))
    assert steps.load_windows(human) is None
    steps.windows_path(human).write_text("{}", encoding="utf-8")
    with pytest.raises(steps.StepError, match="does not pin"):
        steps.load_windows(human)


def test_each_counted_window_is_placed_in_exactly_one_sequence(tmp_path):
    s = steps.load(write_windows(tmp_path))
    w = steps.load_windows(s)
    goh = vocab.INDEX["get_over_here"]
    for stride, own in ((48, []), (64, [(goh, 84, 99)])):
        placed, unplaced = steps.place_windows(s, w.counted, stride=stride)
        assert not unplaced and sorted((c, p0, p1) for c, p0, p1, *_ in placed) == sorted(w.counted)
        assert [(c, p0, p1) for c, p0, p1, *_, is_own in placed if is_own] == own
        for c, p0, p1, st, n, a, is_own in placed:                          # scored whole: after burn-in, inside
            assert st + steps.loss_mask_start(st, a) <= p0 and p1 < st + n
    placed, _ = steps.place_windows(s, w.counted, lag=1, stride=48)            # output k is the target of row k + 1
    assert [(p0, p1) for c, p0, p1, *_ in placed][:1] == [(9, 24)]


def test_windows_count_as_press_positives_in_replay_statistics(tmp_path):
    s = steps.load(write_windows(tmp_path))
    relabelled = dataclasses.replace(s, header={**s.header, "split": "train"})   # as a future replay arm would
    placed, _ = steps.place_windows(s, steps.load_windows(s).counted, stride=64)
    plain = steps.train_statistics([relabelled])
    with_windows = steps.train_statistics([relabelled], windows={s.session_id: placed})
    wc, goh = vocab.INDEX["web_cluster"], vocab.INDEX["get_over_here"]
    assert plain["press"][wc] == plain["press"][goh] == 0                       # the table holds no cast 1
    assert with_windows["press"][wc] == 3 and with_windows["press"][goh] == 2
    assert with_windows["press_known"][wc] == plain["press_known"][wc] + 3
    assert steps.pos_weight(3, with_windows["press_known"][wc]) == 20.          # capped, as for a human press


def test_window_recall_counts_a_window_once_whatever_its_presses(tmp_path):
    s = steps.load(write_windows(tmp_path))
    w = steps.load_windows(s)
    runs = [steps.step_records(s, a, b) for a, b in steps.runs(s)]
    wc = vocab.INDEX["web_cluster"]

    def pressing(rows):
        return lambda rec: {"held": [0.] * vocab.N, "release": [0.] * vocab.N, "yaw": 0., "pitch": 0.,
                            "press": [1. if (rec["target_row"] in rows and c == wc) else 0. for c in range(vocab.N)]}
    block = metrics.window_block(metrics.predict_runs(runs, pressing({12, 13, 60})), {s.session_id: w.complete})
    a = block["by_action"]["web_cluster"]
    assert (a["windows"], a["evaluated"], a["hits"], a["presses"]) == (3, 3, 2, 3)   # 10-25 and 20-35 share 12, 13
    assert a["recall"] == 2 / 3 and a["zero_row_press_rate"] == 0.
    assert "counts" not in block                                                 # carried only when given (N4)
    counts = {"web_cluster": {"windows": 4}}
    assert metrics.window_block([], {s.session_id: w.complete}, counts=counts)["counts"] == counts
    everywhere = metrics.window_block(metrics.predict_runs(runs, pressing(set(range(len(s.rows))))),
                                      {s.session_id: w.complete})["by_action"]["web_cluster"]
    assert everywhere["recall"] == 1. and everywhere["zero_row_press_rate"] == 1.   # recall alone would reward this


# ---- cohort patch equivalence (docs/lanes/end-to-end-fit-patch-equivalence.md) ----------------------------------------

OLD_BUILD, NEW_BUILD = "1.1.3870120/build25364676", "1.1.3892207/build25501035"
KIT = "Season 10, Version 20260911"


def on_build(tmp_path, name, build, **kw):
    return rewrite(tmp_path, name, lambda h, r: h.update(patch=build), **kw)


def write_equivalence(tmp_path, kits, name="eq.json", fmt=steps.PATCH_EQUIVALENCE_FORMAT):
    """A test equivalence file and its LF-normalised pin."""
    path = tmp_path / name
    path.write_text(json.dumps({"format": fmt, "kit_versions": kits}), encoding="utf-8")
    return steps.load_patch_equivalence(path, steps.sha256(path))


def entry(*builds, **kw):
    return {"builds": list(builds), "evidence": ["patch notes"], "decided_by": "lead", "decided_on": "2026-09-24", **kw}


def test_two_builds_under_one_kit_version_cohort_together(tmp_path):
    old, new = on_build(tmp_path, "old", OLD_BUILD), on_build(tmp_path, "new", NEW_BUILD)
    with pytest.raises(steps.StepError, match="patch differs from the cohort"):      # without the file: exact builds
        steps.load_cohort([old, new])
    real = steps.load_patch_equivalence()                                             # the pinned data file
    assert real.sha256 == steps.PATCH_EQUIVALENCE_SHA256 and real.kit_of == {OLD_BUILD: KIT, NEW_BUILD: KIT}
    sessions = steps.load_cohort([old, new], equivalence=real)
    assert [s.header["patch"] for s in sessions] == [OLD_BUILD, NEW_BUILD]            # headers keep the real build
    synthetic = write_equivalence(tmp_path, {"K": entry("b1", "b2")})
    assert len(steps.load_cohort([on_build(tmp_path, "b1", "b1"), on_build(tmp_path, "b2", "b2")],
                                 equivalence=synthetic)) == 2


def test_a_build_the_file_does_not_name_or_another_kit_version_is_refused(tmp_path):
    real = steps.load_patch_equivalence()
    unknown = on_build(tmp_path, "u", "1.1.9999999/build0")
    with pytest.raises(steps.StepError, match=r"game build '1\.1\.9999999/build0' is not in .*patch-equivalence\.json"):
        steps.load_cohort([unknown], equivalence=real)                                # even a cohort of one
    with pytest.raises(steps.StepError, match=r"1\.1\.9999999/build0"):
        steps.load_cohort([on_build(tmp_path, "o", OLD_BUILD), unknown], equivalence=real)
    two = write_equivalence(tmp_path, {"K1": entry("b1"), "K2": entry("b2")})
    with pytest.raises(steps.StepError, match="kit version 'K2' \\(build 'b2'\\) differs from the cohort's 'K1'"):
        steps.load_cohort([on_build(tmp_path, "b1", "b1"), on_build(tmp_path, "b2", "b2")], equivalence=two)


@pytest.mark.parametrize("kits, fmt, message", [
    ({"K": entry("b1")}, "rivals-patch-equivalence-v0", "is not rivals-patch-equivalence-v1"),
    ({}, steps.PATCH_EQUIVALENCE_FORMAT, "no kit version"),
    ({"K": entry()}, steps.PATCH_EQUIVALENCE_FORMAT, "non-empty list of builds"),
    ({"K": entry("")}, steps.PATCH_EQUIVALENCE_FORMAT, "non-empty list of builds"),
    ({"K": entry("b1", evidence=[])}, steps.PATCH_EQUIVALENCE_FORMAT, "needs its evidence"),
    ({"K": entry("b1", decided_by="")}, steps.PATCH_EQUIVALENCE_FORMAT, "needs decided_by"),
    ({"K": entry("b1", decided_on="24/09/2026")}, steps.PATCH_EQUIVALENCE_FORMAT, "YYYY-MM-DD"),
    ({"K1": entry("b1"), "K2": entry("b1")}, steps.PATCH_EQUIVALENCE_FORMAT, "under two kit versions"),
])
def test_a_malformed_equivalence_file_is_refused(tmp_path, kits, fmt, message):
    with pytest.raises(steps.StepError, match=message):
        write_equivalence(tmp_path, kits, fmt=fmt)


def test_a_tampered_equivalence_file_is_refused_by_its_pin(tmp_path):
    real = steps.load_patch_equivalence()
    raw = open(real.path, "rb").read()
    crlf = tmp_path / "crlf.json"
    crlf.write_bytes(raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))                                     # a CRLF checkout still loads (raw may already be CRLF)
    assert steps.load_patch_equivalence(crlf).kit_of == real.kit_of
    tampered = tmp_path / "tampered.json"
    tampered.write_bytes(raw.replace(b'"decided_by": "lead"', b'"decided_by": "someone"'))
    with pytest.raises(steps.StepError, match="differs from its pinned sha256"):
        steps.load_patch_equivalence(tampered)                                        # the default pin
    with pytest.raises(steps.StepError, match="differs from its pinned sha256"):
        steps.load_patch_equivalence(real.path, sha256_pin=None)                     # no pin, no file


def test_replay_cohorts_compare_their_patch_exactly_with_or_without_the_file(tmp_path):
    real = steps.load_patch_equivalence()
    a, b = write_replay(tmp_path, "r1"), write_replay(tmp_path, "r2", seed=4)
    assert len(steps.load_cohort([a, b], splits=("replay",), allow_replay=True, equivalence=real)) == 2


ADMITTED = {"20260923T051828-422Z-33696-1": "d49224e3c4382a62ebb4c4252bcc5800138782688e1d0f60e03e46ce4b6e7edb",
            "20260923T171533-187Z-33696-5": "dc28b0c1511f7847c8dde08c3e04addce8b57bc6c32cc2873405962d3235559e",
            "20260923T200129-346Z-33696-6": "fcc9b0443e720648b899453ea3f04f82c0a6dd1735f30a420a36b3675549ba8e",
            "20260923T205528-900Z-45572-3": "941950f16edef6a88b14d6bc536e33a66a0e779867fa145c78e7142164e1fd98"}


@pytest.mark.corpus
def test_the_four_admitted_tables_cohort_as_before_and_are_byte_unchanged():
    root = fixture.Path(steps.__file__).resolve().parents[2]
    paths = [root / "data/human/sessions" / sid / f"{sid}.steps.jsonl" for sid in ADMITTED]
    deny = steps.load_denylist()
    before = steps.load_cohort(paths, splits=("train",), denylist=deny)              # the exact comparison, as before
    after = steps.load_cohort(paths, splits=("train",), denylist=deny, equivalence=steps.load_patch_equivalence())
    assert {s.session_id: s.sha256 for s in before} == {s.session_id: s.sha256 for s in after} == ADMITTED
    assert {s.header["patch"] for s in after} == {OLD_BUILD}
