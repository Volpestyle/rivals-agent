"""Prepare finished input-logger sessions for intake: hash the video, add a recording-log row, print the command.

  uv run python scripts/recording_watch.py                     # poll ~/Videos/RivalsInput every 60 s (the PC)
  uv run python scripts/recording_watch.py --once --dry-run    # one pass; print rows, write nothing

A session is ready when its metadata.json says `complete: true` and the video it names has stopped changing.
This script only prepares. It reads metadata.json and the video's bytes, and nothing else: never inputs.jsonl
or frames.csv, never a decode, never a write under Videos/. It registers, splits, seals and imports nothing;
that is the admission lane's (docs/human-demo-schema.md, docs/machines.md "Record on Windows, import on the
Mac"). A take James calls a validation take is sealed there before anything reads its content.

The row goes into the table in docs/recording-log.md. Content and Cooldowns are left for the lead to fill
from what James says; the intake status column carries what the logger reported and the video's sha256 (the
`expected_media_sha256` a Mac registry needs). A session whose id is already in the log is skipped, so
re-runs and restarts are safe. The log edit is left uncommitted for the lead.
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "docs" / "recording-log.md"
HEADER = "| Video (Videos/) | Logger session |"
INTAKE = ('uv run python scripts/import_human_demo.py import --session "{session}" --review <review.json> '
          '--splits <session-splits.json> --output <imported-demo.jsonl>')


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def settled(video, settle_s):
    """The video exists and its size and mtime did not change over settle_s."""
    try:
        before = video.stat()
        time.sleep(settle_s)
        after = video.stat()
    except OSError:
        return False
    return (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)


def row(meta, video, digest):
    minutes = (int(meta["end_ns"]) - int(meta["start_ns"])) / 60e9
    logger = ", ".join((
        "logger complete" if meta.get("status") == "complete" else f"logger status {meta.get('status')!r}",
        "clean stop" if meta.get("clean_stop") is True else "NOT a clean stop",
        f"{meta.get('queue_dropped_events')} drops", f"{meta.get('raw_input_errors')} raw-input errors"))
    return (f"| {video.name} | {meta['session_id']} | {minutes:.1f} min | (lead: from James) | (lead: from James) "
            f"| {logger}; video sha256 `{digest}`; intake pending |")


def insert(text, line):
    """Add `line` after the last row of the recording table, keeping the file's own line endings."""
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(newline)
    start = next((i for i, s in enumerate(lines) if s.startswith(HEADER)), None)
    if start is None:
        raise SystemExit(f"{LOG}: no table starting {HEADER!r}; nothing written")
    end = start
    while end + 1 < len(lines) and lines[end + 1].startswith("|"):
        end += 1
    return newline.join(lines[:end + 1] + [line] + lines[end + 1:])


def read_log():
    with open(LOG, encoding="utf-8", newline="") as handle:     # keep the checkout's own line endings
        return handle.read()


def scan(root, settle_s, dry_run):
    log = read_log()
    for meta_path in sorted(root.glob("*/metadata.json")):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue                                   # still being written: next pass
        if meta.get("complete") is not True or not meta.get("session_id") or meta["session_id"] in log:
            continue
        video = Path(meta.get("video_path", ""))
        if not video.is_file():
            print(f"{meta['session_id']}: video {video} not found; will retry", file=sys.stderr)
            continue
        if not settled(video, settle_s):
            continue
        before = video.stat()
        digest = sha256(video)
        after = video.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            continue                                   # changed while hashing: next pass
        line = row(meta, video, digest)
        if dry_run:
            print(line)
        else:
            log = insert(read_log(), line)
            with open(LOG, "w", encoding="utf-8", newline="") as handle:
                handle.write(log)
            print(f"{LOG.relative_to(ROOT)}: added {meta['session_id']}")
        print(f"  recorded_video_path: {meta['video_path']}\n  expected_media_sha256: {digest}\n"
              f"  when the admission lane has registered and reviewed it:\n    {INTAKE.format(session=meta_path.parent)}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=Path.home() / "Videos" / "RivalsInput")
    ap.add_argument("--every", type=float, default=60.0, help="seconds between passes")
    ap.add_argument("--settle", type=float, default=10.0, help="seconds the video must stay unchanged")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="print rows; write nothing")
    a = ap.parse_args(argv)
    while True:
        scan(a.root, a.settle, a.dry_run)
        if a.once:
            return 0
        time.sleep(a.every)


if __name__ == "__main__":
    sys.exit(main())
