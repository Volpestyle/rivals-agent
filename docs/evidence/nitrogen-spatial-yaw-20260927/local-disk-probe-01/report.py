"""Reproduce the I/O-only projection from pinned guarded probe artifacts."""
import hashlib
import json
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

root = Path(__file__).parent
pins = {
    "probe.json": "4211b09ff07dc5981187d547bf8c66e1157c1b19110e5b962d9af6326755f7a0",
    "copy.json": "d98a3912cc14e5b83147600c9451a23f5763441f5616123b85ad85a71c81f07d",
}
for name, digest in pins.items():
    assert hashlib.sha256((root / "collected" / name).read_bytes()).hexdigest() == digest
p = json.loads((root / "collected/probe.json").read_bytes())
r = json.loads((root / "collected/result.json").read_bytes())
assert r["status"] == "COMPLETE" and r["accounting"]["state"] == "TERMINAL"
assert r["accounting"]["bound_usd"] == "0.547570"
assert p["all_train_windows_traversed"] and not p["checkpoint_reusable"]
assert not p["scientific_metrics_retained"] and p["frozen_base_exact"]
assert sorted(i for batch in p["batch_ids"][:588] for i in batch) == list(range(4697))
rate = min(p["steady_updates_per_second"], p["second_epoch_updates_per_second"])
seconds = {
    "copy_hash": p["copy_seconds"],
    "train_load_verify": p["load_and_verify_seconds"],
    "15288_updates": 15288 / rate,
    "26_epoch_boundaries": 26 * max(0, p["epoch_boundary_seconds_including_one_step"] - 1 / rate),
    "final_evaluator": p["evaluation_seconds"],
    "eval_reload_allowance": p["load_and_verify_seconds"],
    "model_and_volume_checkpoint_allowance": 120,
}
hold = (Decimal(6720) * Decimal(".0007178888888888888888888888889") + Decimal(".05")).quantize(
    Decimal(".000001"), rounding=ROUND_CEILING)
prior = {"shakedowns": "1.302986", "extractions": "1.780898", "original_fit_refusals": "1.583800",
         "stopped_grid8": "2.252171", "completed_grid4": "2.585487", "local_disk_probe": "0.547570"}
settled = sum(map(Decimal, prior.values()))
print(json.dumps({"tag": "EXPLORATORY TIMING PROJECTION, NOT P95", "artifact_pins": pins,
                  "seconds": seconds, "projected_work_seconds": sum(seconds.values()),
                  "proposed_work_seconds": 6300, "unallocated_work_margin_seconds": 6300-sum(seconds.values()),
                  "proposed_startup_seconds": 300, "proposed_cleanup_seconds": 120,
                  "proposed_hold_each_usd": str(hold), "proposed_three_holds_usd": str(3*hold),
                  "settled_components_usd": prior, "settled_campaign_usd": str(settled),
                  "outstanding_yaw_holds_usd": "0", "campaign_plus_proposed_holds_usd": str(settled+3*hold)}, indent=2))
