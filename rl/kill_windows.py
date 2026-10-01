"""Kill windows: the seconds before each pixel-read hit or KO in James's range takes (VUH-1321, aim step 0).

  python -m rl.kill_windows [OUT.json]

A window is [t - PRE_S, t] before an event in rl/labels/range_rewards_20260930.json, overlapping windows merged. The
camera head's fine-tune upweights the steps inside them: in those seconds James was bringing the crosshair onto a bot
and keeping it there. Times are video seconds (pts 0 = the session's first frame) and logger ns
(t0_composition_ns + t * 1e9), the step tables' clock.

Three sets per session, because a window before every hit covers 64% of James's time (2 s; 46% at 1 s), which would
dilute an upweight:
  windows          before every hit and KO (the literal brief)
  onset_windows    before the first hit of each engagement (rl.ttk: hits under 3 s apart), the acquisition phase the
                   policy lacks; 27% of the time, the recommended set
  ko_windows       before each KO; 23%
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from rl.ttk import engagements

PRE_S = 2.0
LABELS = Path("rl/labels/range_rewards_20260930.json")
HELDOUT = Path("rl/labels/range_rewards_val_20260930.json")   # mix399's val take: evaluation only, never weighted
SETS = ("windows", "onset_windows", "ko_windows")


def windows(times, pre=PRE_S):
    """Merged [start, end] intervals covering [t - pre, t] for each t (clipped at 0)."""
    out = []
    for t in sorted(times):
        s = max(0., t - pre)
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], t)
        else:
            out.append([s, t])
    return [[round(a, 2), round(b, 2)] for a, b in out]


def session_windows(d, pre=PRE_S):
    sessions = {}
    for name, s in d["sessions"].items():
        t0 = s["t0_composition_ns"]
        onsets = [e["start"] for e in engagements(s["hit"], s["ko"])]
        row = {"seconds": s["seconds"], "t0_composition_ns": t0, "hits": len(s["hit"]), "kos": len(s["ko"]),
               "engagements": len(onsets)}
        for key, times in zip(SETS, (s["hit"] + s["ko"], onsets, s["ko"])):
            w = windows(times, pre)
            row[key + "_s"] = w
            row[key + "_ns"] = [[t0 + int(round(a * 1e9)), t0 + int(round(b * 1e9))] for a, b in w]
            row[key + "_covered_s"] = round(sum(b - a for a, b in w), 1)
        sessions[name] = row
    return sessions


def build(labels=LABELS, heldout=HELDOUT, pre=PRE_S):
    d = json.loads(Path(labels).read_text())
    sessions = session_windows(d, pre)
    total = sum(s["seconds"] for s in sessions.values())
    share = {k: round(sum(s[k + "_covered_s"] for s in sessions.values()) / total, 3) for k in SETS}
    return {"what": " ".join(__doc__.split("\n\n")[1].split()), "pre_s": pre, "source": str(labels),
            "reader_commit": d.get("reader_commit"), "covered_share": share, "recommended": "onset_windows",
            "sessions": sessions,
            "heldout_sessions": session_windows(json.loads(Path(heldout).read_text()), pre) if Path(heldout).exists()
            else {},
            "heldout_note": "mix399's val take (policy/bc2/cloud.py VAL): for evaluating pre-hit camera sign and MAE "
                            "only; never weight or train on it. sessions holds TRAIN and DEV; weight TRAIN only."}


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    out = Path(argv[0] if argv else "rl/labels/kill_windows_20260930.json")
    result = build()
    out.write_text(json.dumps(result, indent=1) + "\n")
    print(out, "covered share", result["covered_share"])
    return result


if __name__ == "__main__":
    main()
