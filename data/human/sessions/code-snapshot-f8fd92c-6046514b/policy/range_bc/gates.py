"""Gates and the headline number (`docs/lanes/end-to-end-fit.md` §3), pre-registered.

Two evaluation modes over the same validation runs (F2, F3):
    teacher-forced (tf): the true previous action is the input; edges match within [t-1, t]
    self-fed (sf):       the model's own executed previous action is the input, from each run's start; edges match
                         within [t-1, t+1]

    G0  leak check (tf)   the echo baseline's macro press-F1 stays under ECHO_MAX; otherwise the gates are invalid
    G1  frames matter (tf) seed 0 and the 3-seed mean beat the history-only twin: +0.05 macro press-F1 and 10% lower
                          camera MAE. With `g1_press` (the lead's decision on fit-real-prereg-draft.md, before any
                          validation read) the press-F1 part reads the executed teacher-forced blocks instead
                          (metrics.EXECUTED_TEACHER, late 0: a one-step echo scores nothing); the camera part stays
                          on the teacher-forced blocks, and the probability version is reported beside it, ungated
    G2  edges (sf)        macro press-F1 >= 0.30 over the six edge actions; spider_power, web_cluster, get_over_here
                          each >= 0.20. The seed-0 macro is the headline
    G3  camera (tf)       per axis: MAE <= 0.8 x the best of persistence, zero-motion and AR(2); onset/reversal sign
                          agreement >= the best of persistence, AR(2) and the twin + 0.05
    G4  holds (sf)        against the self-fed history-only twin (K4): move and swing balanced accuracy >= the
                          twin's - 0.01, and mean change-F1 > the twin's, a change counted from each model's own
                          previous executed hold
    G5  sanity (sf)       press rates of live actions within [0.5, 2] x human; no predicted hold longer than the
                          longest human hold, and 10 s mean rotation within the human range, where "human" is the
                          train split plus the evaluation set's own recorded actions (a check the human fails is
                          not a check)
    G6  seeds             G2 (sf) and G3 (tf) hold on all three seeds

With an unknown pitch gain (calibration pitch null) the pitch axis is masked everywhere: G1 and G3 use yaw only, G5
skips pitch drift, the verdict carries `pitch_gain_known: false`, and the fit is not pilot-worthy (the executor has no
pitch mapping without the gain).

Changing a threshold after seeing validation numbers voids the gate; the report records these constants.
"""
from . import vocab

SEEDS = (0, 1, 2)
CANDIDATE = 0
ECHO_MAX = .05
G1_PRESS_F1_MARGIN = .05
G1_CAMERA_MAE_RATIO = .90
G2_MACRO = .30
G2_EACH = .20
G3_MAE_RATIO = .80
G3_ONSET_MARGIN = .05
G4_HELD_SLACK = .01
G5_RATE = (.5, 2.)
THRESHOLDS = {k: v for k, v in globals().items() if k.startswith(("ECHO_", "G1_", "G2_", "G3_", "G4_", "G5_"))}


def _mean(values):
    values = list(values)
    return sum(values) / len(values)


def _num(v):
    return 0. if v is None else v


def g0(echo):
    v = echo["macro_press_f1_tol"]
    return {"pass": v <= ECHO_MAX, "echo_macro_press_f1_tol": v}


def g1(model, history, press_model=None, press_history=None):
    """press_model / press_history (both or neither): {seed: block} whose macro press-F1 replaces the teacher-forced
    one; the camera MAE always comes from model / history."""
    press_model, press_history = press_model or model, press_history or history

    def check(m_f1, h_f1, m_mae, h_mae):
        ok_f1 = m_f1 - h_f1 >= G1_PRESS_F1_MARGIN
        ok_mae = m_mae is not None and h_mae is not None and m_mae <= G1_CAMERA_MAE_RATIO * h_mae
        return ok_f1 and ok_mae, {"press_f1_delta": m_f1 - h_f1, "camera_mae": m_mae, "history_camera_mae": h_mae}
    ok0, d0 = check(press_model[CANDIDATE]["macro_press_f1_tol"], press_history[CANDIDATE]["macro_press_f1_tol"],
                    model[CANDIDATE]["camera_mae_mean"], history[CANDIDATE]["camera_mae_mean"])
    maes = [model[s]["camera_mae_mean"] for s in SEEDS] + [history[s]["camera_mae_mean"] for s in SEEDS]
    if any(v is None for v in maes):
        return {"pass": False, "seed0": d0, "mean": None, "reason": "camera MAE undefined"}
    okm, dm = check(_mean(press_model[s]["macro_press_f1_tol"] for s in SEEDS),
                    _mean(press_history[s]["macro_press_f1_tol"] for s in SEEDS),
                    _mean(model[s]["camera_mae_mean"] for s in SEEDS),
                    _mean(history[s]["camera_mae_mean"] for s in SEEDS))
    return {"pass": ok0 and okm, "seed0": d0, "mean": dm}


def g2(block):
    each = {n: _num(block["actions"][n]["press_f1_tol"]) for n in vocab.EDGE_EACH}
    macro = block["macro_press_f1_tol"]
    return {"pass": macro >= G2_MACRO and all(v >= G2_EACH for v in each.values()), "macro": macro, "each": each}


def g3(block, persistence, zero, ar2, twin):
    axes = {}
    for a in block["camera_axes"]:
        mae = block["camera"][a]["mae_deg"]
        onset = block["camera"][a]["onset_sign_agreement"]
        mae_refs = [b["camera"][a]["mae_deg"] for b in (persistence, zero, ar2) if b["camera"][a]["mae_deg"] is not None]
        onset_refs = [b["camera"][a]["onset_sign_agreement"] for b in (persistence, ar2, twin)
                      if b["camera"][a]["onset_sign_agreement"] is not None]
        ok_mae = mae is not None and bool(mae_refs) and mae <= G3_MAE_RATIO * min(mae_refs)
        ok_onset = onset is not None and bool(onset_refs) and onset >= max(onset_refs) + G3_ONSET_MARGIN
        axes[a] = {"pass": ok_mae and ok_onset, "mae_deg": mae, "best_trivial_mae_deg": min(mae_refs, default=None),
                   "onset_sign": onset, "best_reference_onset_sign": max(onset_refs, default=None)}
    return {"pass": bool(axes) and all(v["pass"] for v in axes.values()), "axes": axes}


def g4(block, twin):
    """Both blocks self-fed: the model against the self-fed history-only twin."""
    held = {}
    for n in vocab.HELD_ACTIONS:
        m, p = block["actions"][n]["held_balanced_accuracy"], twin["actions"][n]["held_balanced_accuracy"]
        held[n] = {"model": m, "twin": p, "pass": m is not None and p is not None and m >= p - G4_HELD_SLACK}
    chg = _mean(_num(block["actions"][n]["held_change_f1"]) for n in vocab.HELD_ACTIONS)
    chg_twin = _mean(_num(twin["actions"][n]["held_change_f1"]) for n in vocab.HELD_ACTIONS)
    return {"pass": all(v["pass"] for v in held.values()) and chg > chg_twin, "held": held,
            "change_f1": chg, "twin_change_f1": chg_twin}


def human_reference(stats, human):
    """Longest holds and drift range over the train statistics and the evaluation set's recorded actions."""
    longest = [max(stats["longest_hold"][c], human["longest_hold"][n]) for c, n in enumerate(vocab.NAMES)]
    drift = {}
    for axis in ("yaw", "pitch"):
        values = [v for v in stats["drift"][axis] + human["drift"][axis] if v is not None]
        drift[axis] = [min(values), max(values)] if values else [None, None]
    return {"longest_hold": longest, "drift": drift, "live_mask": stats["live_mask"],
            "pitch_gain_known": stats.get("pitch_gain_known", True)}


def g5(block, sanity, stats):
    rates = {}
    for c, n in enumerate(vocab.NAMES):
        if not stats["live_mask"][c]:
            continue
        m = block["actions"][n]
        human, pred = m["human_press_rate"], m["pred_press_rate"]
        if human:
            ratio = pred / human
            ok = G5_RATE[0] <= ratio <= G5_RATE[1]
        else:
            ratio, ok = None, pred == 0     # no human presses on validation: any predicted press fails
        rates[n] = {"ratio": ratio, "pass": ok}
    stuck = {n: {"predicted": sanity["longest_hold"][n], "human": stats["longest_hold"][c],
                 "pass": sanity["longest_hold"][n] <= stats["longest_hold"][c]} for c, n in enumerate(vocab.NAMES)}
    drift = {}
    for axis in ("yaw", "pitch") if stats.get("pitch_gain_known", True) else ("yaw",):
        (plo, phi), (hlo, hhi) = sanity["drift"][axis], stats["drift"][axis]
        if hlo is None:
            drift[axis] = {"pass": False, "reason": "no 10 s human window in train"}
        elif plo is None:
            drift[axis] = {"pass": True, "reason": "no 10 s predicted window"}
        else:
            drift[axis] = {"pass": hlo <= plo and phi <= hhi, "predicted": [plo, phi], "human": [hlo, hhi]}
    ok = all(v["pass"] for v in rates.values()) and all(v["pass"] for v in stuck.values()) and all(
        v["pass"] for v in drift.values())
    return {"pass": ok, "rates": rates, "stuck": stuck, "drift": drift}


def evaluate(tf, sf, sanity, stats, human, g1_press=None):
    """tf: {"model": {seed: block}, "history_only": {seed: block}, "persistence", "zero_motion", "prior", "echo",
    "ar2": block}; sf: {"model": {seed: block}, "history_only": {seed: block}}; sanity: {seed: metrics.sanity(...)};
    stats: train statistics;
    human: metrics.sanity over the evaluation set's recorded actions. Blocks are the "all" entries of
    `metrics.stratified`.
    g1_press: None (G1 as pre-registered first) or {"model": {seed: block}, "history_only": {seed: block}} of executed
    teacher-forced blocks for G1's press-F1 part; the verdict then records "G1_press_source" and the probability G1
    as "G1_teacher_forced_probability" (not gated). Without it the verdict is exactly as before."""
    reference = human_reference(stats, human)
    missing = [s for s in SEEDS if s not in tf["model"] or s not in tf["history_only"] or s not in sf["model"]
               or s not in sf["history_only"] or s not in sanity
               or (g1_press is not None and (s not in g1_press["model"] or s not in g1_press["history_only"]))]
    if missing:
        return {"complete": False, "missing_seeds": missing, "pilot_worthy": False, "thresholds": THRESHOLDS,
                "pitch_gain_known": stats.get("pitch_gain_known", True)}
    tfm, sfm = tf["model"], sf["model"]
    out = {"complete": True, "thresholds": THRESHOLDS,
           "headline_self_fed_macro_press_f1": sfm[CANDIDATE]["macro_press_f1_tol"],
           "G0": g0(tf["echo"]), "G1": g1(tfm, tf["history_only"], *((g1_press["model"], g1_press["history_only"])
                                                                   if g1_press is not None else ())),
           "G2": g2(sfm[CANDIDATE]),
           "G3": g3(tfm[CANDIDATE], tf["persistence"], tf["zero_motion"], tf["ar2"], tf["history_only"][CANDIDATE]),
           "G4": g4(sfm[CANDIDATE], sf["history_only"][CANDIDATE]),
           "G5": g5(sfm[CANDIDATE], sanity[CANDIDATE], reference)}
    per_seed = {s: {"G2": g2(sfm[s])["pass"],
                    "G3": g3(tfm[s], tf["persistence"], tf["zero_motion"], tf["ar2"], tf["history_only"][s])["pass"]}
                for s in SEEDS}
    out["G6"] = {"pass": all(v["G2"] and v["G3"] for v in per_seed.values()), "seeds": per_seed}
    if g1_press is not None:
        out["G1_press_source"] = "executed_teacher_forced"
        out["G1_teacher_forced_probability"] = g1(tfm, tf["history_only"])
    out["pitch_gain_known"] = stats.get("pitch_gain_known", True)
    out["pitch_gain_kind"] = stats.get("pitch_gain_kind")          # "derived_equal_sensitivity" flags derived labels
    out["degree_caveat"] = stats.get("degree_caveat")
    out["pilot_worthy"] = all(out[g]["pass"] for g in ("G0", "G1", "G2", "G3", "G4", "G5", "G6")) and \
        out["pitch_gain_known"]
    return out
