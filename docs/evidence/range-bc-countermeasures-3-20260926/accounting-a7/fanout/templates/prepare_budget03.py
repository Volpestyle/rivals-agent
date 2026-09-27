"""Settle collected smoke03 and derive reviewed Writer forecast; no cloud launch."""
from pathlib import Path
import json,hashlib,shutil,sys,math
H=Path(__file__).resolve().parent;P=H/"smoke03-proposal";B=H/"budget03-proposal"
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
def write(p,x):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open("x") as f:json.dump(x,f,sort_keys=True,indent=2,allow_nan=False);f.write("\n")
collection=read(P/"collection/collection.json")
assert collection["status"]=="PASS" and collection["teardown"]["status"]=="TERMINAL"
actual=H/"f5-real/bootstrap-campaign/smoke-03";wrapper=read(actual/"result.json")
assert sha(actual/"result.json")==collection["wrapper_result_sha256"] and wrapper["status"]=="PASS"
B.mkdir()
for name in ("cm3_accounting.py","cm3_timeouts.py","cm3_budget_plan.py","make_receipt.py","canonical_safety.py","common-context.json","input-closure.frozen.json"):
 shutil.copyfile(P/name,B/name)
shutil.copytree(P/"accounting",B/"accounting")
for src,dest in ((actual/"reservation.json",B/"accounting/reservations/smoke-03.json"),(actual/"result.json",B/"accounting/results/smoke-03.json")):shutil.copyfile(src,dest)
owner_ref=wrapper["owner_result"];owner=P/"collection/artifacts"/Path(owner_ref["path"]).relative_to("/")
assert sha(owner)==owner_ref["sha256"]
target=B/"accounting"/owner_ref["path"].lstrip("/");target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(owner,target)
ref=lambda p:{"path":str(p.relative_to(B/"accounting")),"sha256":sha(p)}
inv=read(B/"accounting/inventory.json");inv["reservations"]["smoke-03"]=ref(B/"accounting/reservations/smoke-03.json")
(B/"accounting/inventory.json").write_text(json.dumps(inv,sort_keys=True,indent=2)+"\n")
ledger=read(B/"accounting/ledger.json");ledger["inventory"]=ref(B/"accounting/inventory.json")
ledger["settlements"].append({"attempt_id":"smoke-03","reservation":inv["reservations"]["smoke-03"],"result":ref(B/"accounting/results/smoke-03.json")})
ledger["settlements"].sort(key=lambda x:x["attempt_id"]);(B/"accounting/ledger.json").write_text(json.dumps(ledger,sort_keys=True,indent=2)+"\n")
sys.path.insert(0,str(B));import cm3_accounting as a,cm3_budget_plan as plan
from canonical_safety import measured_inventory
from make_receipt import Writer
def document(ref):
 path=Path(ref["path"]);assert sha(path)==ref["sha256"];return read(path)
host_ref={"path":str(B/"accounting/ledger.json"),"sha256":sha(B/"accounting/ledger.json")}
live=measured_inventory({"bootstrap_campaign_directory":str(H/"f5-real/bootstrap-campaign")},H/"campaigns/r3-20260926-l40s/reservations")
context=read(B/"common-context.json");state=read(P/"state.json");state["stage_results"]["smoke"]=owner_ref
totals=a.ledger(host_ref,document,inventory=live,required_results=[state["stage_results"][s] for s in ("inputs","proof128","smoke")]);write(B/"settlement.json",totals)
remote_accounting="/outputs/.modal-control/budget-03/accounting"
state["allocation"].update(spent_seconds=totals["spent_seconds"],spent_usd=totals["spent_usd"],accounting={"path":remote_accounting+"/ledger.json","sha256":host_ref["sha256"]})
sessions=[];manifest=read(B/"input-closure.frozen.json")
for sid,row in context["sources"].items():
 p=Path("/Users/james/dev/range-bc-data/caches15")/sid/"cache.json"
 assert sha(p)==row["cache_manifest_sha256"]
 cache=read(p);frames=max(cache["row_frame"])+1
 for view in ("global","crop"):
  expected=frames*math.prod(cache[view+"_shape"])
  frozen=next(r for r in manifest["files"] if r["path"]=="caches15/"+sid+"/"+view+".u8")
  assert frozen["bytes"]==expected
 sessions.append(dict(session=sid,role=row["role"],frames=frames,cache_manifest_sha256=sha(p)))
total=sum(r["frames"] for r in sessions);assert total==173698
state["projection"]=dict(safety_factor=1.25,total_cache_frames=total,
 per_fit_diagnostics_serialization_seconds=plan.DIAGNOSTICS_SECONDS,
 source_and_full_cache_hashing_seconds=14*plan.SOURCE_HASH_SECONDS,
 verification_seconds=300,startup_shutdown_seconds=4050,non_compute_usd=plan.FUTURE_NONCOMPUTE_USD)
write(B/"state.json",state);shutil.copyfile(P/"approvals.at-launch.json",B/"approvals.for-derivation.json")
writer=Writer(context,state,read(B/"approvals.for-derivation.json"),[(remote_accounting,B/"accounting"),("/outputs",P/"collection/artifacts/outputs")])
forecast=writer.forecast();write(B/"budget-03.receipt.json",forecast)
details=writer.doc(writer.doc(owner_ref)["artifacts"]["details"]);write(B/"smoke-details.json",details)
extraction=forecast["extraction_and_rehash_seconds"];measured=forecast["measured_fit_seconds"]
unpadded=sum(measured.values())+extraction+14*plan.SOURCE_HASH_SECONDS+300+4050
assert abs(forecast["forecast_total_seconds"]-(totals["spent_seconds"]+1.25*unpadded))<1e-7
extract_hold_usd=float(a.usd_up(a.Decimal(2220)*a.Decimal(str(plan.RATE))+a.Decimal(str(plan.EXTRACTION_OVERHEAD_USD))))
verify_usd=float(a.usd_up(a.Decimal(300)*a.Decimal(str(plan.RATE))+a.Decimal(str(plan.VERIFY_OVERHEAD_USD))))
decision=dict(format="cm3-budget-decision-v2",status=forecast["status"],stop_reasons=forecast["stop_reasons"],
 budget_receipt={"path":"/outputs/.modal-control/budget-03/budget-03.receipt.json","sha256":sha(B/"budget-03.receipt.json")},
 smoke_result=owner_ref,smoke_collection_sha256=sha(P/"collection/collection.json"),
 mandatory_executions=dict(A=3,H=4,I=3,W=3),settled=totals,sessions=sessions,
 projection=state["projection"],measured_fit_seconds=measured,extraction_seconds=extraction,
 future_unpadded_seconds=unpadded,future_padded_seconds=1.25*unpadded,
 forecast_total_seconds=forecast["forecast_total_seconds"],projected_modal_usd=forecast["projected_modal_usd"],
 extract_admission=dict(spent_seconds=totals["spent_seconds"],hold_seconds=2220,verification_seconds=300,total_seconds=totals["spent_seconds"]+2520,
 spent_usd=totals["spent_usd"],hold_usd=extract_hold_usd,verification_usd=verify_usd,total_usd=totals["spent_usd"]+extract_hold_usd+verify_usd),
 cap_seconds=69120,cap_usd=60,launch_authorized=False,workspace_limit="unconfirmed")
write(B/"decision.json",decision)
print(json.dumps(decision,indent=2))
