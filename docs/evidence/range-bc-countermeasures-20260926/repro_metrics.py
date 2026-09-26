"""Countermeasures code, reproduction proof (a): re-evaluate a stored report's checkpoints with the new evaluate_set
and show every existing figure (teacher_forced, self_fed, sanity, human_sanity, gates) is byte-identical as canonical
JSON; write the new blocks (executed_teacher_forced, self_fed_checks) for the interim re-read. Inference only.

    python repro_metrics.py <run dir> <out.json>
"""
import json
from pathlib import Path
import sys

from policy.range_bc import report as rpt, steps, train

D = Path("/Users/james/dev/range-bc-data")
DEV = [D / "steps15/20260923T171533-187Z-33696-5.jsonl", D / "steps15/20260923T205528-900Z-45572-3.jsonl"]
run, out = Path(sys.argv[1]), Path(sys.argv[2])
stored = json.loads((run / "report.json").read_text(encoding="utf-8"))
cfg = stored["config"]
deny = steps.load_denylist(steps.DENYLIST, steps.DENYLIST_SHA256)
eq = steps.load_patch_equivalence(steps.PATCH_EQUIVALENCE, steps.PATCH_EQUIVALENCE_SHA256)
dev = train.load_arrays(DEV, D / "caches15", lag=cfg["lag"], regimes=tuple(cfg["regimes"]), splits=("train",),
                        denylist=deny, equivalence=eq)
models = {}
for name, sha in stored["checkpoints"].items():
    assert steps.sha256(run / name) == sha, name
    model, payload = train.load_checkpoint(run / name, device=stored["device"])
    models[payload["meta"]["arm"], payload["meta"]["seed"]] = model
new, verdicts = train.evaluate_set(models, dev, stored["train_statistics"], stored["ar2"], device=stored["device"],
                                   stride=cfg["stride"])
old = stored["metrics"]["dev"]
canon = lambda v: rpt.canonical(json.loads(json.dumps(v)))          # the report's own serialisation
result = {"run": str(run), "report_sha256": steps.sha256(run / "report.json"), "equal": {}}
for k in sorted(old):
    result["equal"][k] = canon(new[k]) == canon(old[k])
result["equal"]["gates"] = canon(verdicts) == canon(stored["gates"]["dev"])
result["new_keys"] = sorted(set(new) - set(old))
result["executed_teacher_forced"] = new["executed_teacher_forced"]
result["self_fed_checks"] = new["self_fed_checks"]
out.write_text(rpt.canonical(json.loads(json.dumps(result))) + "\n", encoding="utf-8")
print(json.dumps(result["equal"]), result["new_keys"])
