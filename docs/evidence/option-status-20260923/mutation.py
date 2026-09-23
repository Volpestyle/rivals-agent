"""Break each option-status rule in a copy of the tree and confirm a test fails: the automated form of l5-brain.md's hand check.

  uv run --offline python -B docs/evidence/option-status-20260923/mutation.py

Copies agent/, policy/, scripts/, tests/ and pyproject.toml into a temporary directory, applies one mutation at a time (each replaces
exactly one line of code), and runs tests/test_options.py, tests/test_brain.py and tests/test_tracker.py there. The unmutated copy must
pass and every mutant must fail. Writes mutation.json here.
"""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT, HERE = Path(__file__).resolve().parents[3], Path(__file__).resolve().parent
TESTS = ["tests/test_options.py", "tests/test_brain.py", "tests/test_tracker.py"]
MUTANTS = {   # name: (file, line as written, its replacement)
    "ko_does_not_end_the_option": ("agent/brain.py", "    if ko is not None and KO_FEED in kind.completes_on:\n", "    if False:\n"),
    "ko_never_confirmed": ("agent/brain.py", "        if len(memory.feed_on) == FEED_CONFIRM:\n", "        if False:\n"),
    "ko_on_one_true_read": ("agent/brain.py", "FEED_CONFIRM = 2 ", "FEED_CONFIRM = 1 "),
    "lost_target_does_not_end_the_option": ("agent/brain.py", "    if not _hold_stands(state, memory, target):\n", "    if False:\n"),
    "arrival_does_not_complete": ("agent/brain.py", '    if ARRIVAL in kind.completes_on and box is not None and range_of(box, state) == "near":\n',
                                  "    if False:\n"),
    "unread_bound_reads_failed": ("agent/brain.py", "        if kind.completes_on and not unread:\n", "        if kind.completes_on:\n"),
    "ko_stops_only_a_running_option": ("agent/brain.py",
                                       "    if memory.option is not None and (completed or (ko is not None and KO_FEED in _kind(memory.option).completes_on)):\n",
                                       "    if memory.option is not None and completed:\n"),
    "every_ending_stops_the_primitive": ("agent/brain.py",
                                         "    if memory.option is not None and (completed or (ko is not None and KO_FEED in _kind(memory.option).completes_on)):\n",
                                         "    if memory.option is not None and memory.option.status != RUNNING:\n"),
    "completed_option_reissued_by_flicker_grace": ("agent/brain.py", "    if target is None and not completed and (", "    if target is None and ("),
    "controller_ignores_stop": ("agent/controller.py", "        if stop is not None and self.played is stop and self.seq",
                                "        if False and stop is not None and self.played is stop and self.seq"),
    "loop_reads_the_feed_in_range_skill_mode": ("agent/loop.py", "phased=self.decision_slots is not None, feed=not self.range_skill_mode)",
                                                "phased=self.decision_slots is not None, feed=True)"),
    "loop_passes_no_stop": ("agent/loop.py", "        if fresh and not self.range_skill_mode and d.stop is not None:\n", "        if False:\n"),
}


def run(tmp):
    got = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", *TESTS], cwd=tmp, capture_output=True, text=True)
    failed = sorted({line.split(" ")[1].split("[")[0] for line in got.stdout.splitlines() if line.startswith("FAILED ")})
    return got.returncode, got.stdout.strip().splitlines()[-1], failed


def main():
    results = {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for d in ("agent", "policy", "scripts", "tests"):
            shutil.copytree(ROOT / d, tmp / d, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy(ROOT / "pyproject.toml", tmp)
        code, tail, failed = run(tmp)
        assert code == 0, tail
        results["unmutated"] = {"exit": code, "summary": tail}
        for name, (path, old, new) in MUTANTS.items():
            original = (tmp / path).read_text(encoding="utf-8")
            assert original.count(old) == 1, (name, original.count(old))
            (tmp / path).write_text(original.replace(old, new), encoding="utf-8")
            code, tail, failed = run(tmp)
            (tmp / path).write_text(original, encoding="utf-8")
            results[name] = {"killed": code != 0, "summary": tail, "failed": failed}
            print(f"{name}: {'killed' if code else 'SURVIVED'} ({tail})")
    (HERE / "mutation.json").write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")
    assert all(r["killed"] for k, r in results.items() if k != "unmutated"), "a mutant survived"


if __name__ == "__main__":
    main()
