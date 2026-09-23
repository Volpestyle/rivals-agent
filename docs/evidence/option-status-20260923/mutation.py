"""Break each option-status rule in a copy of the tree and confirm a test fails: the automated form of l5-brain.md's hand check.

  uv run --offline python -B docs/evidence/option-status-20260923/mutation.py

Copies agent/, policy/, scripts/, tests/, docs/spiderman-kit.md and pyproject.toml into a temporary directory, applies one mutation at a
time (each replaces one exact span of code), and runs TESTS there. The unmutated copy must pass and every mutant must fail, except the one
marked equivalent. Writes mutation.json here.

MUTANTS are this lane's; REVIEW_MUTANTS are the independent review's (review-1315/mutate_extra.py), re-pointed where the review fixes
rewrote the line they mutated, with the same intent.
"""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT, HERE = Path(__file__).resolve().parents[3], Path(__file__).resolve().parent
TESTS = ["tests/test_options.py", "tests/test_brain.py", "tests/test_tracker.py", "tests/test_jev.py", "tests/test_jev_async.py",
         "tests/test_loop.py"]
STOP_LINE = "    if ko is not None and memory.option is not None and _kind(memory.option).stops_on_ko:\n"
FEED_SET = "    if memory.feed is None or v == memory.feed:\n        memory.feed, memory.feed_t, memory.feed_cand = v, state.t, ()\n"
MUTANTS = {   # name: (file, span as written, its replacement)
    "ko_does_not_end_the_option": ("agent/brain.py", "    if ko is not None and KO_FEED in kind.completes_on:\n", "    if False:\n"),
    "ko_never_confirmed": ("agent/brain.py", "    if len(memory.feed_cand) < FEED_CONFIRM:\n        return None\n",
                           "    if True:\n        return None\n"),
    "ko_on_one_true_read": ("agent/brain.py", "FEED_CONFIRM = 2 ", "FEED_CONFIRM = 1 "),
    "ko_rearmed_by_one_false": ("agent/brain.py", "    if memory.feed is None or v == memory.feed:\n",
                                "    if memory.feed is None or v == memory.feed or v is False:\n"),
    "lost_target_does_not_end_the_option": ("agent/brain.py", "    if not _hold_stands(state, memory, target):\n", "    if False:\n"),
    "arrival_does_not_complete": ("agent/brain.py", '    if ARRIVAL in kind.completes_on and box is not None and range_of(box, state) == "near":\n',
                                  "    if False:\n"),
    "unread_bound_reads_failed": ("agent/brain.py", "        if kind.completes_on and not unread:\n", "        if kind.completes_on:\n"),
    "ko_stops_only_a_running_option": ("agent/brain.py", STOP_LINE, STOP_LINE.replace(".stops_on_ko:", ".stops_on_ko and completed:")),
    "every_ending_stops_the_primitive": ("agent/brain.py", STOP_LINE, "    if memory.option is not None and memory.option.status != RUNNING:\n"),
    "arrival_stops_the_primitive": ("agent/brain.py", STOP_LINE,
                                    "    if memory.option is not None and (completed or (ko is not None and _kind(memory.option).stops_on_ko)):\n"),
    "a_web_strike_stops_on_ko": ("agent/brain.py", "    WebStrike: OptionKind(STRIKE_MAX_S, (KO_FEED, ARRIVAL)),\n",
                                 "    WebStrike: OptionKind(STRIKE_MAX_S, (KO_FEED, ARRIVAL), stops_on_ko=True),\n"),
    "completed_option_reissued_by_flicker_grace": ("agent/brain.py", "    if target is None and not completed and (", "    if target is None and ("),
    "controller_ignores_stop": ("agent/controller.py", "        if stop is not None and self.played is stop and self.seq",
                                "        if False and stop is not None and self.played is stop and self.seq"),
    "loop_reads_the_feed_in_range_skill_mode": ("agent/loop.py", "phased=self.decision_slots is not None, feed=not self.range_skill_mode)",
                                                "phased=self.decision_slots is not None, feed=True)"),
    "loop_passes_no_stop": ("agent/loop.py", "        if fresh and not self.range_skill_mode and d.stop is not None:\n", "        if False:\n"),
}
REVIEW_MUTANTS = {
    "jev_launch_ignores_running": ("agent/jev.py", "if self._flight is None and not brain.running(memory) and not (",
                                   "if self._flight is None and not ("),
    "stop_by_equality": ("agent/controller.py", "self.played is stop and self.seq", "self.played == stop and self.seq"),
    "stop_ignores_seq_name": ("agent/controller.py", " and self.seq_name == _option_primitive(stop):", ":"),
    "retreat_does_not_end_option": ("agent/brain.py", "        if running(memory):\n            memory.option = memory.option.end(INTERRUPTED, Evidence(RETREAT_HP",
                                    "        if False:\n            memory.option = memory.option.end(INTERRUPTED, Evidence(RETREAT_HP"),
    "bound_ignored": ("agent/brain.py", "    if t >= op.bound_t:\n", "    if False:\n"),
    "none_resets_feed": ("agent/brain.py", "    if v is None:\n        return None\n", "    if v is None:\n        memory.feed_cand = ()\n        return None\n"),
    "line_up_at_start_counts": ("agent/brain.py", FEED_SET, "    if memory.feed is None:\n        memory.feed, memory.feed_t = False, state.t\n"
                                "    if v == memory.feed:\n        memory.feed, memory.feed_t, memory.feed_cand = v, state.t, ()\n"),
    "superseded_not_recorded": ("agent/brain.py", "    if running(memory):\n        memory.option = memory.option.end(INTERRUPTED, Evidence(SUPERSEDED",
                                "    if False:\n        memory.option = memory.option.end(INTERRUPTED, Evidence(SUPERSEDED"),
    "arrival_on_any_target_box": ("agent/brain.py", "    return next((d for d in state.detections or [] if d.track == held.track and d.cls in HOSTILE), None)\n",
                                  "    return target\n"),
    "stop_on_ko_for_any_kind": ("agent/brain.py", STOP_LINE, "    if ko is not None and memory.option is not None:\n"),
    "stop_never_reset": ("agent/brain.py", "    memory.t, memory.stop = t, None\n", "    memory.t = t\n"),
    "ko_refires_after_confirm": ("agent/brain.py", "    memory.feed, memory.feed_t, memory.feed_cand = v, state.t, ()\n    if v is True:\n",
                                 "    memory.feed_cand = memory.feed_cand[1:]\n    if v is True:\n"),
    "decider_ignores_feed_flag": ("agent/loop.py", "        if self.feed:\n            state.kill_feed", "        if self.p.killfeed is not None:\n            state.kill_feed"),
    "loop_stop_when_stale": ("agent/loop.py", "        if fresh and not self.range_skill_mode and d.stop is not None:\n",
                             "        if d is not None and not self.range_skill_mode and d.stop is not None:\n"),
}
EQUIVALENT = {"loop_stop_when_stale": "a stale decision's intent is Idle, which clears the controller's sequence anyway (review F4)"}


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
        (tmp / "docs").mkdir()
        shutil.copy(ROOT / "docs/spiderman-kit.md", tmp / "docs")
        shutil.copy(ROOT / "pyproject.toml", tmp)
        code, tail, failed = run(tmp)
        assert code == 0, tail
        results["unmutated"] = {"exit": code, "summary": tail}
        for source, table in (("lane", MUTANTS), ("review", REVIEW_MUTANTS)):
            for name, (path, old, new) in table.items():
                original = (tmp / path).read_text(encoding="utf-8")
                assert original.count(old) == 1, (name, original.count(old))
                (tmp / path).write_text(original.replace(old, new), encoding="utf-8")
                code, tail, failed = run(tmp)
                (tmp / path).write_text(original, encoding="utf-8")
                results[name] = {"source": source, "killed": code != 0, "summary": tail, "failed": failed,
                                 **({"equivalent": EQUIVALENT[name]} if name in EQUIVALENT else {})}
                print(f"{source} {name}: {'killed' if code else 'survived'} ({tail})")
    (HERE / "mutation.json").write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")
    survived = [k for k, r in results.items() if k != "unmutated" and not r["killed"] and k not in EQUIVALENT]
    assert not survived, f"survived: {survived}"


if __name__ == "__main__":
    main()
