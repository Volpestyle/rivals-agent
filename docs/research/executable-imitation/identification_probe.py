"""Exact synthetic falsification of 'freeze a predictor and it becomes causal'.

No game input, corpus access, third-party dependencies, or learned-policy claims.
All arithmetic is rational. The problem is missing action support, not an
unobserved confounder: x is fully observed. Keep those failure modes distinct.
"""

from fractions import Fraction as F
import json


def mse(model, rows):
    b, g = model
    return sum((b * x + g * u - y) ** 2 for x, u, y in rows) / len(rows)


def fit(rows):
    xx = sum(x * x for x, _, _ in rows)
    uu = sum(u * u for _, u, _ in rows)
    xu = sum(x * u for x, u, _ in rows)
    xy = sum(x * y for x, _, y in rows)
    uy = sum(u * y for _, u, y in rows)
    determinant = xx * uu - xu * xu
    if not determinant:
        return None, determinant
    return ((xy * uu - uy * xu) / determinant,
            (uy * xx - xy * xu) / determinant), determinant


def main():
    truth = (F(1, 2), F(3, 2))
    xs = [F(i, 10) for i in range(-10, 11) if i]
    transition = lambda x, u: truth[0] * x + truth[1] * u
    demos = [(x, x, transition(x, x)) for x in xs]
    reversed_actions = [(x, -x, transition(x, -x)) for x in xs]
    passive_fit, passive_det = fit(demos)
    assert passive_fit is None and passive_det == 0

    # All b+g=2 interpolate the demos. This finite set illustrates an infinite
    # family, not an exhaustive search of parameter space.
    family = [(F(i, 20), F(2) - F(i, 20)) for i in range(41)]
    assert all(mse(m, demos) == 0 for m in family)
    least_norm = (F(1), F(1))
    passive_off_support_error = mse(least_norm, reversed_actions)
    assert passive_off_support_error > 0

    # On this noise-free fully observed toy, one off-diagonal transition gives
    # full rank. This is not a claim that one Rivals measurement is sufficient.
    calibration = (F(1), F(0), transition(F(1), F(0)))
    calibrated, calibrated_det = fit(demos + [calibration])
    assert calibrated == truth and calibrated_det > 0
    assert mse(calibrated, reversed_actions) == 0

    # Solve for a zero endpoint with each identified model. Both controllers
    # use identical goal/state information; no future observation is supplied.
    def control_error(model):
        b, g = model
        return sum(transition(x, -b * x / g) ** 2 for x in xs) / len(xs)

    assert control_error(least_norm) == passive_off_support_error
    assert control_error(calibrated) == 0
    print(json.dumps({
        "kind": "synthetic_identification_falsification_not_gameplay",
        "demonstration_rows": len(demos),
        "perfect_fit_models_checked": len(family),
        "passive_gram_determinant": str(passive_det),
        "passive_minimum_norm_model": [str(v) for v in least_norm],
        "passive_training_mse": str(mse(least_norm, demos)),
        "passive_reversal_prediction_mse": str(passive_off_support_error),
        "passive_zero_goal_control_mse": str(control_error(least_norm)),
        "added_calibration_rows": 1,
        "calibrated_model": [str(v) for v in calibrated],
        "calibrated_gram_determinant": str(calibrated_det),
        "calibrated_reversal_prediction_mse": str(mse(calibrated, reversed_actions)),
        "calibrated_zero_goal_control_mse": str(control_error(calibrated)),
        "new_algorithm_advantage_demonstrated": False,
    }, indent=2))


if __name__ == "__main__":
    main()
