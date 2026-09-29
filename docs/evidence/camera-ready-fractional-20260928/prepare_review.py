"""Pin the uncommitted fractional-NCC delta; never issue an approval receipt."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).parent
BASE = "adfe13f6a1516d5987424acbda9cfbe1211929d2"
PATHS = ["perception/camera_ready_pose.py", "tests/test_camera_ready_pose.py"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def write(name, data):
    with (OUT / name).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write("\n")


receipt_path = ROOT / "docs/evidence/camera-ready-revision-20260928/review-v2.json"
receipt = json.loads(receipt_path.read_text())
pins = {p: sha(ROOT / p) for p in receipt["files"]}
assert [p for p in pins if pins[p] != receipt["files"][p]] == [PATHS[0]]
old = ast.parse(git("show", BASE + ":" + PATHS[0]).decode())
new = ast.parse((ROOT / PATHS[0]).read_text())
assert len(old.body) == len(new.body)
changed = [getattr(b, "name", type(b).__name__) for a, b in zip(old.body, new.body)
           if ast.dump(a, include_attributes=False) != ast.dump(b, include_attributes=False)]
assert changed == ["analyze"]
prime_hash = sha(ROOT / "perception/camera_prime_response.py")
assert prime_hash == "465fc4792697802802db778320e2450ea1054eba501ef5eec7c0a341b4308d31"
assert not git("diff", BASE, "--", "scripts/measure_camera_turns.py", "tests/test_measure_camera_turns.py",
               "perception/camera_prime_response.py")
patch = OUT / "delta.diff"
assert not patch.exists()
git("diff", "--binary", "--no-ext-diff", "--output=" + str(patch), BASE, "--", *PATHS)
write("review-inputs.json", {
    "format": "camera-fractional-ncc-review-inputs-v1", "status": "unreviewed_uncommitted_no_live_use",
    "base_commit": BASE, "head_at_packet": git("rev-parse", "HEAD").decode().strip(),
    "diff_command": "git diff " + BASE + " -- " + " ".join(PATHS),
    "diff_sha256": sha(patch), "files": pins, "additional_files": {PATHS[1]: sha(ROOT / PATHS[1])},
    "prior_receipt": {"path": str(receipt_path.relative_to(ROOT)), "sha256": sha(receipt_path)},
    "ast_changed": changed, "module_constants_and_helpers": "unchanged",
    "driver_and_driver_tests": "byte-identical to v2 receipt", "prime_module_sha256_unchanged": prime_hash,
    "tests": "final-tests.txt", "native_cases": "native-replay.json", "prime_diagnostic": "prime-diagnostic.json",
    "scope": "NCC measured at already-estimated fractional offset; displacement and all thresholds unchanged",
})
write("files.sha256.json", {p.name: sha(p) for p in sorted(OUT.iterdir()) if p.is_file()})
print("Pinned 2-file delta; driver/prime unchanged; no staging or review receipt")
