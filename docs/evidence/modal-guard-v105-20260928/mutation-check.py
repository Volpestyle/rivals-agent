"""Run from repo root. Scratch-only mutants; never edit the canonical package."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

mutations = [
    ("closed-hour-buffer", "reconciliation.py", "last + 7200 <= end", "last + 3600 <= end",
     "test_incomplete_evidence_retains_allowance[young]"),
    ("active-app-credit", "reconciliation.py", 'row["state"] != "TERMINAL"',
     'row["state"] not in ("TERMINAL", "RUNNING")', "test_incomplete_evidence_retains_allowance[nonterminal]"),
    ("warn-boundary", "ledger.py", '< usd(WARN_USD)', '<= usd(WARN_USD)',
     "test_warn_boundary_atomic_reservation[147.75-False]"),
]
results = []
for label, module, before, after, case in mutations:
    with tempfile.TemporaryDirectory(prefix="modal-v105-mutant-") as temp:
        root = Path(temp)
        shutil.copytree("cloud/modal_guard", root / "cloud/modal_guard", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree("tests/modal_guard", root / "tests/modal_guard", ignore=shutil.ignore_patterns("__pycache__"))
        path = root / "cloud/modal_guard" / module
        text = path.read_text()
        assert text.count(before) == 1
        path.write_text(text.replace(before, after))
        run = subprocess.run([sys.executable, "-m", "pytest", "-q",
                              "tests/modal_guard/test_reconciliation.py::" + case],
                             cwd=root, capture_output=True, text=True)
        assert run.returncode == 1 and "1 failed" in run.stdout, run.stdout + run.stderr
        results.append({"mutant": label, "killed": True, "test": case})
print(json.dumps(results, indent=2))
