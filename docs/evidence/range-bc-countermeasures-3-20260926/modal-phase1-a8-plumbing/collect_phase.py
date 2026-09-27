"""Bounded phase transport; scientific results stay unmodified, gate/judge remain separate."""
import pathlib,json,hashlib,sys,signal,time
from safety import digest,document,require,remote_path
from collector import refs
from lifecycle import connect_verified,atomic
from phase_transport import validate_authority
ROOT=pathlib.Path(__file__).resolve().parent
def main():
 signal.alarm(1800)
 p=json.loads((ROOT/"phase1-plan.json").read_bytes());b=validate_authority(p)
 phase=pathlib.Path(p["campaigns_directory"])/p["campaign_id"]/p["run_id"]
 summary=json.loads((phase/"phase-result.json").read_bytes())
 require(summary["status"]=="COMPLETE" and set(summary["task_results"])==set(p["tasks"]),"phase incomplete")
 rows={};selected=[]
 for key,ref in summary["task_results"].items():
  require(ref["path"]==str(phase/key/"wrapper-result.json") and digest(ref["path"])==ref["sha256"],"wrapper result pin")
  wrapper=json.loads(pathlib.Path(ref["path"]).read_bytes())
  require(wrapper["status"]=="COMPLETE" and wrapper["measured_settlement_eligible"] and not wrapper["over_hold"],"unsettled/incomplete fit")
  require(wrapper["teardown"]["status"]=="TERMINAL" and any(e.get("containers")==0 for e in wrapper["teardown"]["events"]),"unproven teardown")
  worker=wrapper["worker"];a=p["tasks"][key]["attempt_receipts"][0]
  require(worker["result"]==wrapper["owner_result"] and worker["attempt_id"]==a["attempt_id"],"attempt reference")
  verification=worker["mounted_verification"]
  require(verification["status"]=="PASS" and verification["witness_sha256"]==p["input_witness"]["sha256"] and verification["volume_id"]==p["input_volume_id"] and verification["version_id"]==p["input_version_id"] and verification["payload_bytes_read"]==0,"mounted closure verification")
  require(0<len(worker["files"])<=64 and sum(x["bytes"] for x in worker["files"])<=2*1024**3,"owner output bound")
  for row in worker["files"]:
   require(row["path"].startswith(a["output"]+"/") and row["path"] not in rows,"output namespace/duplicate")
   rows[row["path"]]=row
  selected.append({"task":key,"attempt_id":a["attempt_id"],"arm":key[0],"seed":int(key[-1]),"purpose":"repeat" if key=="H-repeat-0" else "registered",
    "output":a["output"],"approval_ref":{"path":p["receipt_root"]+"/"+a["path"],"sha256":a["sha256"]},
    "context_sha256":p["context_sha256"],"result_ref":worker["result"],"wrapper_result":ref})
 predecessor=document(p["extraction_collection"]);source_root=pathlib.Path(p["extraction_collection"]["local_path"]).parent/"artifacts"
 external={r["path"]:r for r in predecessor["files"]}
 for name,row in external.items():
  require(name not in rows,"current/predecessor namespace overlap");rows[name]=row
 controls=document(p["control_manifest"])
 for name,row in controls["files"].items():
  require(name not in rows,"new/existing control overlap")
  rows[name]={"path":name,"bytes":row["bytes"],"sha256":row["sha256"]}
 require(len(rows)<=1024 and sum(r["bytes"] for r in rows.values())<=15*1024**3,"bounded full closure")
 dest=ROOT/"collection";dest.mkdir(exist_ok=False);partial=dest/"partial";partial.mkdir()
 client,identity=connect_verified({"profile":"rivals","workspace":"volpestyle","workspace_id":"ac-kMLf5bJKqF5CAlSbfNhGh0"})
 import modal,job_status
 vol=modal.Volume.from_id(p["output_volume_id"],client=client)
 entries={x.path:x.size for x in vol.iterdir("/",recursive=True) if x.type==modal.volume.FileEntryType.FILE}
 for s in selected:
  prefix=s["output"].removeprefix("/outputs/")+"/"
  actual={path:size for path,size in entries.items() if path.startswith(prefix)}
  expected={r["path"].removeprefix("/outputs/"):r["bytes"] for r in rows.values() if r["path"].startswith(s["output"]+"/")}
  require(actual==expected,"owner inventory changed")
 total=0;docs={};started=time.monotonic()
 for i,row in enumerate(rows.values(),1):
  path=remote_path(row["path"]);target=partial/path.relative_to("/");target.parent.mkdir(parents=True,exist_ok=True)
  require(type(row["bytes"]) is int and 0<=row["bytes"]<=4*1024**3,"file bound")
  def chunks():
   if row["path"] in external:
    old=source_root/path.relative_to("/")
    require(old.is_file() and not old.is_symlink() and old.stat().st_size==row["bytes"],"predecessor artifact missing")
    with old.open("rb") as f:
     while chunk:=f.read(1024**2):yield chunk
   else:yield from vol.read_file(str(path.relative_to("/outputs")))
  h=hashlib.sha256();size=0
  with target.open("xb") as f:
   for chunk in chunks():
    size+=len(chunk);total+=len(chunk)
    require(size<=row["bytes"] and total<=15*1024**3 and time.monotonic()-started<1800,"collection bound")
    f.write(chunk);h.update(chunk)
  require(size==row["bytes"] and h.hexdigest()==row["sha256"],"corrupt artifact "+str(path))
  if path.suffix==".json":
   require(size<=64*1024**2,"oversize JSON");docs[str(path)]=json.loads(target.read_bytes())
  job_status.write("cm3-phase1-02-collect",owner="modal-port",host="mac",stage="running",progress={"n":i,"total":len(rows)},eta=None,evidence=str(ROOT/"collection.log"))
 # Diagnostic journals are bounded evidence, never a substitute for owner PASS.
 diagnostics=[]
 for name,size_expected in entries.items():
  if not name.startswith(".modal-journal/"+p["run_id"]+"/"):continue
  require(size_expected<=64*1024**2 and len(diagnostics)<40,"diagnostic bound")
  target=partial/"outputs"/name;target.parent.mkdir(parents=True,exist_ok=True)
  h=hashlib.sha256();size=0
  with target.open("xb") as f:
   for chunk in vol.read_file(name):
    size+=len(chunk);total+=len(chunk)
    require(size<=size_expected and total<=15*1024**3,"diagnostic bytes")
    f.write(chunk);h.update(chunk)
  require(size==size_expected,"diagnostic truncation")
  diagnostics.append({"path":"/outputs/"+name,"bytes":size,"sha256":h.hexdigest()})
 import cm3_accounting as accounting
 canonical_roots=[]
 for name,row in rows.items():
  if not name.endswith("/accounting/ledger.json"):continue
  local=partial/pathlib.PurePosixPath(name).relative_to("/")
  def doc(ref):
   q=pathlib.Path(ref["path"]);require(q.is_relative_to(local.parent) and digest(q)==ref["sha256"],"canonical reference")
   return json.loads(q.read_bytes())
  accounting.ledger({"path":str(local),"sha256":row["sha256"]},doc)
  canonical_roots.append(name.removesuffix("ledger.json"))
 inputs={"/inputs/"+r["path"]:r for r in document(p["input_manifest"])["files"]}
 for name,doc in docs.items():
  if any(name.startswith(root) for root in canonical_roots):continue
  for ref in refs(doc):
   table=inputs if ref["path"].startswith("/inputs/") else rows
   require(ref["path"] in table and table[ref["path"]]["sha256"]==ref["sha256"],"reference closure")
 for s in selected:
  result=docs[s["result_ref"]["path"]]
  require(rows[s["result_ref"]["path"]]["sha256"]==s["result_ref"]["sha256"],"selected result hash")
  require(s["result_ref"]["path"]==s["output"]+"/result.json" and result["stage"]=="fit" and result["status"]=="PASS","supervisor PASS required")
  for field in ("arm","seed","purpose","attempt_id","context_sha256"):require(result[field]==s[field],"selected identity")
  require(result["approval"]==s["approval_ref"] and result["hardware"]["class"]=="cuda:L40S","fit approval/class")
  approval=docs[s["approval_ref"]["path"]];require(approval["fit_predecessors"]=={},"phase1 predecessor")
  details=docs[result["artifacts"]["details"]["path"]];checkpoint=details["checkpoint_file"]
  require(checkpoint["path"]==s["output"]+"/checkpoint.pt" and checkpoint["sha256"]==details["checkpoint_sha256"]==rows[checkpoint["path"]]["sha256"],"checkpoint substitution")
 partial.rename(dest/"artifacts")
 receipt={"format":"cm3-phase-collection-v1","status":"ARTIFACTS_VERIFIED","selected":selected,"files":list(rows.values()),"bytes":total,
  "phase_result_sha256":digest(phase/"phase-result.json"),"launch_binding_sha256":p["launch_binding"]["sha256"],
  "diagnostic_files":diagnostics,"matrix_verified":False,"judge_run":False}
 atomic(dest/"collection.json",receipt)
 job_status.write("cm3-phase1-02-collect",owner="modal-port",host="mac",stage="done",progress="All five artifacts/checkpoints verified; phase gate remains separate",eta=None,evidence=str(dest/"collection.json"))
 print(json.dumps({"status":receipt["status"],"bytes":total,"files":len(rows)}))
if __name__=="__main__":
 try:main()
 except BaseException as exc:
  import job_status
  job_status.write("cm3-phase1-02-collect",owner="modal-port",host="mac",stage="failed",progress=str(exc),eta=None,evidence=str(ROOT/"collection.log"))
  raise
