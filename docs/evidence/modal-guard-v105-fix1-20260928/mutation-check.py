"""Scratch mutant removes overhead from commitment; regenerate scratch release."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

with tempfile.TemporaryDirectory(prefix="modal-overhead-mutant-") as temp:
    root = Path(temp)
    shutil.copytree("cloud/modal_guard", root / "cloud/modal_guard", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree("tests/modal_guard", root / "tests/modal_guard", ignore=shutil.ignore_patterns("__pycache__"))
    package = root / "cloud/modal_guard"
    path = package / "ledger.py"
    text = path.read_text()
    assert text.count("retained += overhead") == 1
    path.write_text(text.replace("retained += overhead", 'retained += usd("0")'))
    manifest = json.loads((package / "RELEASE.json").read_bytes())
    manifest["files"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in package.glob("*.py")}
    (package / "RELEASE.json").write_text(json.dumps(manifest))
    run = subprocess.run([sys.executable, "-m", "pytest", "-q",
                          "tests/modal_guard/test_reconciliation.py::test_covered_app_cannot_release_storage_overhead[197.75-False]"],
                         cwd=root, capture_output=True, text=True)
    assert run.returncode == 1 and "1 failed" in run.stdout and "AssertionError" in run.stdout, run.stdout + run.stderr
    assert "shared library" not in run.stdout, "mutation only failed release pinning"
    print(json.dumps({"mutant": "omit-covered-non-app-overhead", "killed": True,
                      "scratch_release_rehashed": True, "paid_actions": 0}))
