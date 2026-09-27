"""A3 L40S fan-out revision: offline review only. CLI paid launch is disabled."""
import argparse,hashlib,json,pathlib,subprocess,time,sys,os,re
from safety import (require,digest,sha,document,canonical,projection,numeric_plan,validate_binding,ledger,
                    relative,remote_path,running_bound,fit_budget,PHASE1,PHASE2,STARTUP_SECONDS)
from input_closure import validate_input
from lifecycle import (connect_verified,verify_client,reserve,update_inventory,atomic,cleanup,finish_task)
ROOT=pathlib.Path(__file__).resolve().parent
PLAN=ROOT/"launch-plan.json"
DEPLOYMENT_ENABLED=False

def read_plan():return json.loads(PLAN.read_bytes())
def is_sha(value):
 try:sha(value);return True
 except ValueError:return False

def build_app(p,identity,client,key):
 if p.get("transport_v4"):
  from phase_transport import build_app_v4
  return build_app_v4(p,identity,client,key)
 # Called only after authenticated identity, reservation and guard readiness.
 require(identity==p["verified_identity"],"unverified app identity")
 verify_client(client,identity)
 require(key in p["tasks"] and p["selected_task"]==key,"wrong app task")
 import modal
 app=modal.App(p["owned_app_name"])
 image=modal.Image.from_registry(p["reviewed_image_digest"]).add_local_python_source("safety","input_closure","lifecycle","cm3_accounting","cm3_timeouts","cm3_budget_plan")
 inputs=modal.Volume.from_id(p["input_volume_id"],client=client).read_only()
 outputs=modal.Volume.from_id(p["output_volume_id"],client=client)
 function=app.function(image=image,gpu="L40S",cpu=(8,8),memory=(32768,32768),
       volumes={"/inputs":inputs,"/outputs":outputs},retries=0,
       timeout=p["attempt_timeout_seconds_by_arm"][key[0]],startup_timeout=STARTUP_SECONDS,single_use_containers=True)(run_fit)
 return app,function

def run_fit(arm,seed,purpose="registered",runtime_plan=None):
 if runtime_plan and runtime_plan.get("transport_v4"):
  from phase_worker import run_fit_v4
  return run_fit_v4(arm,seed,purpose,runtime_plan)
 import modal
 p=runtime_plan
 assert isinstance(p,dict),"driver must bind the validated launch plan"
 outputs=modal.Volume.from_id(p["output_volume_id"])
 assert arm in ("A","H","I","W") and seed in (0,1,2)
 assert purpose in ("registered","repeat")
 repeat=purpose=="repeat"
 assert not repeat or (arm=="H" and seed==0)
 key="H-repeat-0" if repeat else f"{arm}-{seed}"
 assert p["selected_task"]==key,"wrong dedicated task"
 work_seconds=p["attempt_timeout_seconds_by_arm"][arm]
 spec=p["tasks"][key]
 # The reviewed owner entrypoint must perform all approval/authentication itself.
 # We never call training primitives and never rewrite a lead receipt.
 code=pathlib.Path("/inputs")/p["code_directory"]
 entry=code/"policy/range_bc/cm3_run.py"
 assert digest(entry)==p["entrypoint_sha256"],"entrypoint changed"
 task_dir=pathlib.Path("/outputs/.modal-journal")/p["run_id"]/key
 task_dir.mkdir(parents=True,exist_ok=True)
 previous=sorted(task_dir.glob("attempt-*.json"))
 attempt=0
 assert p["attempts_max"]==1,"no automatic training retry"
 assert time.time()<p["absolute_deadline_unix"],"running-spend deadline"
 allocation=spec["attempt_receipts"][attempt]
 receipt=pathlib.Path("/inputs")/allocation["path"]
 assert digest(receipt)==allocation["sha256"],"lead pin mismatch"
 approval=json.loads(receipt.read_text())
 expected_purpose="repeat" if repeat else "registered"
 assert approval["format"]=="cm3-stage-approval-v1" and approval["stage"]=="fit"
 assert approval["arm"]==arm.split("-")[0] and approval["seed"]==seed
 assert approval["purpose"]==expected_purpose and approval["subset"]=="one-registered-fit"
 assert approval["attempt_id"]==allocation["attempt_id"]
 assert approval["context_sha256"]==p["context_sha256"]
 assert set(approval["predecessors"])=={"inputs","proof128","smoke","extract"}
 assert set(approval["pairing"])=={"path","sha256"}
 expected_predecessors={} if p["phase"]=="phase1" else {"phase1_gate":p["phase1_gate"]["remote_ref"]}
 assert approval["fit_predecessors"]==expected_predecessors
 if p["phase"]=="phase2":
  gate_ref=expected_predecessors["phase1_gate"]
  assert digest(gate_ref["path"])==gate_ref["sha256"],"phase-1 gate bytes changed"
 assert approval["output"]==allocation["output"]
 fit_budget(p,key,approval["budget"])
 assert pathlib.Path(approval["output"]).is_relative_to("/outputs")
 if previous:
  latest=json.loads(previous[-1].read_text())
  ref=latest.get("result")
  if latest.get("status")=="COMPLETE" and ref and digest(ref["path"])==ref["sha256"]:
   result=json.loads(pathlib.Path(ref["path"]).read_text())
   assert pathlib.Path(ref["path"])==pathlib.Path(approval["output"])/"result.json"
   assert result["status"]=="PASS" and result["format"]=="cm3-stage-result-v1"
   assert result["approval"]=={"path":str(receipt),"sha256":allocation["sha256"]}
   assert result["attempt_id"]==allocation["attempt_id"] and result["context_sha256"]==p["context_sha256"]
   return latest
  return {"arm":arm,"seed":seed,"exit":125,"status":"INCOMPLETE",
          "reason":"preempted/partial attempt; new lead receipt, attempt_id and output required"}
 # A fresh lead-issued attempt receipt is required for each explicitly relaunched job.
 record={"arm":arm,"seed":seed,"attempt":attempt,"started_at":time.time(),"status":"RUNNING"}
 marker=task_dir/f"attempt-{attempt}.json";marker.write_text(json.dumps(record));outputs.commit()
 command=[sys.executable,"-m","policy.range_bc.cm3_run","fit","--receipt",str(receipt),
          "--receipt-sha256",allocation["sha256"],"--arm",arm.split("-")[0],"--seed",str(seed)]
 log=task_dir/f"attempt-{attempt}.log"
 with log.open("w") as f:
  proc=subprocess.Popen(command,cwd=code,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
  try:
   exit_code=proc.wait(timeout=min(work_seconds-30,p["absolute_deadline_unix"]-time.time()))
  except subprocess.TimeoutExpired:
   import signal
   os.killpg(proc.pid,signal.SIGKILL);proc.wait();exit_code=124
 result_path=pathlib.Path(approval["output"])/"result.json"
 result_ref=None
 if exit_code==0:
  assert result_path.is_file(),"exit 0 without result"
  result=json.loads(result_path.read_text())
  assert result["format"]=="cm3-stage-result-v1" and result["status"]=="PASS"
  assert result["arm"]==approval["arm"] and result["seed"]==seed and result["purpose"]==expected_purpose
  assert result["approval"]=={"path":str(receipt),"sha256":allocation["sha256"]}
  assert result["context_sha256"]==approval["context_sha256"]
  assert result["attempt_id"]==allocation["attempt_id"]
  result_ref={"path":str(result_path),"sha256":digest(result_path)}
 record.update(exit=exit_code,finished_at=time.time(),status="COMPLETE" if exit_code==0 else "FAILED",
               attempt_id=allocation["attempt_id"],result=result_ref)
 marker.write_text(json.dumps(record));outputs.commit()
 return record


def validate_gate(p):
 ref=p["phase1_gate"]
 assert is_sha(ref["sha256"]) and digest(ref["local_path"])==ref["sha256"],"external phase-1 gate pin mismatch"
 assert ref["remote_ref"]["sha256"]==ref["sha256"]
 gate=json.loads(pathlib.Path(ref["local_path"]).read_text())
 assert gate["format"]=="cm3-phase1-gate-v1" and gate["status"]=="PASS"
 assert gate["approved_by"]=="herdr-lead" and gate["context_sha256"]==p["context_sha256"]
 assert set(gate["outputs"])=={"A0","A1","A2","H0","H0_repeat"}
 assert gate["A_control_gate"]["status"]=="PASS" and set(gate["A_control_gate"]["controls"])=={"0","1","2"}
 assert gate["H0_repeat"]["status"]=="PASS" and gate["H0_repeat"]["repeat_identical"] is True
 assert gate["H0_repeat"]["H0"]==gate["H0_repeat"]["repeat"]
 from datetime import datetime
 assert datetime.fromisoformat(gate["completed"].replace("Z","+00:00")).timestamp()<=time.time()
 # Owner entrypoint recomputes A S and H0 identity from all pinned outputs.
 # Judge independently binds output digests and actual completion/start timestamps.

def validate_harness(b):
 if b.get("transport_v4"):
  from phase_transport import validate_harness_v4
  return validate_harness_v4(b)
 required={"modal_app.py","safety.py","lifecycle.py","guard.py","identity_probe.py","input_closure.py","collector.py","packet_adapter.py","map_metrics.py","job_status.py","cm3_timeouts.py","cm3_budget_plan.py","cm3_accounting.py","task_driver.py","judge_entry.py"}
 require(set(b["harness_code"])==required,"incomplete harness closure")
 for name,h in b["harness_code"].items():require(digest(ROOT/name)==h,"harness source changed: "+name)

def validate_launch(p):
 if p.get("transport_v4"):
  from phase_transport import validate_plan_v4
  return validate_plan_v4(p)
 require(p["integration_review_pass"] and p["fixes2_review_pass"] and p["entrypoint_supports_arm_seed"],"DRAFT: independent review gates not accepted")
 require(p["profile"]=="rivals" and p["workspace"]=="volpestyle","wrong planned account")
 require(p["amendment"]==3 and p["execution_mode"]=="two-phase","not A3")
 for field in ("run_id","campaign_id"):
  require(isinstance(p[field],str) and re.fullmatch("[a-zA-Z0-9_-]{1,80}",p[field]),"unsafe campaign/run identifier")
 numeric_plan(p)
 require(digest(ROOT/"fixes2-files.json")==p["fixes2_freeze_sha256"],"fixes2 candidate changed")
 require(json.loads((ROOT/"fixes2-files.json").read_bytes())["files"]["policy/range_bc/cm3_run.py"]==p["entrypoint_sha256"],"entrypoint changed")
 require(p["judge_sha256"]=="e23b3212a0eadc98bc590e5081a92c9fab6740e93808aba2d245d6020b3f8eb0" and digest(ROOT/"judge_cm3-a3.py")==p["judge_sha256"],"judge changed")
 require(digest(ROOT/"FIT-RECEIPT.md")==p["contract_sha256"] and digest(ROOT/"FIT-RECEIPT-a3.md")==p["a3_contract_sha256"],"contract changed")
 require(isinstance(p["reviewed_image_digest"],str) and re.fullmatch(r"[^\s]+@sha256:[0-9a-f]{64}",p["reviewed_image_digest"]),"immutable image digest required")
 relative(p["code_directory"])
 require(p["phase1_gate"] is None,"phase1 cannot supply a gate") if p["phase"]=="phase1" else validate_gate(p)
 seen_ids=set();seen_outputs=set();seen_receipts=set()
 for task in p["tasks"].values():
  require(len(task["attempt_receipts"])==1,"one attempt receipt required")
  a=task["attempt_receipts"][0];relative(a["path"]);sha(a["sha256"])
  output=remote_path(a["output"])
  require(output.is_relative_to("/outputs") and not output.is_relative_to("/outputs/.modal-journal"),"reserved/invalid output namespace")
  require(a["attempt_id"] not in seen_ids and a["output"] not in seen_outputs and a["sha256"] not in seen_receipts,"duplicate attempt/output/receipt")
  require(isinstance(a["attempt_id"],str) and re.fullmatch(r"[A-Za-z0-9_-]{1,80}",a["attempt_id"]),"unsafe attempt ID")
  seen_ids.add(a["attempt_id"]);seen_outputs.add(a["output"]);seen_receipts.add(a["sha256"])
 b=validate_binding(p)
 require(b["run_id"]==p["run_id"] and b["phase"]==p["phase"] and b["tasks_sha256"]==canonical(p["tasks"]) and b["tasks"]==p["tasks"],"task routing not lead bound")
 validate_harness(b)
 context=document(p["approved_context"])
 validate_input(p,context)
 ledger(p,ROOT/"campaigns"/p["campaign_id"]/"reservations")
 return b

def _orchestrate(p):
 require(DEPLOYMENT_ENABLED,"DRAFT: paid launch disabled pending independent delta review and lead approval")
 b=validate_launch(p)
 expected={"profile":"rivals","workspace":"volpestyle","workspace_id":b["workspace_id"]}
 client,identity=connect_verified(expected)
 if p.get("transport_v4"):
  from phase_transport import preflight_cloud
  preflight_cloud(p,client,identity)
 local,bounds=reserve(p,pathlib.Path(p["campaigns_directory"]) if p.get("transport_v4") else ROOT/"campaigns",identity)
 atomic(local/"runtime.json",{"plan":p,"phase_directory":str(local.resolve())})
 runtime_ref={"path":str((local/"runtime.json").resolve()),"sha256":digest(local/"runtime.json")}
 guards={};children={};completed={};results={};failure=None
 def alive_guards():
  for key,g in guards.items():
   if key not in completed:require(g.poll() is None,"task watchdog died: "+key)
 def start_guard(key):
  task=local/key
  with (task/"guard.log").open("x") as log:
   g=subprocess.Popen([sys.executable,str(ROOT/"guard.py"),str(task)],stdin=subprocess.DEVNULL,
                      stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  atomic(task/"guard-pid.json",{"pid":g.pid});guards[key]=g
 try:
  # All independent watchdogs must be live before the first paid app creation.
  for key in sorted(p["tasks"]):start_guard(key)
  ready_until=time.monotonic()+10
  while not all((local/k/"guard-ready.json").exists() for k in p["tasks"]):
   alive_guards();require(time.monotonic()<ready_until,"watchdogs unavailable");time.sleep(.1)
  for key in sorted(p["tasks"]):
   alive_guards();running_bound(bounds,completed=completed)
   with (local/key/"driver.log").open("x") as log:
    children[key]=subprocess.Popen([sys.executable,str(ROOT/"approved_task_entry.py"),str(local/key),
                                   runtime_ref["path"],runtime_ref["sha256"]],
                                  stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  pending=set(children);last_report=0
  while pending:
   # Settle completed app clocks before evaluating shorter task deadlines.
   for key in list(pending):
    code=children[key].poll()
    if code is None:continue
    path=local/key/"wrapper-result.json"
    result=json.loads(path.read_bytes()) if path.exists() else finish_task(local/key,reason="child exited without record")
    results[key]=result;pending.remove(key)
    require(result["measured_settlement_eligible"],"task cleanup unverified; retain hold")
    completed[key]=result["spend"]["seconds_through_cleanup"]
    require(code==0 and result["status"]=="COMPLETE" and not result["over_hold"],"fit incomplete; no retry or advancement")
   alive_guards()
   atomic(local/"spend.json",{"gross_upper_usd":running_bound(bounds,completed=completed),
                             "completed_seconds":completed,"pending":sorted(pending)})
   if time.monotonic()-last_report>=30 or not pending:
    report(p,"running",{"n":len(completed),"total":len(p["tasks"])},local/"spend.json");last_report=time.monotonic()
   if pending:time.sleep(.25)
 except BaseException as exc:
  failure=str(exc)
 finally:
  # Stop only our children; each remote app has its own independent watchdog too.
  import signal,concurrent.futures
  for child in children.values():
   if child.poll() is None:
    try:os.killpg(child.pid,signal.SIGKILL)
    except ProcessLookupError:pass
  for child in children.values():child.wait()
  def finish(key):
   worker_path=local/key/"worker.json"
   worker=json.loads(worker_path.read_bytes()) if worker_path.exists() else None
   return finish_task(local/key,worker,reason=failure)
  # Concurrent cleanup preserves the 120s reserve for every slot.
  with concurrent.futures.ThreadPoolExecutor(max_workers=len(p["tasks"])) as pool:
   for key,result in zip(sorted(p["tasks"]),pool.map(finish,sorted(p["tasks"]))):results[key]=result
  refs={key:{"path":str((local/key/"wrapper-result.json").resolve()),"sha256":digest(local/key/"wrapper-result.json")} for key in results}
  atomic(local/"phase-result.json",{"format":"cm3-phase-summary-v1","status":"INCOMPLETE" if failure else "COMPLETE",
       "separately_charged":False,"task_results":refs,"failure":failure,"artifacts_collected":False})
 require(failure is None,failure or "phase incomplete")
 require(all(r["status"]=="COMPLETE" and r["measured_settlement_eligible"] and not r["over_hold"] for r in results.values()),
         "INCOMPLETE_CLEANUP; campaign stays reserved")
 atomic(local/"driver.exit.json",{"exit":0,"artifacts_collected":False})
 return local

def report(p,stage,progress,evidence):
 import job_status
 return job_status.write("cm3-"+p["run_id"],owner="modal-port",host="modal",stage=stage,
                         progress=progress,eta=None,evidence=str(pathlib.Path(evidence).resolve()))

def orchestrate(p):
 # Receipts report lifecycle; they confer no execution approval.
 require(isinstance(p.get("run_id"),str) and re.fullmatch("[a-zA-Z0-9_-]{1,80}",p["run_id"]),"unsafe run ID")
 evidence=ROOT/("lifecycle-"+p["run_id"]+".json")
 require(not evidence.exists(),"fresh lifecycle required")
 atomic(evidence,{"status":"validating","launch_enabled":DEPLOYMENT_ENABLED})
 report(p,"running","Validating approvals, budget, closure and identity",evidence)
 try:
  result=_orchestrate(p)
 except BaseException as exc:
  atomic(evidence,{"status":"failed","reason":str(exc)})
  report(p,"failed","Incomplete; see lifecycle and cleanup evidence",evidence)
  raise
 atomic(evidence,{"status":"done","run_directory":str(result),"artifacts_collected":False})
 report(p,"done","Execution ended; artifact collection and judging remain separate",evidence)
 return result

def main():
 parser=argparse.ArgumentParser();parser.add_argument("--launch",action="store_true");args=parser.parse_args()
 if args.launch and not DEPLOYMENT_ENABLED:raise SystemExit("DRAFT: paid launch disabled pending independent delta review and lead approval")
 p=read_plan()
 if not args.launch:
  print(json.dumps({"draft":True,"mandatory_A3_executions":13,"gpu":"L40S","launch_enabled":False},indent=2));return
 orchestrate(p)
if __name__=="__main__":main()
