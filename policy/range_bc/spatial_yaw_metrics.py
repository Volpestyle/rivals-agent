"""Pre-stated exploratory yaw slices; no decoder or threshold selection."""


def _mean(values):
    return sum(values) / len(values) if values else None


def yaw_slices(runs):
    groups = {name: [] for name in ("all", "left", "right", "human_yaw_zero", "both_axes_zero")}
    for run in runs:
        for record, prediction in run:
            target = record["target"]
            if not record["valid"] or not target["camera_known"] or target["yaw"] is None:
                continue
            true, got = target["yaw"], prediction["yaw"]
            if got is None:
                raise ValueError("missing predicted yaw on known target")
            groups["all"].append((true, got))
            groups["left" if true < 0 else "right" if true > 0 else "human_yaw_zero"].append((true, got))
            if true == 0 and target["pitch"] == 0:
                groups["both_axes_zero"].append((true, got))
    result = {}
    for name, values in groups.items():
        moving = [(t, p) for t, p in values if t != 0]
        row = {"n": len(values), "mae_deg": _mean([abs(t - p) for t, p in values]),
               "zero_motion_mae_deg": _mean([abs(t) for t, _ in values])}
        if name in ("human_yaw_zero", "both_axes_zero"):
            row.update(nonzero_turn_rate=_mean([p != 0 for _, p in values]),
                       false_turn_ge_point6_rate=_mean([abs(p) >= .6 for _, p in values]),
                       mean_abs_output_deg=_mean([abs(p) for _, p in values]),
                       false_left_rate=_mean([p < 0 for _, p in values]),
                       false_right_rate=_mean([p > 0 for _, p in values]))
        else:
            row.update(moving_n=len(moving), sign_accuracy=_mean([t * p > 0 for t, p in moving]),
                       missed_turn_rate=_mean([p == 0 for _, p in moving]),
                       opposite_turn_rate=_mean([t * p < 0 for t, p in moving]))
        result[name] = row
    return result


def retention(base_runs, candidate_runs):
    if len(base_runs) != len(candidate_runs):
        raise ValueError("retention run count differs")
    frames = 0
    for base, candidate in zip(base_runs, candidate_runs):
        if len(base) != len(candidate):
            raise ValueError("retention row count differs")
        for (record, left), (other, right) in zip(base, candidate):
            if record != other:
                raise ValueError("retention source rows differ")
            if any(left[k] != right[k] for k in ("held", "press", "release", "pitch")):
                raise ValueError("frozen action/pitch predictions changed")
            frames += 1
    return {"frames": frames, "exact_action_and_pitch_predictions": True}
