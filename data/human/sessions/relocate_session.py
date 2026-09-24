"""Record a verified transcode for an assembled session (media relocation); the original stays the identity.

    python relocate_session.py SESSION_ID --receipt PATH/<stem>.transcode.json --snapshot code-snapshot-XXXXXXX [--reprobe]

Refuses unless the receipt (scripts/transcode_recording.py) is clean, names this session and its frozen original
sha256, and pins the same logger files the session froze. Writes `media-relocation.json` beside the session's
artefacts, proves the session still loads through `load_dataset_relocated` (with `--reprobe` also decoding the
transcode and comparing its PTS with the import), and re-freezes as a new version: the previous
`artifact-hashes.json` is kept as `.vN` and pinned. Only after this may the original be deleted. It never transcodes
and never deletes anything.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DENYLIST = ROOT / "data/human/sealed-denylist.json"
DENYLIST_SHA256 = "57cfe01f29f6e1a55293f968ec697aa293c268bd87d7cf247ef648279e2fba7c"   # pinned (review I3)
REGISTRY = ROOT / "data/human/session-splits.corpus.json"
RAW = Path("C:/Users/volpe/Videos/RivalsInput")


class Refused(RuntimeError):
    pass


def need(condition, message):
    if not condition:
        raise Refused(message)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("session")
    ap.add_argument("--receipt", required=True)
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--reprobe", action="store_true")
    args = ap.parse_args()
    sys.path.insert(0, str(HERE / args.snapshot))
    from agent import human_intake as hi
    denylist = hi.load_denylist(DENYLIST, sha256_pin=DENYLIST_SHA256)
    registry = hi.check_registry(REGISTRY, denylist=denylist)
    need(args.session in registry, "session not registered")
    d = HERE / args.session
    need(hi.check_freeze(d, root=ROOT) == [], "the session's current freeze must check clean first")
    header = json.loads((d / "imported-demo.jsonl").open(encoding="utf-8").readline())
    identity = header["media_sha256"]
    hi.assert_not_sealed(args.session, identity, denylist)
    receipt = json.loads(Path(args.receipt).read_text(encoding="utf-8"))
    for name in ("metadata.json", "frames.csv", "inputs.jsonl"):
        need(receipt.get("session_files", {}).get(name, {}).get("sha256") == hi.sha256(RAW / args.session / name),
             f"the receipt's {name} is not this session's logger file")
    record = hi.relocation_record(args.receipt, session_id=args.session, identity_sha256=identity)
    need(not (d / hi.RELOCATION_FILE).exists(), "a relocation is already recorded")
    ds = hi.load_dataset_relocated(d / "imported-demo.jsonl", splits=REGISTRY, denylist=denylist, relocation=record,
                                   reprobe=args.reprobe)
    need(ds.media_sha256 == identity, "identity changed")
    (d / hi.RELOCATION_FILE).write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8", newline="\n")
    version = 1
    while (d / f"artifact-hashes.v{version}.json").exists():
        version += 1
    previous = d / f"artifact-hashes.v{version}.json"
    (d / "artifact-hashes.json").rename(previous)
    old = json.loads(previous.read_text(encoding="utf-8"))
    external = [ROOT / k if not Path(k).is_absolute() else Path(k) for k in old["external"]]
    external = [p for p in external if p.is_file() or p.as_posix() == Path(record["original_path"]).as_posix()]
    doc = hi.freeze(d, root=ROOT, external=[p for p in external if p.is_file()] + [record["transcoded_path"],
                                                                                  record["receipt"]["path"]],
                    extra=dict(session=args.session, status="assembled", relocated=True,
                               supersedes={previous.name: hi.sha256(previous)},
                               identity_sha256=identity, transcoded_sha256=record["transcoded_sha256"]))
    print("relocation recorded; freeze", hi.sha256(d / "artifact-hashes.json"), "check", hi.check_freeze(d, root=ROOT),
          "frames", len(ds.frames))


if __name__ == "__main__":
    main()
