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
DENYLIST_SHA256 = "439c80df6cd5d6daa60b48e0acb2d3a3fa833134ff14edddc4121348c2dceb20"   # pinned (review I3)

ROWS = [
    dict(session="20260922T032454-642Z-24328-1", date="2026-09-21", status="held",
         reason="at most 11.0-22.28 s admissible (normal play before the first Esc, <= 0.19 counted min); before it "
                "loading and selection, after it the settings menu (R3) and No Ability Cooldown ON from 23.7 s; "
                "intake only on request", regime="normal", focused_min=0.478),
    dict(session="20260922T033319-205Z-24328-2", date="2026-09-21", status="held",
         reason="permanently unadmitted (lead): regime unresolved, no depletion in inspected windows against James's "
                "cooldowns-OFF report (R5: note and scan disagree); stays out", regime=None, focused_min=6.933),
    dict(session="20260923T053616-779Z-33696-2", date="2026-09-23", status="sealed", reason="validation take; never read"),
    dict(session="20260923T053929-795Z-33696-3", date="2026-09-23", status="not_range", reason="calibration take"),
    dict(session="20260923T054325-507Z-33696-4", date="2026-09-23", status="not_range",
         reason="DayMR native replay viewing, not logged play"),
    dict(session="20260923T203716-726Z-45572-1", date="2026-09-23", status="not_range",
         reason="7.4 s HEVC encoder test (anchor holds, hevc-check.md)"),
    dict(session="20260923T204707-487Z-45572-2", date="2026-09-23", status="not_range",
         reason="settings and calibration take (settings pages, 360-degree turn, pitch sweep)"),
    dict(session="20260925T030045-211Z-7804-3", date="2026-09-24", status="not_range",
         reason="multi-speed calibration take (four yaw speed classes, pitch sweeps): data/human/calibration/"),
    *[dict(session=s, date="2026-09-25", status="not_range",
           reason="OBS false start (4-15 s) before a take; James deleted the video; not a session")
      for s in ("20260925T200851-935Z-49728-1", "20260925T212548-665Z-49728-3", "20260925T212615-212Z-49728-4",
                "20260925T212626-543Z-49728-5")],
    *[dict(session=m, date="2026-09-25", status="not_range",
           reason="evaluation-only match recording (reader_validation, reader_development or match_dev), never trained on "
                  "(handoff/matches-0925.md)")
      for m in ("20260926T005304-628Z-63684-4", "20260926T010620-721Z-63684-5", "20260926T012552-291Z-63684-6",
                "20260926T013711-125Z-63684-7", "20260926T015610-960Z-63684-8", "20260926T021321-378Z-63684-9",
                "20260926T034805-307Z-63684-13")],
    *[dict(session=s, date="2026-09-26", status="not_range", reason=reason) for s, reason in (
        ("20260926T161008-331Z-116800-2", "reader_development: the replay of the Heart of Heaven match (20-06-20), never "
                                          "trained on"),
        ("20260926T162648-153Z-116800-4", "leftward yaw calibration take (calibration_sessions); never a split"),
        ("20260926T162623-219Z-116800-3", "OBS false start (13 s, Alt+Tab only); James deleted the video; not a session"),
        ("20260926T060921-977Z-60612-1", "main-account yaw calibration take (calibration_sessions); never a split"),
    )],
    *[dict(session=s, date=d, status="sealed", reason=reason) for s, d, reason in (
        ("20260926T002109-428Z-63684-2", "2026-09-25", "gate2 pair 1 (sealed): the live match (Central Park, 19:28); never read"),
        ("20260926T044958-507Z-63684-15", "2026-09-25", "gate2 pair 1 (sealed): its replay; never read"),
        ("20260926T002851-659Z-63684-3", "2026-09-25", "gate2 pair 2 (sealed): the live half (Thebes 19:36 and Hall of Djalia "
                                                      "19:49; the whole file); never read"),
        ("20260926T155737-285Z-116800-1", "2026-09-26", "gate2 pair 2 (sealed): the Hall of Djalia replay; never read"))],
    *[dict(session=s, date="2026-09-26", status="sealed", reason=reason) for s, reason in (
        ("20260926T153835-237Z-111496-2", "test take 2026-09-26 (James, 16 min); never read"),
        ("20260926T153812-936Z-111496-1", "held with the 2026-09-26 test take (23 s, same OBS process); never read"))],
    *[dict(session=s, date="2026-09-25", status="pending", reason="logger folder without a video; not opened")
      for s in ("20260925T234952-361Z-63684-1", "20260926T022734-732Z-63684-10", "20260926T031019-828Z-63684-11",
                "20260926T033121-111Z-63684-12")],
]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


ADMITTED = ("20260923T051828-422Z-33696-1", "20260923T171533-187Z-33696-5", "20260923T200129-346Z-33696-6",
            "20260923T205528-900Z-45572-3", "20260924T232304-170Z-12024-1", "20260925T025230-605Z-7804-2",
            "20260925T021320-371Z-7804-1", "20260925T212646-322Z-49728-6",
            "20260925T203745-207Z-49728-2", "20260926T045729-166Z-79780-1",
            "20260926T035932-508Z-63684-14")   # 212646 is val: beside the headline


def recording_date(session):
    """The recording's date in America/Chicago (assemble_session.chicago_date), from the recorder's started_utc."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("assemble_session", HERE / "assemble_session.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    started = json.loads((HERE / session / "provenance.json").read_text())["metadata"]["started_utc"]
    from datetime import datetime
    return module.chicago_date(datetime.fromisoformat(started.replace("Z", "+00:00")))


def admitted_row(hi, session):
    d = HERE / session
    need(hi.check_freeze(d, root=ROOT) == [], f"{session} freeze check fails")
    m = json.loads((d / "minutes.json").read_text())
    return dict(session=m["session"], date=recording_date(session), status="admitted",
                reason="assembled: review.json from the owner and independent verdicts, imported, steps file frozen",
                regime=m["regime"], focused_min=m["focused_s"] / 60, admitted_min=m["counted"]["counted_minutes"],
                trainable_min=m["trainable_minutes"], stride_ns=m["stride_ns"], rejected_min=m["rejected_s"] / 60,
                unresolved_min=m["unresolved_s"] / 60, tags_s=m["tags_s"],
                artifact_sha256=sha(d / "artifact-hashes.json"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default="code-snapshot-86a1912")
    args = ap.parse_args()
    sys.path.insert(0, str(HERE / args.snapshot))
    from agent import human_intake as hi
    denylist = hi.load_denylist(ROOT / "data/human/sealed-denylist.v2.json", sha256_pin=DENYLIST_SHA256)
    registry = hi.check_registry(ROOT / "data/human/session-splits.corpus.json", denylist=denylist)
    rows = [dict(r) for r in ROWS] + [admitted_row(hi, x) for x in ADMITTED]
    for r in rows:
        place = registry.get(r["session"])
        r.update(group=place.session_group if place else None, split=place.split if place else None)
    rows.sort(key=lambda r: r["session"])
    t = hi.tally(rows, denylist=denylist)
    t.update(registry={"path": "data/human/session-splits.corpus.json", "sha256": sha(ROOT / "data/human/session-splits.corpus.json")},
             denylist={"path": "data/human/sealed-denylist.v2.json", "sha256": sha(ROOT / "data/human/sealed-denylist.v2.json")},
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
