"""Rewrite an assembled session's step file for the current fit vocabulary (a new version; review and import unchanged).

    python restep_session.py SESSION_ID --reason TEXT --snapshot code-snapshot-XXXXXXX

The identity still comes from the session's own `review.json` (`write_steps` derives it; review I1), so only the action
list and what it routes change. The previous step file, sampling record and freeze are kept renamed `.vN` and pinned
by the new freeze's `supersedes`. Refuses unless the current freeze checks clean and the accepted row set is unchanged.
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("assemble_session", HERE / "assemble_session.py")
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("session")
    ap.add_argument("--reason", required=True)
    ap.add_argument("--snapshot", required=True)
    args = ap.parse_args()
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
    snapshot = HERE / args.snapshot
    sys.path.insert(0, str(snapshot))
    from agent import human_intake as hi
    from agent import human_demos as hd
    denylist = hi.load_denylist(A.DENYLIST, sha256_pin=A.DENYLIST_SHA256)
    hi.check_registry(A.REGISTRY, denylist=denylist)
    d = HERE / args.session
    A.need(hi.check_freeze(d, root=A.ROOT) == [], "the current freeze must check clean before a new version")
    version = 1
    while (d / f"artifact-hashes.v{version}.json").exists():
        version += 1
    steps = d / f"{args.session}.steps.jsonl"
    renamed = {}
    for path, target in ((steps, d / f"{args.session}.steps.v{version}.jsonl"), (d / "sampling.json", d / f"sampling.v{version}.json"),
                         (d / "artifact-hashes.json", d / f"artifact-hashes.v{version}.json")):
        A.need(not target.exists(), f"{target.name} exists")
        renamed[path.name] = {"to": target.name, "sha256": A.sha(path)}
        path.rename(target)
    dataset = hd.load_dataset(d / "imported-demo.jsonl", splits=A.REGISTRY)
    old_header = json.loads((d / f"{args.session}.steps.v{version}.jsonl").open(encoding="utf-8").readline())
    reg_rows = {r["session_id"]: r for r in json.loads(A.REGISTRY.read_text())["sessions"]}
    header, n = hi.write_steps(dataset, steps, sitting=reg_rows[args.session]["sitting"], calibration=old_header["calibration"],
                               denylist=denylist, step_ns=old_header["step_ns"],
                               settings_hash=old_header["settings_hash"], patch=old_header["patch"],
                               source=dict(old_header.get("source") or {}, snapshot=args.snapshot,
                                           snapshot_manifest_sha256=A.sha(snapshot / "manifest.json"), version=version + 1))
    table = [json.loads(x) for x in steps.read_text(encoding="utf-8").splitlines()[1:]]
    accepted = [r for r in table if r["suitability"] == "accepted"]
    eligible = [r for r in accepted if r["gap_free"]]
    minutes = json.loads((d / "minutes.json").read_text())
    A.need(len(eligible) == minutes["eligible_anchors"], "the accepted row set changed")
    A.write_json(d / "sampling.json", dict(session=args.session, format=header["format"], step_ns=header["step_ns"],
                                           frame_period_ns=header["frame_period_ns"], rows=n, accepted_rows=len(accepted),
                                           eligible_rows=len(eligible), steps={"path": steps.name, "sha256": A.sha(steps)},
                                           export_digest=A.sha(steps), version=version + 1, actions=header["actions"]))
    old = json.loads((d / f"artifact-hashes.v{version}.json").read_text())
    external = [A.ROOT / k if not Path(k).is_absolute() else Path(k) for k in old["external"]]
    external = [p for p in external if p.is_file() and p.name != "manifest.json"] + [snapshot / "manifest.json"]
    hi.freeze(d, root=A.ROOT, external=external,
              extra=dict({k: v for k, v in old.items() if k not in ("format", "files", "external", "supersedes")},
                         version=version + 1, snapshot=args.snapshot,
                         supersedes=dict(reason=args.reason, renamed=renamed)))
    print("version", version + 1, "rows", n, "actions", len(header["actions"]), "steps", A.sha(steps),
          "freeze", A.sha(d / "artifact-hashes.json"), "check", hi.check_freeze(d, root=A.ROOT))


if __name__ == "__main__":
    main()
