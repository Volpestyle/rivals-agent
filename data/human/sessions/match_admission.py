"""Write a PENDING `rivals-idm-match-admission-v1` receipt for assembled live matches (match mode, lead 2026-09-27).

    python match_admission.py SESSION_ID [SESSION_ID ...] --snapshot code-snapshot-XXXXXXX --out PATH

Per session it pins what policy/idm/match_targets.py checks: the registered media hash and family, the frozen step
table, the imported demo, the canonical motor/calibration identity of the step header, and the session's motor record
(motor-settings.json, which quotes James's dated statement verbatim). Every session must be registered idm_train, not
training_pending, not a replay (no `pair`), not sealed, and its assembly freeze must check clean. The producer never
accepts its own receipt: `decision` is "pending" and `reviewer` is null. The independent reviewer writes the accepted
copy, and the run pins that copy's hash.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path


class Refused(RuntimeError):
    pass


def need(condition, message):
    """An explicit guard that survives `python -O`; asserts are not used for refusals here."""
    if not condition:
        raise Refused(message)


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DENYLIST = ROOT / "data/human/sealed-denylist.v2.json"
DENYLIST_SHA256 = "439c80df6cd5d6daa60b48e0acb2d3a3fa833134ff14edddc4121348c2dceb20"   # pinned (review I3)
REGISTRY = ROOT / "data/human/session-splits.corpus.json"
FORMAT = "rivals-idm-match-admission-v1"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def entry(session, *, sessions_dir, rows, hi, digest, identity):
    """One session's receipt entry, after every refusal check."""
    row = rows.get(session)
    need(row is not None and row.get("split") == "idm_train", f"{session}: not registered idm_train")
    need(not row.get("training_pending"), f"{session}: training_pending ({row.get('training_pending')})")
    need(not row.get("pair") and row.get("session_group") == session, f"{session}: a replay or another family's file")
    d = sessions_dir / session
    need(hi.check_freeze(d, root=ROOT) == [], f"{session}: assembly freeze does not check clean")
    steps, demo, motor = d / f"{session}.steps.jsonl", d / "imported-demo.jsonl", d / "motor-settings.json"
    need(motor.is_file(), f"{session}: no motor-settings.json (the motor step's record of James's dated statement)")
    with steps.open(encoding="utf-8") as fh:
        header = json.loads(fh.readline())
    need(header["session_id"] == session and header["split"] == "idm_train", f"{session}: step header role")
    need(header["media_sha256"] == row["expected_media_sha256"], f"{session}: step media differs from the registry")
    need(header["source"]["imported_demo_sha256"] == sha(demo), f"{session}: demo differs from the step table's pin")
    return dict(source_kind="live", session_group=row["session_group"], media_sha256=row["expected_media_sha256"],
                steps_sha256=sha(steps), imported_demo_sha256=sha(demo), identity_sha256=digest(identity(header)),
                motor_statement_sha256=sha(motor))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sessions", nargs="+")
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    snapshot = HERE / args.snapshot
    sys.path.insert(0, str(snapshot))
    from agent import human_intake as hi
    from policy.idm.match_targets import digest, identity
    denylist = hi.load_denylist(DENYLIST, sha256_pin=DENYLIST_SHA256)
    hi.check_registry(REGISTRY, denylist=denylist)                    # denylist first, then the registry
    rows = {r["session_id"]: r for r in json.loads(REGISTRY.read_text(encoding="utf-8"))["sessions"]}
    for s in args.sessions:
        hi.assert_not_sealed(s, rows.get(s, {}).get("expected_media_sha256"), denylist)
    out = Path(args.out)
    need(not out.exists(), f"{out} already written")
    doc = dict(format=FORMAT, scope="EXPLORATORY", decision="pending", reviewer=None,
               producer="admission-owner (data/human/sessions/match_admission.py)", snapshot=args.snapshot,
               snapshot_manifest_sha256=sha(snapshot / "manifest.json"),
               registry={"path": "data/human/session-splits.corpus.json", "sha256": sha(REGISTRY)},
               sessions={s: entry(s, sessions_dir=HERE, rows=rows, hi=hi, digest=digest, identity=identity)
                         for s in args.sessions})
    out.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(out, sha(out))


if __name__ == "__main__":
    main()
