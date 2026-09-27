"""Synthetic metric transport checks only. No real result, source or checkpoint read."""
import copy,json
from map_metrics import map_arm,require_report_diagnostics
rows=[]
for seed in range(3):
 evaluation={k:{"synthetic":k,"seed":seed} for k in
 ("self_fed_checks","executed_teacher_forced","self_fed","teacher_forced","sanity","executed_decisions_sha256","zero_motion_camera_mae")}
 rows.append({"result":{"format":"cm3-stage-result-v1","arm":"H","seed":seed,"status":"PASS","stage":"fit",
 "purpose":"registered","context_sha256":"a"*64},"details":{"evaluation":evaluation,
 "logs":{"epochs":[{"epoch":i,"train_loss":1,"dev":{"total":2}} for i in range(13)]},"checkpoint_sha256":str(seed)*64}})
out=map_arm(rows)
for seed in range(3):
 for key in ("self_fed_checks","executed_teacher_forced","self_fed"):
  assert out["metrics"]["dev"][key]["model_nohud"][str(seed)]==rows[seed]["details"]["evaluation"][key]
out["metrics"]["dev"]["self_fed"]["model_nohud"]["0"]["synthetic"]="changed-copy"
assert rows[0]["details"]["evaluation"]["self_fed"]["synthetic"]=="self_fed"
checks=["exact block mapping without metric recomputation","output copy does not mutate inputs"]
for name,mutate in [
 ("duplicate seed",lambda x:x[1]["result"].update(seed=0)),
 ("mixed context",lambda x:x[1]["result"].update(context_sha256="b"*64)),
 ("incomplete epoch",lambda x:x[1]["details"]["logs"]["epochs"].pop()),
 ("incomplete result",lambda x:x[1]["result"].update(status="INCOMPLETE")),
 ("repeat substituted for registered fit",lambda x:x[1]["result"].update(purpose="repeat"))]:
 bad=copy.deepcopy(rows);mutate(bad)
 try:map_arm(bad)
 except AssertionError:checks.append(name+" refused")
 else:raise RuntimeError(name+" accepted")
try:require_report_diagnostics("H",{str(s):{} for s in range(3)})
except ValueError:checks.append("missing measured diagnostics refused")
else:raise RuntimeError("missing diagnostics accepted")
print(json.dumps({"pass":True,"synthetic_only":True,"checks":checks},indent=2))
