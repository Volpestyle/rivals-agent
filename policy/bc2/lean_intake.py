"""Lean intake of one new James take into a policy step table, without the admission lane's review ceremony.

Uses the admission tooling unchanged (agent.human_demos.import_session, agent.human_intake.write_steps) with:
- a private registry copy (the shared corpus registry plus this take's row), never the shared file;
- a minimal review: one accepted segment over the focused recording after a 250 ms settle, James's standing
  motor settings and bindings from the last admitted session, the standard muxer anchor, and every assumption
  written into the review's sources (motor statement pending, patch assumed, regime from James's statement).
Outputs go under <out>/<session>/ only: registry.json, review.json, imported-demo.jsonl, <session>.steps.jsonl.

    python -m policy.bc2.lean_intake <session_id> --video <mkv> --out D:/rivals-policy/intake \
        --template data/human/sessions/<admitted session>
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = Path("C:/Users/volpe/Videos/RivalsInput")
STEP_NS = 33_333_333
SETTLE_NS = 250_000_000


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("session_id")
    p.add_argument("--video", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--template", required=True, help="an admitted session dir whose review provides motor/bindings")
    p.add_argument("--sitting", default=None)
    p.add_argument("--regime", default="normal")
    p.add_argument("--note", default="lean intake (policy lane, VUH-1346); lead-approved lean mode, no review ceremony")
    a = p.parse_args(argv)
    from agent import human_demos as hd
    from agent import human_intake as hi
    from policy.range_bc import steps
    sid = a.session_id
    out = Path(a.out) / sid
    out.mkdir(parents=True, exist_ok=True)
    meta = json.loads((RAW / sid / "metadata.json").read_text())
    if meta["video_path"].replace("\\", "/") != a.video.replace("\\", "/"):
        raise SystemExit("video path differs from the logger metadata")

    # Private registry: the shared rows plus this take (split train; session_group == session_id).
    shared = json.loads((ROOT / "data/human/session-splits.corpus.json").read_text())
    if any(s["session_id"] == sid for s in shared["sessions"]):
        raise SystemExit("already registered in the shared registry; use the admission path")
    sitting = a.sitting or meta["started_utc"][:10] + "-lean"
    row = {"session_id": sid, "session_group": sid, "split": "train", "video_path": a.video,
           "split_basis": a.note, "sitting": sitting, "obs_process": int(sid.split("-")[-2])}
    registry = dict(shared, sessions=shared["sessions"] + [row])
    (out / "registry.json").write_text(json.dumps(registry, indent=2) + "\n")

    template = json.loads((Path(a.template) / "review.json").read_text())
    prov = template["provenance"]
    assumption = f"{a.note}: assumed unchanged from {template['session_id']} (James's motor statement for this take is pending)"
    review = {
        "schema_version": 1, "session_id": sid, "reviewer": "policy lane (lean intake, no independent review)",
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "device_scope": {"kind": "single_keyboard_mouse", "source": assumption},
        "pts_anchor": {k: template["pts_anchor"][k] for k in ("kind", "offset_num", "offset_den")}
        | {"source": f"standard muxer offset as in {template['session_id']}; {a.note}"},
        "provenance": {
            "hero": "Spider-Man",
            "settings": {"value": prov["settings"]["value"], "source": assumption},
            "bindings": {"value": prov["bindings"]["value"], "source": assumption},
            "game_patch": {"value": prov["game_patch"]["value"],
                           "source": f"assumed the same build as {template['session_id']} ({a.note})"},
            "cooldown_regime": {"value": a.regime, "source": "James's statement for this take (docs/recording-log.md)"},
        },
        "alignment": template.get("alignment"),
        "segments": [{"segment_id": "seg-000", "start_ns": meta["start_ns"] + SETTLE_NS, "end_ns": meta["end_ns"],
                      "reviewed_gameplay": True, "imitation_suitability": "accepted",
                      "suitability_reason": "whole take accepted without frame review (start-from-still recipe take)",
                      "evidence": a.note}],
    }
    (out / "review.json").write_text(json.dumps(review, indent=2) + "\n")

    dataset = hd.import_session(RAW / sid, review=out / "review.json", splits=out / "registry.json",
                                output=out / "imported-demo.jsonl")
    calibration = json.loads((ROOT / "data/human/calibration/20260923T204707-487Z-45572-2/calibration.json")
                             .read_text())["header_calibration"]
    steps_path = out / f"{sid}.steps.jsonl"
    hi.write_steps(dataset, steps_path, sitting=sitting, calibration=calibration,
                   denylist=hi.load_denylist(ROOT / "data/human/sealed-denylist.v2.json",
                                             sha256_pin=steps.DENYLIST_SHA256), step_ns=STEP_NS,
                   regime=a.regime, source={"lean_intake": a.note, "template": template["session_id"]})
    print(json.dumps({"steps": str(steps_path), "rows": sum(1 for _ in steps_path.open()) - 1}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
