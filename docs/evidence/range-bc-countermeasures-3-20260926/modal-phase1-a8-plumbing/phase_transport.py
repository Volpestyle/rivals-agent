"""Approved mount, identity and metadata transport adapter; no budget or science formulas."""
import pathlib,json,time,hashlib,os
from safety import require,digest,document,canonical,validate_binding,numeric_plan,ledger,relative,fit_budget,PHASE1
from lifecycle import verify_client,Backend,atomic
ROOT=pathlib.Path(__file__).resolve().parent
IDENTITY={"profile":"rivals","workspace":"volpestyle","workspace_id":"ac-kMLf5bJKqF5CAlSbfNhGh0"}
def read(path):return json.loads(pathlib.Path(path).read_bytes())
def validate_harness_v4(b):
 require(b.get("transport_v4") is True,"transport version")
 for name,pin in b["harness_code"].items():
  relative(name);require(digest(ROOT/name)==pin,"harness bytes changed: "+name)
 require(set(b["harness_code"])==set(read(ROOT/"harness-files.json")),"incomplete harness closure")
 require(b["source_review"]["manifest_sha256"]=="09f0e5ea9acaeae510cff9ab367fbf7d67fdc8c8cfb47241bd9cf10a1781cdf2","review source changed")
def validate_authority(p):
 require(p.get("transport_v4") is True and p["phase"]=="phase1","this adapter only permits phase1")
 require(p["launch_binding"]["local_path"]==str(ROOT/"launch-binding.proposal.json"),"binding path")
 a=read(ROOT/"authority.json")
 require(a["sender"]=="c302f78b-5125-4d15-91cb-8e2c8cf04b80" and a["senderGeneration"]==2,"lead identity")
 require(a["binding_sha256"]==p["launch_binding"]["sha256"]==digest(ROOT/"launch-binding.proposal.json"),"lead driver pin")
 require(a["ledger_sha256"]==digest(ROOT/"approvals.at-launch.json"),"ledger pin")
 rows=read(ROOT/"approvals.at-launch.json")["approvals"];b=document(p["launch_binding"])
 def approved(stage,ref):
  require(any(r.get("stage")==stage and r.get("path")==ref["path"] and r.get("sha256")==ref["sha256"] and r.get("approver")=="herdr-lead" and r.get("approved_at") for r in rows),"missing exact approval "+stage)
 approved("phase1-02-driver",{"path":"handoff/modal/phase102-proposal/launch-binding.proposal.json","sha256":a["binding_sha256"]})
 approved("budget",b["budget_approval"])
 approved("common-context-inputs07",b["context_ref"])
 for key,task in p["tasks"].items():
  v=task["attempt_receipts"][0];approved("fit",{"path":p["receipt_root"]+"/"+v["path"],"sha256":v["sha256"]})
 validate_harness_v4(b)
 return b
def validate_plan_v4(p):
 b=validate_authority(p);numeric_plan(p);validate_binding(p)
 require(p["run_id"]=="phase1-02" and p["campaign_id"]=="r3-20260926-l40s","run namespace")
 require(set(p["tasks"])==PHASE1 and p["phase1_gate"] is None,"A3 phase1")
 require(b["tasks"]==p["tasks"] and b["tasks_sha256"]==canonical(p["tasks"]),"routing pin")
 require(p["campaigns_directory"]==b["campaigns_directory"]==str(ROOT.parent/"campaigns"),"campaign root")
 for key in ("input_version_id","receipt_root","image_id","input_witness","control_manifest","extraction_collection","extraction_result","control_refs","diagnostic_contract","plumbing_review_pending","review_policy"):
  require(p[key]==b[key],"transport binding changed: "+key)
 require(p["receipt_root"]=="/outputs/.modal-control/phase1-02/receipts","receipt namespace")
 require(p["plumbing_review_pending"] is True and p["review_policy"]=="plumbing-delta-review-before-verdict","review policy")
 require(p["image_id"]=="im-tE3Y0YrWYZ0po0yAA0JQT8","existing captured image only")
 require(p["entrypoint_sha256"]=="7f27cd5d777ac24294083878379daf4d2a276b263c8131ffb568dd92c69693bd","reviewed LF owner")
 context=document(p["approved_context"])
 from input_closure import bind_context
 manifest=document(p["input_manifest"]);bind_context(manifest,context,b["control_refs"])
 require(manifest["volume_id"]==p["input_volume_id"] and manifest["code_directory"]==p["code_directory"],"input volume/code binding")
 require(context["code"]["policy/range_bc/cm3_run.py"]==p["entrypoint_sha256"],"context/owner")
 witness=document(p["input_witness"]);full=witness["full_verification"]
 require(witness["version_id"]==p["input_version_id"],"input version binding changed")
 require(witness["manifest_sha256"]==p["input_manifest"]["sha256"] and witness["volume_id"]==p["input_volume_id"],"witness binding")
 require(full["status"]=="PASS" and full["exact_inventory"] and full["sealed_excluded"] and full["manifest_sha256"]==p["input_manifest"]["sha256"],"full input verification")
 collection=document(p["extraction_collection"])
 require(collection["status"]=="PASS" and collection["stage"]=="extract" and collection["teardown"]["status"]=="TERMINAL","extraction unverified")
 control=document(p["control_manifest"]);validate_control_manifest(p,control)
 require(control["input_manifest_sha256"]==p["input_manifest"]["sha256"],"control/input closure")
 from make_receipt import Writer
 authority=read(ROOT/"approvals.at-launch.json")
 outputs=pathlib.Path(p["extraction_collection"]["local_path"]).parent/"artifacts/outputs"
 ids=set();paths=set()
 for key,task in p["tasks"].items():
  allocation=task["attempt_receipts"][0];relative(allocation["path"])
  state=read(ROOT/"states"/(key+".json"))
  writer=Writer(context,state,authority,[(p["receipt_root"],ROOT/"receipts"),("/outputs/.modal-control/phase1-02/accounting",ROOT/"accounting"),("/outputs",outputs)])
  receipt=writer.stage("fit",allocation["output"],task=key,attempt=allocation["attempt_id"])
  require(receipt==read(ROOT/"receipts"/allocation["path"]),"Writer receipt mismatch")
  require(digest(ROOT/"receipts"/allocation["path"])==allocation["sha256"],"receipt pin")
  require(receipt["predecessors"]["extract"]==collection["owner_result"],"selected extraction mismatch")
  fit_budget(p,key,receipt["budget"])
  require(allocation["attempt_id"] not in ids and allocation["output"] not in paths,"duplicate fit attempt/output")
  ids.add(allocation["attempt_id"]);paths.add(allocation["output"])
 ledger(p,pathlib.Path(p["campaigns_directory"])/p["campaign_id"]/"reservations")
 return b
def validate_control_manifest(p,m):
 require(m["format"]=="cm3-phase-control-manifest-v1" and m["approved_by"]=="herdr-lead","control schema")
 require(m["root"]=="/outputs/.modal-control/phase1-02" and m["identity"]==IDENTITY,"control namespace/identity")
 require(m["output_volume_id"]==p["output_volume_id"] and m["tasks_sha256"]==canonical(p["tasks"]),"control route")
 require(0<len(m["files"])==101 and sum(r["bytes"] for r in m["files"].values())<=8*1024**2,"control bound")
 for name,row in m["files"].items():
  remote=pathlib.PurePosixPath(name)
  require(str(remote)==name and remote.is_relative_to(m["root"]) and ".." not in remote.parts and remote.suffix==".json","control path")
  require(type(row["bytes"]) is int and 0<row["bytes"]<=1024**2,"control file bound")
  rel=relative(row["local_path"]);require(name==m["root"]+"/"+str(rel),"control/local routing mismatch")
  source=ROOT/rel
  require(source.resolve().is_relative_to(ROOT.resolve()) and not source.is_symlink(),"control source escape")
  require(source.stat().st_size==row["bytes"] and digest(source)==row["sha256"],"control source bytes changed")
 for key,task in p["tasks"].items():
  a=task["attempt_receipts"][0];require(m["files"][p["receipt_root"]+"/"+a["path"]]["sha256"]==a["sha256"],"receipt omitted from controls")
 return m
def preflight_cloud(p,client,identity):
 verify_client(client,identity)
 from volume_scope import no_volume_conflicts
 no_volume_conflicts(client,Backend(identity),[p["input_volume_id"],p["output_volume_id"]],())
 import modal
 manifest=document(p["input_manifest"])
 v=modal.Volume.from_id(p["input_volume_id"],client=client)
 found={x.path:x.size for x in v.iterdir("/",recursive=True) if x.type==modal.volume.FileEntryType.FILE}
 require(found=={r["path"]:r["bytes"] for r in manifest["files"]},"input inventory changed")
 prefixes=[".modal-control/phase1-02",".modal-journal/phase1-02"]
 prefixes += [a["output"].removeprefix("/outputs/") for t in p["tasks"].values() for a in t["attempt_receipts"]]
 out=modal.Volume.from_id(p["output_volume_id"],client=client)
 for x in out.iterdir("/",recursive=True):
  require(not any(x.path==q or x.path.startswith(q+"/") for q in prefixes),"fresh phase namespace already exists")
def build_app_v4(p,identity,client,key):
 verify_client(client,identity);require(identity==IDENTITY==p["verified_identity"] and p["selected_task"]==key,"task identity")
 import modal
 from phase_worker import run_fit_v4,stage_controls
 image=modal.Image.from_id(p["image_id"],client=client).add_local_python_source("safety","input_closure","cm3_accounting","cm3_timeouts","cm3_budget_plan","volume_inventory","diagnostic_capture","phase_worker")
 app=modal.App(p["owned_app_name"]);outputs=modal.Volume.from_id(p["output_volume_id"],client=client)
 function=app.function(image=image,gpu="L40S",cpu=(8,8),memory=(32768,32768),
  volumes={"/inputs":modal.Volume.from_id(p["input_volume_id"],client=client).read_only(),"/outputs":outputs},
  retries=0,timeout=p["attempt_timeout_seconds_by_arm"][key[0]],startup_timeout=150,single_use_containers=True)(run_fit_v4)
 control=None
 if key=="A-0":
  control=app.function(image=image,cpu=(8,8),memory=(32768,32768),nonpreemptible=True,
   volumes={"/outputs":outputs},retries=0,timeout=150,startup_timeout=150,single_use_containers=True)(stage_controls)
 class Prepared:
  def spawn(self,arm,seed,purpose,task_plan):
   from lifecycle import guard_reason
   local=pathlib.Path(p["task_local_directory"]);ready=local.parent/"controls-ready.json"
   def funded():
    require(guard_reason(read(local/"inventory.json")) is None,"funded deadline during control handoff")
   funded()
   if key=="A-0":
    manifest=document(p["control_manifest"])
    payload={name:(ROOT/row["local_path"]).read_bytes() for name,row in manifest["files"].items()}
    result=control.remote({"plan":task_plan,"manifest":manifest,"manifest_bytes":pathlib.Path(p["control_manifest"]["local_path"]).read_bytes(),"payload":payload})
    require(result["status"]=="PASS" and result["manifest_sha256"]==p["control_manifest"]["sha256"],"control stage mismatch")
    backend=Backend(identity);deadline=min(time.time()+30,p["absolute_deadline_unix"])
    while any(c["app_id"]==app.app_id for c in backend.containers(5)):
     funded();require(time.time()<deadline,"control container did not terminate");time.sleep(.5)
    atomic(ready,result)
   else:
    while not ready.exists():funded();time.sleep(.25)
    require(read(ready)["manifest_sha256"]==p["control_manifest"]["sha256"],"wrong controls-ready")
   funded()
   task_plan["input_manifest_text"]=pathlib.Path(p["input_manifest"]["local_path"]).read_text()
   task_plan["input_witness_bytes"]=pathlib.Path(p["input_witness"]["local_path"]).read_bytes()
   task_plan["control_manifest_bytes"]=pathlib.Path(p["control_manifest"]["local_path"]).read_bytes()
   return function.spawn(arm,seed,purpose,task_plan)
 return app,Prepared()
