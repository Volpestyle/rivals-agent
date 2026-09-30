"""Paired frames and logged actions for the world model. Standard library only.

The step tables (`policy/range_bc/steps.py`, format rivals-range-steps-v1) hold one row per 30 Hz anchor: the
frame shown at the anchor and the input in the bin that follows it (lag 0). The world model runs at 10 Hz, so one
model step covers STRIDE rows: its frame is the first row's frame and its action aggregates the STRIDE rows' input.
Action a_k is what the player did between frame k and frame k+1.

Action vector (ACTION_DIM floats):
  held[15]  share of the step's rows in which each semantic action was held (unknown -> 0)
  press[15] 1 if the action was pressed in any of the step's rows
  yaw, pitch  camera degrees over the step (mouse counts x the session's calibration), divided by DEG_SCALE
"""
from __future__ import annotations

import json

ACTIONS = ("move_forward", "move_left", "move_back", "move_right", "jump", "web_swing", "get_over_here",
           "amazing_combo", "ultimate", "melee", "spider_power", "web_cluster", "team_up", "goh_targeting",
           "simple_swing")
N_ACT = len(ACTIONS)
ACTION_DIM = 2 * N_ACT + 2
DEG_SCALE = 20.0     # a fast flick is ~30-60 deg per 100 ms; this keeps typical values near unit scale
STRIDE = 3           # 30 Hz rows per 10 Hz model step


def read_steps(path):
    with open(path, encoding="utf-8") as f:
        header = json.loads(f.readline())
        rows = [json.loads(line) for line in f if line.strip()]
    if header.get("format") != "rivals-range-steps-v1":
        raise ValueError(f"{path}: not a rivals-range-steps-v1 table")
    return header, rows


def _order(header):
    names = header["actions"]
    missing = [a for a in ACTIONS if a not in names]
    if missing:
        raise ValueError(f"step table lacks actions {missing}")
    return [names.index(a) for a in ACTIONS]


def row_features(header, row, order=None):
    """(held, press, yaw_deg, pitch_deg) for one 30 Hz row."""
    order = order or _order(header)
    cal = header["calibration"]
    held = [float(row["held_end"][j]) if row["held_known"][j] else 0.0 for j in order]
    press = [1.0 if row["press"][j] else 0.0 for j in order]
    if row.get("relative_known"):
        yaw = row["mouse_dx"] * cal["yaw_deg_per_count"]
        pitch = row["mouse_dy"] * cal["pitch_deg_per_count"]
    else:
        yaw = pitch = 0.0
    return held, press, yaw, pitch


def step_actions(header, rows, stride=STRIDE):
    """Per row r, the 10 Hz step action over rows r..r+stride-1 (a list of ACTION_DIM floats).

    Rows whose step would run past the table's end get None; callers only use starts from valid_starts.
    """
    order = _order(header)
    feats = [row_features(header, r, order) for r in rows]
    out = []
    for r in range(len(rows)):
        if r + stride > len(rows):
            out.append(None)
            continue
        chunk = feats[r:r + stride]
        held = [sum(c[0][j] for c in chunk) / stride for j in range(N_ACT)]
        press = [max(c[1][j] for c in chunk) for j in range(N_ACT)]
        yaw = sum(c[2] for c in chunk) / DEG_SCALE
        pitch = sum(c[3] for c in chunk) / DEG_SCALE
        out.append(held + press + [yaw, pitch])
    return out


def usable(row):
    return row.get("suitability") == "accepted" and bool(row.get("gap_free"))


def valid_starts(rows, span):
    """Row indices s such that rows s..s+span-1 are usable, in one run, with consecutive step indices."""
    starts, streak = [], 0
    for j, row in enumerate(rows):
        if not usable(row):
            streak = 0
        elif streak and rows[j - 1]["run"] == row["run"] and rows[j - 1]["i"] + 1 == row["i"]:
            streak += 1
        else:
            streak = 1
        if streak >= span:
            starts.append(j - span + 1)
    return starts


def window_span(frames, stride=STRIDE):
    """Rows a window of `frames` model frames needs, including the last frame's step action."""
    return stride * frames


def check_not_sealed(session_ids, denylist_path):
    """Refuse any session named in the sealed denylist (exact id match)."""
    with open(denylist_path, encoding="utf-8") as f:
        sealed = {s["session_id"] if isinstance(s, dict) else s for s in json.load(f)["sessions"]}
    hit = sorted(set(session_ids) & sealed)
    if hit:
        raise ValueError(f"sealed sessions refused: {hit}")
