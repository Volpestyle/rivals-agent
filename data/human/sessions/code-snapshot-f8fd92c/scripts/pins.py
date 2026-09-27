"""The five identity-pinned runtime files: print their closure, or refuse an undeclared commit to them.

  uv run python scripts/pins.py closure [--json]      # `just closure`
  python scripts/pins.py commit-msg <message-file>    # the pre-commit commit-msg hook (.pre-commit-config.yaml)

Checkpoint bindings pin these files' bytes. Receipts record two forms because the PC checks out CRLF
(core.autocrlf) while git and the Mac hold LF: `LF_normalized_sha256` and `CRLF_blob_sha256`, as in
data/runtime/galacta-pilot-20260923-preflight/controller-deployed.json. `closure` prints both, the git
blob id, and whether the working file still matches HEAD.

A commit that changes one of them is refused unless its message carries a `DECLARATION:` trailer saying
why and which binding it invalidates. A merge is checked only for bytes that neither parent had (a
conflict resolution); the branch commits that made the change carried their own declarations.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

PINNED = ("perception/hud.py", "perception/outline.py", "agent/loop.py", "agent/brain.py", "agent/tracker.py")
TRAILER = "DECLARATION"


def git(*args, check=True):
    return subprocess.run(("git", *args), capture_output=True, text=True, check=check).stdout


def closure(root):
    rows = []
    for rel in PINNED:
        lf = (root / rel).read_bytes().replace(b"\r\n", b"\n")
        blob = hashlib.sha1(b"blob %d\0" % len(lf) + lf).hexdigest()   # what `git hash-object` gives the LF bytes
        rows.append({"path": rel, "git_blob": blob,
                     "LF_normalized_sha256": hashlib.sha256(lf).hexdigest(),
                     "CRLF_blob_sha256": hashlib.sha256(lf.replace(b"\n", b"\r\n")).hexdigest(),
                     "matches_HEAD": blob == git("rev-parse", f"HEAD:{rel}", check=False).strip()})
    return rows


def touched():
    """Pinned paths this commit changes: the index against HEAD, and for a merge only bytes new to both parents."""
    changed = set(git("diff", "--cached", "--name-only", "--no-renames", "--", *PINNED).split())
    merging = subprocess.run(("git", "rev-parse", "-q", "--verify", "MERGE_HEAD"), capture_output=True).returncode == 0
    if merging and changed:
        changed &= set(git("diff", "--cached", "--name-only", "--no-renames", "MERGE_HEAD", "--", *PINNED).split())
    return sorted(changed)


def declared(message_file):
    """True when the message carries a non-empty DECLARATION: trailer (git's own trailer parsing)."""
    for line in git("interpret-trailers", "--parse", message_file).splitlines():
        key, _, value = line.partition(":")
        if key.strip().upper() == TRAILER and value.strip():
            return True
    return False


def commit_msg(message_file):
    paths = touched()
    if not paths or declared(message_file):
        return 0
    print("Refused: this commit changes identity-pinned file(s):", *(f"  {p}" for p in paths), sep="\n", file=sys.stderr)
    print("Checkpoint bindings pin their bytes (run `just closure`). If the change is intended, end the message\n"
          "with a trailer in the same block as Co-Authored-By, for example:\n"
          f"  {TRAILER}: agent/loop.py changes <what>; binding <which> must be re-issued (VUH-NNNN)", file=sys.stderr)
    return 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("closure").add_argument("--json", action="store_true")
    sub.add_parser("commit-msg").add_argument("message_file")
    a = ap.parse_args(argv)
    if a.command == "commit-msg":
        return commit_msg(a.message_file)
    rows = closure(Path(git("rev-parse", "--show-toplevel").strip()))
    if a.json:
        print(json.dumps(rows, indent=2))
    else:
        for r in rows:
            print(f"{r['path']:22} blob {r['git_blob']}  LF {r['LF_normalized_sha256']}  "
                  f"CRLF {r['CRLF_blob_sha256']}  {'= HEAD' if r['matches_HEAD'] else 'CHANGED vs HEAD'}")
    return 0 if all(r["matches_HEAD"] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
