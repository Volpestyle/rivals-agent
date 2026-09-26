"""Regenerate ONE events file without letting its content reach whoever runs it.

    uv run --group perception python scripts/regenerate_sealed.py data/demos/events/sections/<source>.jsonl

For a source under sealed handling (docs/plan.md, "Sealed test data": the
sealed-migration ruling on VUH-1326): the file is rebuilt by the unchanged writer from its own recorded
recipe (`from_video`, patch resolved as it always is), and everything the job
says -- progress, warnings, alarms, tracebacks, ffmpeg -- goes to a log under
data/demos/migration-format5/sealed-logs/ that nobody reads (mode 600). The only
output is one line: source id, written yes/no, format, writer fingerprint,
check pass/fail. A failure prints the same line with written no and check fail;
its reason stays in the log.
"""
import json
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "data/demos/migration-format5/sealed-logs"


def main(argv):
    path = Path(argv[1]).resolve()
    source = path.stem
    LOGS.mkdir(parents=True, exist_ok=True)
    log = LOGS / f"{source}.log"
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    os.chmod(log, 0o600)
    status = os.dup(1)                       # the one line goes here
    sys.stdout.flush()
    sys.stderr.flush()
    os.dup2(fd, 1)                           # everything else, subprocesses too, goes to the log
    os.dup2(fd, 2)
    written, fmt, writer, ok = "no", "-", "-", "fail"
    try:
        sys.path.insert(0, str(ROOT))
        os.chdir(ROOT)
        from perception.events import check, from_video

        before = path.stat().st_mtime_ns
        recipe = json.loads(path.open().readline())["recipe"]
        from_video(recipe["video"], path, recipe["hz"], recipe.get("start"), recipe.get("duration"),
                   recipe["layout"], patch=recipe.get("patch"), patch_from=recipe.get("patch_from"))
        written = "yes" if path.stat().st_mtime_ns != before else "no"
        meta = json.loads(path.open().readline())
        fmt, writer = str(meta.get("format")), str(meta.get("writer"))
        stale = [p for p, _ in check(path.parent) if Path(p).resolve() == path]
        parses = all(json.loads(line) is not None for line in path.open() if line.strip())
        ok = "pass" if written == "yes" and not stale and parses else "fail"
    except BaseException:                    # noqa: BLE001 -- the reason belongs in the log only
        traceback.print_exc()
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
    os.write(status, f"{source} written={written} format={fmt} writer={writer} check={ok}\n".encode())
    return 0 if ok == "pass" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
