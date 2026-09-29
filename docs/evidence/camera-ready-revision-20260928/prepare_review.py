"""Pin this specific uncommitted delta for independent live-review; no approval."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).parent
BASE = "e91a2d4f6bf03da8c624967a1c578e7da3f3c0c1"
PATHS = ["perception/camera_ready_pose.py", "scripts/measure_camera_turns.py",
         "tests/test_camera_ready_pose.py", "tests/test_measure_camera_turns.py"]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def write(name, value):
    with (OUT / name).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


review = json.loads((ROOT / "docs/evidence/live-loop-repair-20260928/review-v1.json").read_text())
files = {p: digest(ROOT / p) for p in review["files"]}
changed_pins = [p for p in files if files[p] != review["files"][p]]
assert set(changed_pins) == set(PATHS) - {"tests/test_camera_ready_pose.py"}
ast_report = {}
for path, allowed in ((PATHS[0], {"analyze"}),
                      (PATHS[1], {"ready_proof", "retain_pose_refusal"})):
    original = ast.parse(git("show", BASE + ":" + path).decode())
    current = ast.parse((ROOT / path).read_text())
    def definitions(tree):
        return {node.name: ast.dump(node, include_attributes=False) for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    before, after = definitions(original), definitions(current)
    assert before.keys() == after.keys()
    changed = [name for name in before if before[name] != after[name]]
    assert set(changed) == allowed
    ast_report[path] = {"changed_definitions": changed,
                        "unchanged_definitions": [n for n in before if n not in changed]}
patch = OUT / "delta.diff"
assert not patch.exists()
git("diff", "--binary", "--no-ext-diff", "--output=" + str(patch), BASE, "--", *PATHS)
write("ast-delta.json", ast_report)
write("review-inputs.json", {
    "format": "camera-ready-delta-review-inputs-v1", "status": "unreviewed_uncommitted_no_live_use",
    "base_commit": BASE, "worktree_head_at_packet": git("rev-parse", "HEAD").decode().strip(),
    "diff_command": "git diff " + BASE + " -- " + " ".join(PATHS),
    "diff_sha256": digest(patch), "files": files,
    "additional_files": {PATHS[2]: digest(ROOT / PATHS[2])},
    "prior_review": {"path": "docs/evidence/live-loop-repair-20260928/review-v1.json",
                     "sha256": digest(ROOT / "docs/evidence/live-loop-repair-20260928/review-v1.json")},
    "changed_runtime_paths": PATHS, "ast_evidence": "ast-delta.json",
    "tests": "final-tests.txt", "native_replay": "native-replay.json",
    "scope": "pose findings 1-3 plus audit/frame retention; no prime/segment/lease/token/deadline or FPS changes",
    "limits": "Sparse native frames cannot prove continuous recovery; no calibration/rate/focal acceptance",
})
write("files.sha256.json", {p.name: digest(p) for p in sorted(OUT.iterdir()) if p.is_file()})
print("Prepared exact 4-file delta and 12 required source pins; no staging, commit or receipt issued")
