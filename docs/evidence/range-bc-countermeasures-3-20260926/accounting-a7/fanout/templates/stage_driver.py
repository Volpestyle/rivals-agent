"""One lead-approved inputs attempt; frozen fit launcher remains disabled."""
import pathlib,json,hashlib,sys,os,time,subprocess,uuid,math
BASE=pathlib.Path(__file__).resolve().parent
OLD=BASE.parent/"f5-real";FROZEN=BASE/"wrapper-runtime"
sys.path.insert(0,str(FROZEN))
from lifecycle import connect_verified,locked,atomic,update_inventory,cleanup,verify_client,Backend
import job_status
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def immutable(path,x):
 with pathlib.Path(path).open("x") as f:json.dump(x,f,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
def main():
 authority=json.loads((BASE/"authority.json").read_text())
 assert authority["sender"]=="c302f78b-5125-4d15-91cb-8e2c8cf04b80" and authority["senderGeneration"]==2
 assert sha(BASE/"launch-binding.proposal.json")==authority["binding_sha256"]
 assert sha(BASE/"approvals.at-launch.json")==authority["ledger_sha256"]
 b=json.loads((BASE/"launch-binding.proposal.json").read_text());budget=b["budget"]
 ledger=json.loads((BASE/"approvals.at-launch.json").read_text())["approvals"]
 def approved(stage,path,pin):
  assert any(a["stage"]==stage and a["path"]==path and a["sha256"]==pin and a["approver"]=="herdr-lead" and a["approved_at"] for a in ledger)
 approved("smoke-03-driver","handoff/modal/smoke03-proposal/launch-binding.proposal.json",authority["binding_sha256"])
 approved("smoke",b["receipt"]["path"],b["receipt"]["sha256"])
 approved("common-context-inputs05",b["context_ref"]["path"],b["context_ref"]["sha256"])
 for name,pin in b["executor_files"].items():assert sha(BASE/name)==pin
 for name,pin in b["wrapper_runtime"].items():assert sha(FROZEN/name)==pin
 for field in ("input_manifest","input_witness"):assert sha(b[field]["local_path"])==b[field]["sha256"]
 for remote,row in b["control_artifacts"].items():assert sha(row["local_path"])==row["sha256"]
 for remote,row in b["external_artifacts"].items():assert sha(row["local_path"])==row["sha256"]
 assert sha(b["source_inputs_collection"]["local_path"])==b["source_inputs_collection"]["sha256"]
 assert b["image_id"]=="im-tE3Y0YrWYZ0po0yAA0JQT8" and b["image_rebuild"] is False
 assert b["gpu"]=="L40S" and b["runner_class"]=="cuda:L40S"
 assert b["benchmark_provider"]=="modal" and b["judge_instance"]==b["judge_model"]=="modal:L40S"
 for value in budget.values():assert type(value) in (int,float) and math.isfinite(value) and value>=0
 assert budget["work_seconds"]==600 and budget["reserved_seconds"]==1020
 assert budget["overhead_usd"]+budget["reserved_seconds"]*budget["rate_usd_second"]<=budget["reserved_usd"]+1e-12
 assert budget=={"cap_seconds":69120,"cap_usd":60,"cleanup_seconds":120,"overhead_usd":0.2678032,
 "prior_seconds":24373,"prior_usd":19.35691756,"rate_usd_second":0.00071784,"reserved_seconds":1020,
 "reserved_usd":1,"startup_seconds":300,"work_seconds":600}
 campaign=OLD/"bootstrap-campaign"
 client,identity=connect_verified(b["identity"])
 backend=Backend(identity)
 from volume_scope import no_volume_conflicts
 def no_other_readers(owned=()):
  return no_volume_conflicts(client,backend,[b["input_volume_id"],b["output_volume_id"]],owned)
 idle=no_other_readers()
 import modal
 input_handle=modal.Volume.from_id(b["input_volume_id"],client=client)
 old_manifest=json.loads(pathlib.Path(b["input_manifest"]["local_path"]).read_text())
 found={x.path:x.size for x in input_handle.iterdir("/",recursive=True) if x.type==modal.volume.FileEntryType.FILE}
 assert found=={r["path"]:r["bytes"] for r in old_manifest["files"]},"predecessor inventory mismatch before paid work"
 output_handle=modal.Volume.from_id(b["output_volume_id"],client=client)
 for x in output_handle.iterdir("/",recursive=True):
  assert not any(x.path==p or x.path.startswith(p+"/") for p in [b["output"].removeprefix("/outputs/"),b["journal"].removeprefix("/outputs/"),b["control_directory"].removeprefix("/outputs/")]),"fresh output/journal exists"
 with locked(campaign/"campaign.lock"):
  from admission import admit
  totals=admit(b);spent_usd=totals["spent_usd"];spent_seconds=totals["spent_seconds"]
  from stage_pacing import admit_live
  admit_live(b,client)
  start=time.time();mono=time.monotonic()
  local=campaign/"smoke-03";local.mkdir(exist_ok=False)
  immutable(local/"reservation.json",{"attempt_id":"smoke-03","reserved_usd":1,"reserved_compute_seconds":1020,
    "prior_committed_usd":spent_usd,"campaign_committed_usd":spent_usd+1,"prior_compute_seconds":spent_seconds,
    "campaign_reserved_seconds":spent_seconds+1020,"approval_ledger_sha256":authority["ledger_sha256"],
    "approved_receipt_sha256":b["receipt"]["sha256"],"authorization_swarm_message":authority["message_id"],
    "binding_sha256":sha(BASE/"launch-binding.proposal.json"),"driver_sha256":sha(__file__),"worker_sha256":sha(BASE/"stage_worker.py"),
    "control_worker_sha256":sha(BASE/"control_worker.py"),"bounds":budget,"automatic_retries":0,"resume":False})
  atomic(local/"inventory.json",{"identity":identity,"app_name":"rivals-cm3-smoke-03-"+uuid.uuid4().hex[:12],
   "apps":[],"calls":{},"creation_started":False,"creation_finished":False,"driver_pid":os.getpid(),
   "bounds":{"started_at_unix":start,"started_monotonic":mono,"appcreate_seconds":300,"stop_at_unix":start+900,"stop_monotonic":mono+900}})
 immutable(local/"no-active-readers.initial.json",idle)
 guardlog=(local/"guard.log").open("x")
 guard=subprocess.Popen([sys.executable,str(FROZEN/"guard.py"),str(local)],stdout=guardlog,stderr=subprocess.STDOUT,start_new_session=True)
 for _ in range(100):
  if (local/"guard-ready.json").exists():break
  assert guard.poll() is None
  time.sleep(.05)
 assert (local/"guard-ready.json").exists()
 def report(message,stage="running"):
  job_status.write("cm3-smoke-03",owner="modal-port",host="modal",stage=stage,progress=message,eta=None,evidence=str(local/"inventory.json"))
 result=None;error=None;restore_pacing=None
 try:
  report("Guard active; smoke-only, $1 reserved including startup/teardown")
  import modal
  from stage_worker import run_smoke
  from control_worker import write_control
  verify_client(client,identity)
  inv=json.loads((local/"inventory.json").read_text());app=modal.App(inv["app_name"])
  image=modal.Image.from_id(b["image_id"],client=client).add_local_python_source("input_closure","safety","volume_inventory","diagnostic_capture","control_transport")
  inputs=modal.Volume.from_id(b["input_volume_id"],client=client).read_only()
  outputs=modal.Volume.from_id(b["output_volume_id"],client=client)
  function=app.function(image=image,gpu="L40S",cpu=(8,8),memory=(32768,32768),volumes={"/inputs":inputs,"/outputs":outputs},
      retries=0,timeout=600,startup_timeout=150,single_use_containers=True)(run_smoke)
  transition_function=app.function(image=image,cpu=(8,8),memory=(32768,32768),nonpreemptible=True,
      volumes={"/outputs":outputs},
      retries=0,timeout=600,startup_timeout=150,single_use_containers=True)(write_control)
  spec={"binding":b,"manifest_text":pathlib.Path(b["input_manifest"]["local_path"]).read_text(),"witness_bytes":pathlib.Path(b["input_witness"]["local_path"]).read_bytes()}
  def funded():
   assert guard.poll() is None and time.monotonic()<mono+900 and time.time()<start+900,"funded deadline/guard"
  from stage_pacing import install
  restore_pacing=install(client,local,b,funded)
  update_inventory(local,lambda x:x.update(creation_started=True))
  with modal.enable_output(),app.run(client=client),modal.Dict.ephemeral(client=client) as claim:
   update_inventory(local,lambda x:x.update(apps=[app.app_id],creation_finished=True))
   assert time.monotonic()-mono<900
   spec["claim_dict_id"]=claim.object_id
   immutable(local/"invocation-claim.json",{"dict_id":claim.object_id,"key":"smoke-03-started","skip_if_exists":True})
   transition_spec={"binding":b,"claim_dict_id":claim.object_id,"control_payload":{name:pathlib.Path(row["local_path"]).read_bytes() for name,row in b["control_writes"].items()}}
   transition_call=transition_function.spawn(transition_spec)
   update_inventory(local,lambda x:x["calls"].update(transition=transition_call.object_id))
   while True:
    remaining=900-(time.monotonic()-mono);assert remaining>0,"funded deadline"
    try:transition_result=transition_call.get(timeout=min(10,remaining));break
    except (TimeoutError,modal.exception.TimeoutError):report("Exclusive control receipt staging")
   assert transition_result["status"]=="PASS"
   immutable(local/"transition-result.json",transition_result)
   # Prove CPU container termination before starting the GPU: no concurrent billing/readers.
   transition_stop_deadline=min(mono+900,time.monotonic()+30)
   while any(c["app_id"]==app.app_id for c in backend.containers(5)):
    assert time.monotonic()<transition_stop_deadline,"transition container did not terminate"
    time.sleep(.5)
   immutable(local/"no-active-readers.before-inputs.json",no_other_readers({app.app_id}))
   # Workers are serial; the total work allocation is shared, never reset for stage two.
   spec["remaining_work_seconds"]=min(600-transition_result["work_seconds"],890-(time.monotonic()-mono))
   assert spec["remaining_work_seconds"]>20,"transition exhausted inputs allocation"
   report("Control staged; read-only metadata gate and one owner smoke invocation")
   call=function.spawn(spec)
   update_inventory(local,lambda x:x["calls"].update(smoke=call.object_id))
   while True:
    remaining=900-(time.monotonic()-mono);assert remaining>0,"funded deadline"
    try:result=call.get(timeout=min(20,remaining));break
    except (TimeoutError,modal.exception.TimeoutError):
     report("Metadata inventory verification / owner smoke running; conservative bound $"+format(budget["overhead_usd"]+(time.monotonic()-mono)*budget["rate_usd_second"],".4f"))
   assert result["status"]=="PASS"
   immutable(local/"completed.json",result)
 except BaseException as exc:
  error=type(exc).__name__+": "+str(exc);immutable(local/"INCOMPLETE.json",{"status":"INCOMPLETE","error":error})
 finally:
  if restore_pacing is not None:
   try:restore_pacing()
   except BaseException as exc:error=error or ("pacing restore: "+str(exc))
  terminal=cleanup(local)
  elapsed=time.monotonic()-mono
  estimate=budget["overhead_usd"]+elapsed*budget["rate_usd_second"]
  passed=result is not None and error is None and terminal["status"]=="TERMINAL" and estimate<=1
  receipt={"format":"cm3-inputs-wrapper-result-v1","status":"PASS" if passed else "INCOMPLETE","attempt_id":"smoke-03",
   "binding":{"path":str(BASE/"launch-binding.proposal.json"),"sha256":sha(BASE/"launch-binding.proposal.json")},
   "owner_result":result["result_ref"] if passed else None,"transport_files":result["files"] if passed else [],
   "error":error,"teardown":terminal,"spend":{"reserved_charged_usd":1,"estimated_conservative_usd":estimate,
       "seconds_through_cleanup":elapsed,"campaign_committed_usd":spent_usd+1,"campaign_reserved_seconds":spent_seconds+1020},
   "transition_result_sha256":sha(local/"transition-result.json") if (local/"transition-result.json").exists() else None,
   "completed_sha256":sha(local/"completed.json") if (local/"completed.json").exists() else None}
  immutable(local/"result.json",receipt)
  (BASE/"driver.exit").write_text("0\n" if passed else "1\n")
  report(receipt["status"]+"; "+terminal["status"],"done" if passed else "failed")
  print(json.dumps({"status":receipt["status"],"sha256":sha(local/"result.json"),"result":str(local/"result.json"),"error":error}),flush=True)
 return 0 if passed else 1
if __name__=="__main__":sys.exit(main())
