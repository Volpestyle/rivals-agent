"""Check the frozen unexecuted schedule via the existing offline CLI; stdlib only."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))


def main():
    path = HERE / "schedule.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    slots = manifest["trials"]
    assert len(slots) == 20
    for key in ("episode_id", "run_id", "epoch", "target"):
        assert len({s["spec"][key] for s in slots}) == 20
    for i in range(0, 20, 2):
        a, b = slots[i:i + 2]
        assert a["pair_id"] == b["pair_id"]
        assert {a["policy_role"], b["policy_role"]} == {"scripted", "learned"}
        for key in ("scenario", "patch", "cooldowns", "settings"):
            assert a["spec"][key] == b["spec"][key]
        assert a["condition_profile"] == b["condition_profile"]
    for role in ("scripted", "learned"):
        chosen = [s for s in slots if s["policy_role"] == role]
        assert [s["spec"]["scenario"] for s in chosen] == ["near", "mid"] * 5
        assert sum(s["policy_role"] == role for s in slots[::2]) == 5
    for slot in slots:
        assert slot["execution_status"] == "UNEXECUTED"
        assert slot["observations"] == [] and slot["stop"] is None
        assert slot["run_dir"] is None and slot["log_interval"] is None
        assert slot["scope_audit"] == {"breach": None, "evidence": None}
        assert slot["collection"]["observed_track"] is None
        assert slot["spec"]["track"] == 0  # constructor placeholder, not a detection
    # Real height branch at the exact accepted boundaries; no perception/model IO.
    from agent.brain import RANGES, range_of
    from agent.state import Detection, State
    state = State(t=0, frame=(2560, 1440))
    band_checks = []
    for ratio, expected in ((.325, "near"), (.324, "mid"), (.066, "mid"), (.065, "far")):
        det = Detection(cls="enemy", bbox=(100, 0, 200, ratio * 1440), conf=1.0)
        actual = range_of(det, state)
        assert actual == expected and det.distance is None
        band_checks.append({"ratio": ratio, "range_of": actual})
    assert (RANGES.near_h, RANGES.far_h) == (.325, .065)
    command = [sys.executable, "-m", "scripts.range_benchmark", "score", str(path)]
    ran = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
    result = json.loads(ran.stdout)
    assert len(result["results"]) == 20 and len(result["summary"]["failures"]) == 20
    assert result["comparable_schedule"] is True
    for policy, summary in result["by_policy"].items():
        assert result["schedule_counts"][policy] == {"near": 5, "mid": 5}
        assert summary["scheduled_trials"] == 10
        assert summary["setup_failures"] == 10 and summary["attempted_episodes"] == 0
        assert summary["success_per_scheduled_trial"] == 0
        assert summary["success_per_attempt"] is None
        assert summary["feasibility_gate"]["passed"] is False
        assert result["execution_evidence"][policy] == {
            "auditable_executed_slots": 0, "started_by_scenario": {"near": 0, "mid": 0},
            "comparison_ready": False}
        assert result["matched_baseline_comparison"][policy] is False
    assert result["human_reference"]["comparison"] == "not_established"
    assert result["promotion"] is None
    for row in result["results"]:
        assert row["outcome"] == "setup_failure" and row["reward"] is None
        assert row["evidence"] == [] and row["start_t"] is None and row["end_t"] is None
    with (HERE / "unexecuted-result.json").open("x", encoding="utf-8") as out:
        out.write(ran.stdout)
    files = ("agent/episodes.py", "scripts/range_benchmark.py", "agent/brain.py", "agent/controller.py",
             "agent/loop.py", "agent/startup.py", "agent/state.py", "perception/hud.py", "perception/outline.py")
    receipt = {
        "kind": "unexecuted_schedule_cli_verification_not_gameplay", "exit_code": ran.returncode,
        "command": command, "stderr": ran.stderr, "python": sys.version,
        "code_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_sha256": {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in files},
        "schedule_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "height_boundary_checks": band_checks, "scheduled": 20, "executed": 0,
        "result": "20 retained setup failures, zero attempts, comparison/gates false; no evidence fabricated",
        "imports_excluded": [n for n in ("torch", "cv2", "vgamepad", "dxcam") if n not in sys.modules],
    }
    assert len(receipt["imports_excluded"]) == 4
    with (HERE / "verification.json").open("x", encoding="utf-8") as out:
        json.dump(receipt, out, indent=2)
    print(json.dumps({k: receipt[k] for k in ("kind", "exit_code", "scheduled", "executed", "result")}))


if __name__ == "__main__":
    main()
