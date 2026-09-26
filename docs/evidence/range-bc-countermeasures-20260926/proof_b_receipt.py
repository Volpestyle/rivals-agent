"""N1: the retained comparison for proof (b), from the existing runs (no training): the default-off retrain on the new
code (runs/cm-repro-control47-seed0) against the stored interim94-control47-s012 seed 0. Stdlib only."""
import hashlib, json, sys
from pathlib import Path
R = Path("/Users/james/dev/range-bc-data/runs")
new, old = R / "cm-repro-control47-seed0", R / "interim94-control47-s012"
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
a, b = (json.loads((d / "report.json").read_text()) for d in (new, old))
out = {"new_run": str(new), "old_run": str(old), "new_report_sha256": sha(new / "report.json"),
       "old_report_sha256": sha(old / "report.json"), "new_exit": (R / "cm-repro-control47-seed0.exit").read_text().strip(),
       "new_log_sha256": sha(R / "cm-repro-control47-seed0.log"), "code": "code-cm (cf25505 + the four reviewed files, first version)",
       "checkpoints": {}, "equal": {}}
for n in ("model_nohud-seed0.pt", "history_only-seed0.pt"):
    fn, fo = sha(new / n), sha(old / n)
    out["checkpoints"][n] = {"new_file": fn, "old_file": fo, "new_report_entry": a["checkpoints"][n],
                             "old_report_entry": b["checkpoints"][n], "equal": fn == fo == a["checkpoints"][n] == b["checkpoints"][n]}
ma, mb = a["metrics"]["dev"], b["metrics"]["dev"]
for blk in ("teacher_forced", "self_fed", "sanity"):
    for arm in ma[blk]:
        out["equal"][f"{blk}.{arm}"] = (ma[blk][arm]["0"] == mb[blk][arm]["0"]) if arm in ("model_nohud", "history_only") \
            else ma[blk][arm] == mb[blk][arm]
out["equal"]["human_sanity"] = ma["human_sanity"] == mb["human_sanity"]
strip = lambda l: [{k: v for k, v in e.items() if k != "seconds"} for e in l]
for n in ("model_nohud-seed0.pt", "history_only-seed0.pt"):
    out["equal"]["epochs_log." + n] = strip(a["epochs_log"][n]) == strip(b["epochs_log"][n])
out["equal"]["train_statistics"] = a["train_statistics"] == b["train_statistics"]
out["equal"]["ar2"] = a["ar2"] == b["ar2"]
out["equal"]["config_except_new_keys"] = {k: v for k, v in a["config"].items() if k not in ("prev_dropout", "self_condition")} == b["config"]
out["new_config_keys"] = {k: a["config"][k] for k in ("prev_dropout", "self_condition")}
out["new_metric_keys"] = sorted(set(ma) - set(mb))
out["all_equal"] = all(out["equal"].values()) and all(c["equal"] for c in out["checkpoints"].values())
Path(sys.argv[1]).write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
print(out["all_equal"], json.dumps(out["checkpoints"]))
