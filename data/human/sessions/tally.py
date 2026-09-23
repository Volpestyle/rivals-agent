"""Regenerate the corpus tally: data/human/sessions/tally.json and docs/evidence/corpus-tally.md.

    python tally.py [--snapshot code-snapshot-XXXXXXX]

One row per logged session under C:/Users/volpe/Videos/RivalsInput/. Minutes count only for admitted train/val
sessions (focused logged time ∩ accepted segments ∩ gap-free runs >= 1.6 s, never video length). The headline is
per regime, train only. The sealed denylist is loaded first; a denylisted session can only appear as sealed and
nothing of it is read. Statuses and reasons below are the admission lane's current record.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path


class Refused(RuntimeError):
    pass


def need(condition, message):
    """An explicit guard that survives `python -O` (review I3); asserts are not used for refusals here."""
    if not condition:
        raise Refused(message)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT_MD = ROOT / "docs/evidence/corpus-tally.md"
OUT_JSON = HERE / "tally.json"
DENYLIST_SHA256 = "57cfe01f29f6e1a55293f968ec697aa293c268bd87d7cf247ef648279e2fba7c"   # pinned (review I3)

ROWS = [
    dict(session="20260922T032454-642Z-24328-1", date="2026-09-21", status="pending",
         reason="whole-session intake not yet run (28.7 s of focused logged input)", regime="normal", focused_min=0.478),
    dict(session="20260922T033319-205Z-24328-2", date="2026-09-21", status="held",
         reason="override; permanently unadmitted", regime=None, focused_min=6.933),
    dict(session="20260923T053616-779Z-33696-2", date="2026-09-23", status="sealed", reason="validation take; never read"),
    dict(session="20260923T053929-795Z-33696-3", date="2026-09-23", status="not_range", reason="calibration take"),
    dict(session="20260923T054325-507Z-33696-4", date="2026-09-23", status="not_range",
         reason="DayMR native replay viewing, not logged play"),
    dict(session="20260923T200129-346Z-33696-6", date="2026-09-23", status="pending",
         reason="segments-evidence and owner verdicts ready (owner-provisional counted 26.62 min; two deaths cut); "
                "independent per-session review next", regime="normal", focused_min=26.779),
    dict(session="20260923T203716-726Z-45572-1", date="2026-09-23", status="not_range",
         reason="7.4 s HEVC encoder test (anchor holds, hevc-check.md)"),
    dict(session="20260923T204707-487Z-45572-2", date="2026-09-23", status="not_range",
         reason="settings and calibration take (settings pages, 360-degree turn, pitch sweep)"),
    dict(session="20260923T205528-900Z-45572-3", date="2026-09-23", status="pending",
         reason="campaign take 2 (HEVC): segments-evidence and owner verdicts ready (owner-provisional counted 11.07 "
                "min); independent per-session review next", regime="normal", focused_min=11.076),
]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


ADMITTED = ("20260923T051828-422Z-33696-1", "20260923T171533-187Z-33696-5")


def admitted_row(hi, session):
    d = HERE / session
    need(hi.check_freeze(d, root=ROOT) == [], f"{session} freeze check fails")
    m = json.loads((d / "minutes.json").read_text())
    return dict(session=m["session"], date="2026-09-23", status="admitted",
                reason="assembled: review.json from the owner and independent verdicts, imported, steps file frozen",
                regime=m["regime"], focused_min=m["focused_s"] / 60, admitted_min=m["counted"]["counted_minutes"],
                trainable_min=m["trainable_minutes"], stride_ns=m["stride_ns"], rejected_min=m["rejected_s"] / 60,
                unresolved_min=m["unresolved_s"] / 60, tags_s=m["tags_s"],
                artifact_sha256=sha(d / "artifact-hashes.json"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default="code-snapshot-23c8482")
    args = ap.parse_args()
    sys.path.insert(0, str(HERE / args.snapshot))
    from agent import human_intake as hi
    denylist = hi.load_denylist(ROOT / "data/human/sealed-denylist.json", sha256_pin=DENYLIST_SHA256)
    registry = hi.check_registry(ROOT / "data/human/session-splits.corpus.json", denylist=denylist)
    rows = [dict(r) for r in ROWS] + [admitted_row(hi, x) for x in ADMITTED]
    for r in rows:
        place = registry.get(r["session"])
        r.update(group=place.session_group if place else None, split=place.split if place else None)
    rows.sort(key=lambda r: r["session"])
    t = hi.tally(rows, denylist=denylist)
    t.update(registry={"path": "data/human/session-splits.corpus.json", "sha256": sha(ROOT / "data/human/session-splits.corpus.json")},
             denylist={"path": "data/human/sealed-denylist.json", "sha256": sha(ROOT / "data/human/sealed-denylist.json")},
             snapshot=args.snapshot, counted_rule="focused logged time ∩ accepted segments ∩ gap-free runs >= 1.6 s")
    OUT_JSON.write_text(json.dumps(t, indent=1) + "\n", encoding="utf-8", newline="\n")
    head = ("# Corpus tally (whole-session intake, VUH-1359)\n\n"
            "Generated by `data/human/sessions/tally.py` from `data/human/sessions/tally.json`; do not edit by hand.\n"
            "Minutes are **counted minutes**: focused logged time ∩ accepted segments ∩ gap-free runs of at least "
            "1.6 s, never video length. Only admitted train/val sessions count. The 3-hour trigger is the per-regime "
            "train headline. Trainable minutes (eligible anchors × stride) are added once a session is imported, "
            "always with its stride.\n\n")
    provisional = [r for r in rows if r.get("provisional_counted_min") is not None]
    tail = "".join(f"\nProvisional (not counted): {r['session']} {r['provisional_counted_min']:.2f} min, owner "
                   "verdicts only.\n" for r in provisional)
    OUT_MD.write_text(head + hi.render_tally(t) + tail, encoding="utf-8", newline="\n")
    print(sha(OUT_JSON), sha(OUT_MD))
    print(hi.render_tally(t))


if __name__ == "__main__":
    main()
