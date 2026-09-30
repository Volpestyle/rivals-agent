"""Per-session training arrays from a step table and its frame cache.

Only eligible runs (steps.runs, normal regime) are kept, concatenated in row order; `run_start` marks the first step
of each run so that motion inputs and recurrent state never cross a run boundary. Targets follow steps.target:
held/press/release bits with known masks, camera degrees per 1/30 s step (NaN where unknown) and their classes.
"""
import numpy as np

from policy.range_bc import steps, vocab


def session_arrays(session, row_frame):
    rows_idx = [k for a, b in steps.runs(session) for k in range(a, b)]
    starts = {a for a, _ in steps.runs(session)}
    n, m = len(rows_idx), vocab.N
    out = {"row": np.array(rows_idx, np.int64), "frame": np.array([row_frame[k] for k in rows_idx], np.int64),
           "run_start": np.array([k in starts for k in rows_idx], bool),
           "valid": np.zeros(n, bool), "act": np.zeros((n, 3, m), np.uint8), "act_known": np.zeros((n, 3, m), bool),
           "yaw": np.full(n, np.nan, np.float32), "pitch": np.full(n, np.nan, np.float32),
           "cam_class": np.full((n, 2), vocab.ZERO_CLASS, np.int64), "cam_known": np.zeros((n, 2), bool)}
    for i, k in enumerate(rows_idx):
        row = session.rows[k]
        t = steps.target(row, session.calibration)
        out["valid"][i] = bool(row["gap_free"])
        out["act"][i] = [t["held"], t["press"], t["release"]]
        out["act_known"][i] = [t["known"], t["press_known"], t["release_known"]]
        for axis, key, deg in ((0, "cy", "yaw"), (1, "cp", "pitch")):
            if t[key] is not None:
                out["cam_known"][i, axis] = True
                out["cam_class"][i, axis] = t[key]
                out[deg][i] = t[deg]
    return out
