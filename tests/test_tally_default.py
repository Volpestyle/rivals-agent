"""tally.py's default snapshot (2026-09-26): it validates the live registry, and it reproduces the committed tally.

Each check runs in a fresh interpreter, as the command line does, so the snapshot's own agent.human_intake is the one
imported (in this process the repository's module is already loaded)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SESSIONS = ROOT / "data/human/sessions"


def _run(code):
    out = subprocess.run([sys.executable, "-c", code], cwd=SESSIONS, capture_output=True, text=True,
                         env={"PYTHONDONTWRITEBYTECODE": "1", "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", ""),
                              "PATH": __import__("os").environ.get("PATH", "")})
    assert out.returncode == 0, out.stderr
    return out.stdout


def test_the_default_snapshot_is_committed_and_validates_the_live_registry():
    probe = _run(
        "import json, sys, tally\n"
        "snap = tally.HERE / tally.DEFAULT_SNAPSHOT\n"
        "sys.path.insert(0, str(snap))\n"
        "from agent import human_intake as hi\n"
        "assert hi.__file__.startswith(str(snap)), hi.__file__\n"
        "den = hi.load_denylist(tally.ROOT / 'data/human/sealed-denylist.v2.json', sha256_pin=tally.DENYLIST_SHA256)\n"
        "reg = hi.check_registry(tally.ROOT / 'data/human/session-splits.corpus.json', denylist=den)\n"
        "print(json.dumps(sorted({p.split for p in reg.values()})))\n")
    assert json.loads(probe.strip().splitlines()[-1]) == ["gate2", "test", "train", "val"]
    manifest = SESSIONS / "code-snapshot-e7f5045" / "manifest.json"
    assert manifest.is_file()
    tracked = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--error-unmatch", str(manifest)], capture_output=True)
    assert tracked.returncode == 0, "the default snapshot must be committed"


@pytest.mark.corpus    # hashes every admitted freeze (step tables, imports) under data/
def test_the_default_reproduces_the_committed_tally_byte_for_byte():
    out = _run(
        "import json, tally\n"
        "t, md = tally.build()\n"
        "a = (json.dumps(t, indent=1) + '\\n').encode()\n"
        "print(a == tally.OUT_JSON.read_bytes().replace(b'\\r\\n', b'\\n'))\n"
        "print(md.encode() == tally.OUT_MD.read_bytes().replace(b'\\r\\n', b'\\n'))\n")
    assert out.split() == ["True", "True"]
