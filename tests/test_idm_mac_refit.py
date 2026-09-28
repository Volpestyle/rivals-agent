"""Synthetic role and score contracts for the single Mac experiment."""
from copy import deepcopy

import pytest

pytest.importorskip("torch")
from policy.idm import mac_refit as M


def manifest():
    return {"sessions": [{"session_id": s, "role": "train"} for s in (*M.P.RANGES, *M.MATCH_TRAIN)]
                        + [{"session_id": s, "role": "heldout"} for s in M.P.DEV],
            "transfer": [{"session_id": s, "selection": {"row_ids": list(range(n))}}
                         for s, n in zip(M.TRANSFER, (15960, 22020))]}


def test_exact_roster_valid():
    M.validate_roster(manifest())


@pytest.mark.parametrize("case", ["holdout_in_train", "dev_in_train", "duplicate", "missing", "repeated_rows"])
def test_role_or_row_drift_refused(case):
    m = manifest()
    if case == "holdout_in_train":
        m["sessions"][0]["session_id"] = M.TRANSFER[0]
    elif case == "dev_in_train":
        m["sessions"][-1]["role"] = "train"
    elif case == "duplicate":
        m["sessions"].append(deepcopy(m["sessions"][0]))
    elif case == "missing":
        m["sessions"].pop(0)
    else:
        m["transfer"][0]["selection"]["row_ids"][1] = 0
    with pytest.raises(ValueError):
        M.validate_roster(m)


def test_common_rows_require_all_real_models_and_apply_to_zero():
    p = {name: {"s": {0: {"yaw_deg": 1, "pitch_deg": 2}}}
         for name in ("raw", "full03", "prior", "zero")}
    p["raw"]["s"][0]["pitch_deg"] = None
    common = M.shared(p)
    assert all(x["s"][0] == {"yaw_deg": 1, "pitch_deg": None} for x in common.values())
    assert p["zero"]["s"][0]["pitch_deg"] == 2
