"""Lossless per-fit metric mapping for the draft outer harness; no file/data/cloud I/O.

Caller must first authenticate the complete matrix with cm3_run verify and supply
its pinned PASS. This mapper does not certify receipt/provenance or select a model.
The pinned A3 judge validates memory provenance; no placeholders are permitted.
"""
import copy,hashlib,importlib.util,pathlib
JUDGE_SHA="e23b3212a0eadc98bc590e5081a92c9fab6740e93808aba2d245d6020b3f8eb0"
def judge():
 path=pathlib.Path(__file__).with_name("judge_cm3-a3.py")
 assert hashlib.sha256(path.read_bytes()).hexdigest()==JUDGE_SHA
 spec=importlib.util.spec_from_file_location("cm3_a3",path)
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 return module
SEEDS={0,1,2}
def map_arm(rows):
 assert all(r["result"]["format"]=="cm3-stage-result-v1" and r["result"]["arm"] in ("A","H","I","W") and type(r["result"]["seed"]) is int for r in rows)
 assert len(rows)==3 and {r["result"]["seed"] for r in rows}==SEEDS
 assert len({r["result"]["arm"] for r in rows})==1
 assert len({r["result"]["context_sha256"] for r in rows})==1
 metrics={"self_fed_checks":{"model_nohud":{}},"executed_teacher_forced":{"model_nohud":{}},"self_fed":{"model_nohud":{}}}
 logs={};checkpoints={};raw={}
 for row in rows:
  result,detail=row["result"],row["details"]
  assert result["status"]=="PASS" and result["stage"]=="fit" and result["purpose"]=="registered"
  seed=str(result["seed"]);evaluation=detail["evaluation"]
  for name in metrics:metrics[name]["model_nohud"][seed]=copy.deepcopy(evaluation[name])
  epochs=detail["logs"]["epochs"]
  assert [e["epoch"] for e in epochs]==list(range(13))
  logs[seed]=copy.deepcopy(epochs);checkpoints[seed]=detail["checkpoint_sha256"]
  raw[seed]={key:copy.deepcopy(evaluation[key]) for key in
             ("teacher_forced","sanity","executed_decisions_sha256","zero_motion_camera_mae")}
 return {"metrics":{"dev":metrics},"epochs_log":logs,"checkpoints":checkpoints,"raw_diagnostics":raw}
def require_report_diagnostics(arm,diagnostics,backend="cuda"):
 required={"wall_seconds","held_change_f1","raw_teacher_forced","executed_counts"}
 if arm!="A":required|={"unweighted_train_loss","normalized_feature_diagnostics","gate_diagnostics","train_diagnostic_subset"}
 assert set(diagnostics)=={"0","1","2"}
 for seed,values in diagnostics.items():
  missing=[k for k in sorted(required) if k not in values or values[k] is None]
  if missing:raise ValueError(f"{arm}/{seed}: measured diagnostics missing: {missing}")
  judge().check_memory(values,backend)
 return copy.deepcopy(diagnostics)
