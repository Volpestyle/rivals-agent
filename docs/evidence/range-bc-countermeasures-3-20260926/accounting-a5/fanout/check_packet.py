"""Synthetic-only A3 adapter checks; no sources, media, weights or Modal calls."""
import copy,importlib.util,json,pathlib
from packet_adapter import assemble
spec=importlib.util.spec_from_file_location("a3_test",pathlib.Path(__file__).with_name("test_judge_cm3-a3.py"))
T=importlib.util.module_from_spec(spec);spec.loader.exec_module(T)
fixture=T.Amendment3Tests();fixture.setUp();fixture.set_model("modal:L40S")
launch,original=fixture.l,fixture.p
hardware={"class":"cuda:L40S","driver":"synthetic","cuda_runtime":"synthetic","cudnn":"synthetic"}
verification={"format":"cm3-matrix-verification-v1","status":"PASS","context_sha256":"c"*64,
              "hardware":hardware,"code_sha256":"d"*64,"software_sha256":"e"*64,"outputs":[]}
rows=[];metadata={}
for arm,report in original["core"].items():
    metadata[arm]={k:copy.deepcopy(v) for k,v in report.items() if k not in ("metrics","epochs_log","checkpoints","context")}
for ex in original["execution"]:
    arm="H" if ex["arm"]=="H-repeat" else ex["arm"];seed=ex["seed"];s=str(seed)
    purpose="repeat" if ex["arm"]=="H-repeat" else "registered"
    report=original["core"][arm]
    ref={"path":f"/synthetic/{ex['arm']}{s}/result.json","sha256":T.h(ex["arm"]+s)}
    verification["outputs"].append(copy.deepcopy(ref))
    result={k:copy.deepcopy(verification[k]) for k in ("context_sha256","hardware","code_sha256","software_sha256")}
    result.update(format="cm3-stage-result-v1",stage="fit",arm=arm,seed=seed,purpose=purpose,status="PASS")
    ev={k:copy.deepcopy(v["model_nohud"][s]) for k,v in report["metrics"]["dev"].items()}
    ev.update(teacher_forced={},sanity={},executed_decisions_sha256=T.h("decisions"),zero_motion_camera_mae=1)
    ctx=copy.deepcopy(report["context"][s])
    if arm!="A":ctx["train_diagnostic_subset"]={"synthetic":True}
    rows.append({"ref":ref,"result":result,"details":{"evaluation":ev,"context":ctx,
       "logs":{"epochs":copy.deepcopy(report["epochs_log"][s])},
       "checkpoint_sha256":report["checkpoints"][s],"stable_sha256":ex["content_sha256"]}})
args=dict(verification=verification,rows=rows,report_metadata=metadata,execution=original["execution"],
          gate=original["phase1_gate"],launch=launch,elapsed_compute_seconds=original["elapsed_compute_seconds"])
packet=assemble(**args)
verdict=T.J.judge(launch,packet,fixture.host,legacy_report=fixture.legacy)
assert verdict["status"]=="COMPLETE" and verdict["selected"]=="H"
checks=["synthetic verified matrix assembles and passes full pinned A3 judge"]
def reject(label,mutate):
    bad=copy.deepcopy(args);mutate(bad)
    try:assemble(**bad)
    except (AssertionError,KeyError,ValueError):checks.append(label);return
    raise RuntimeError(label+" accepted")
# Imported judge instances have distinct Invalid classes; catch ValueError if inherited.
reject("unverified matrix refused",lambda x:x["verification"].update(status="INCOMPLETE"))
reject("substituted output refused",lambda x:x["rows"][0]["ref"].update(sha256="0"*64))
reject("mixed hardware refused",lambda x:x["rows"][0]["result"]["hardware"].update(**{"class":"cuda:A10"}))
reject("CUDA missing peak source refused",lambda x:x["rows"][0]["details"]["context"].pop("peak_memory_source"))
reject("phase2 before gate refused",lambda x:x["execution"][-1].update(start=T.at(20)))
reject("missing repeat refused",lambda x:x["rows"].pop())
reject("aggregate compute cap refused",lambda x:x.update(elapsed_compute_seconds=57601))
print(json.dumps({"pass":True,"synthetic_only":True,"checks":checks},indent=2))
