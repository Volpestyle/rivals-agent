"""F1 end-to-end metadata transport: live host inventory -> fit pin -> owner reads.
All files are tiny synthetic JSON. No SDK, tensor, sealed data or actual app reads.
"""
import copy,json,pathlib,shutil,tempfile,unittest
import safety,cm3_accounting as accounting
from test_fixes import Fixture
import test_fit_budget

class PortableFixture:
 def __init__(self,root,phase="phase1"):
  self.root=pathlib.Path(root);(self.root/"fixture").mkdir()
  self.f=Fixture(self.root/"fixture",phase);self.p=self.f.p
  self.p["campaign_id"]="r3-20260926-l40s"
  self.bootstrap=self.root/"actual"/"bootstrap";self.bootstrap.mkdir(parents=True)
  self.campaigns=self.root/"actual"/"campaigns";self.campaigns.mkdir()
  self.reservations_dir=self.campaigns/self.p["campaign_id"]/"reservations"
  self.host=self.root/"host-evidence";self.host.mkdir()
  self.container=self.root/"container"/"inputs"/"accounting"
  self.p["bootstrap_campaign_directory"]=str(self.bootstrap)
  self.actual=[];rows=[];inventory={};completed={};self.owner_paths=[]
  keys=["bootstrap-history","campaign-history"] if phase=="phase1" else sorted(safety.PHASE1)
  gate=safety.document({"local_path":self.p["phase1_gate"]["local_path"],"sha256":self.p["phase1_gate"]["sha256"]}) if phase=="phase2" else None
  gate_names={"A-0":"A0","A-1":"A1","A-2":"A2","H-0":"H0","H-repeat-0":"H0_repeat"}
  for i,key in enumerate(keys):
   attempt=key+"-prior"
   owner=self.put("outputs/history/"+attempt+"/result.json",{"elapsed_stage_seconds":10,"attempt_id":attempt,"status":"PASS"})
   self.owner_paths.append(owner["path"])
   raw_owner={"path":"/"+owner["path"],"sha256":owner["sha256"]}
   seconds=100.25+i;rate=self.p["resource_rate_usd_second"];overhead=.1
   reservation={"attempt_id":attempt,"reserved_compute_seconds":500,"reserved_usd":1,
                "bounds":{"rate_usd_second":rate,"overhead_usd":overhead}}
   if i==0:
    actual=self.bootstrap/attempt/"reservation.json"
    logical="reservations/"+attempt+".json"
   else:
    actual=self.reservations_dir/(attempt+".json")
    logical="reservations/"+attempt+".json"
   actual.parent.mkdir(parents=True,exist_ok=True);actual.write_bytes(self.encode(reservation));self.actual.append(actual)
   reserved=self.put(logical,reservation);self.assert_same(actual,self.host/logical)
   result={"format":"cm3-inputs-wrapper-result-v1","attempt_id":attempt,"status":"COMPLETE","owner_result":raw_owner,
    "teardown":{"status":"TERMINAL","identity":accounting.IDENTITY,"apps":["ap-"+attempt],
                "events":[{"containers":0,"terminal_apps":["ap-"+attempt]}],"checked_at_unix":2000},
    "spend":{"seconds_through_cleanup":seconds,"estimated_conservative_usd":overhead+seconds*rate}}
   result_ref=self.put("results/"+attempt+".json",result)
   rows.append({"attempt_id":attempt,"reservation":reserved,"result":result_ref});inventory[attempt]=reserved
   if gate is not None:
    completed[key]=owner;gate["outputs"][gate_names[key]]=raw_owner
  inv=self.put("inventory.json",{"format":"cm3-reservation-inventory-v2","campaign_id":self.p["campaign_id"],"reservations":inventory})
  self.data={"format":"cm3-measured-accounting-v2","approved_by":"herdr-lead","campaign_id":self.p["campaign_id"],
             "basis_seconds":12159,"basis_usd":6.18374656,"inventory":inv,"settlements":rows,"completed_phase1":completed}
  self.put("ledger.json",self.data);self.host_ref={"path":str(self.host/"ledger.json"),"sha256":safety.digest(self.host/"ledger.json")}
  self.p["campaign_ledger"]={"local_path":self.host_ref["path"],"sha256":self.host_ref["sha256"]}
  totals=accounting.ledger(self.host_ref,self.document)
  self.p["spent_before_compute_seconds"]=totals["spent_seconds"];self.p["spent_before_usd"]=totals["spent_usd"]
  self.totals=totals
  if gate is not None:
   ref=self.f.ref(gate);self.p["phase1_gate"]={**ref,"remote_ref":{"path":"/inputs/phase1-gate.json","sha256":ref["sha256"]}}
  self.f.refresh_binding()
  b=safety.document(self.p["launch_binding"]);b["bootstrap_campaign_directory"]=str(self.bootstrap);self.p["launch_binding"]=self.f.ref(b)
  shutil.copytree(self.host,self.container)
  self.container_ref={"path":str(self.container/"ledger.json"),"sha256":safety.digest(self.container/"ledger.json")}
 def encode(self,x):return (json.dumps(x,sort_keys=True,indent=2,allow_nan=False)+"\n").encode()
 def put(self,name,value):
  path=self.host/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(self.encode(value))
  return {"path":name,"sha256":safety.digest(path)}
 def assert_same(self,a,b):assert a.read_bytes()==b.read_bytes()
 def document(self,ref):return safety.document({"local_path":ref["path"],"sha256":ref["sha256"]})
 def owner_document(self,ref):
  path=pathlib.Path(ref["path"]);assert path.is_relative_to(self.container),"owner attempted host evidence"
  return self.document(ref)
 def budget(self):
  key=min(self.p["tasks"]);b=test_fit_budget.FitBudget().budget(self.p,key);b["accounting"]=self.container_ref
  return key,b

class CanonicalTransport(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.x=PortableFixture(self.tmp.name)
 def admit(self,x=None):
  x=x or self.x;safety.validate_binding(x.p);return safety.ledger(x.p,x.reservations_dir)
 def test_identical_ledger_host_admission_fit_pin_owner_allocation(self):
  x=self.x
  self.assertNotEqual(x.host_ref["path"],x.container_ref["path"])
  self.assertEqual(x.host_ref["sha256"],x.container_ref["sha256"])
  self.assertNotIn(str(x.root), (x.host/"ledger.json").read_text())
  self.admit()
  key,b=x.budget();safety.fit_budget(x.p,key,b)
  totals=accounting.allocation(b,x.owner_document)
  self.assertEqual(totals,x.totals)
 def test_changed_transported_owner_refused_even_when_costs_same(self):
  x=self.x;self.admit();key,b=x.budget();safety.fit_budget(x.p,key,b)
  path=x.container/x.owner_paths[0];d=json.loads(path.read_bytes());d["same-cost-extra-field"]=True
  path.write_bytes(x.encode(d))
  with self.assertRaisesRegex(ValueError,"pin"):accounting.allocation(b,x.owner_document)
  self.admit() # host originals and canonical source remain valid
 def test_different_ledger_sha_still_refused_no_totals_fallback(self):
  x=self.x;key,b=x.budget()
  d=copy.deepcopy(x.data);d["annotation"]="same settlements, changed ledger bytes"
  path=x.container/"ledger.json";path.write_bytes(x.encode(d))
  b["accounting"]={"path":str(path),"sha256":safety.digest(path)}
  self.assertEqual(accounting.allocation(b,x.owner_document),x.totals)
  with self.assertRaisesRegex(ValueError,"accounting pin differs"):safety.fit_budget(x.p,key,b)
 def test_actual_inventory_extra_missing_changed_duplicate_and_symlink(self):
  # Mutations apply only to freshly generated synthetic trees.
  for case in ("extra","missing","changed","duplicate","symlink"):
   with self.subTest(case=case),tempfile.TemporaryDirectory() as root:
    x=PortableFixture(root);self.admit(x);path=x.actual[0]
    if case=="extra":
     extra=x.campaigns/"other-campaign"/"reservations"/"extra.json";extra.parent.mkdir(parents=True)
     extra.write_bytes(x.encode({"attempt_id":"extra"}))
    elif case=="missing":path.unlink()
    elif case=="changed":
     d=json.loads(path.read_bytes());d["changed"]=True;path.write_bytes(x.encode(d))
    elif case=="duplicate":
     extra=x.bootstrap/"duplicate"/"reservation.json";extra.parent.mkdir();extra.write_bytes(path.read_bytes())
    else:
     saved=x.root/"saved-original.json";saved.write_bytes(path.read_bytes());path.unlink();path.symlink_to(saved)
    with self.assertRaises(ValueError):self.admit(x)
 def test_host_root_cannot_be_relocated_without_binding_change(self):
  x=self.x;p=copy.deepcopy(x.p);p["campaign_ledger"]["local_path"]=x.container_ref["path"]
  with self.assertRaisesRegex(ValueError,"resolution root"):safety.validate_binding(p)
 def test_relative_paths_traversal_absolute_backslash_colon_and_aliases_refused(self):
  for path in ("../escape.json","/outside/file.json","a/../b.json","a\\b.json","C:/file.json","a//b.json","./b.json"):
   with self.subTest(path=path),self.assertRaises(ValueError):
    accounting.relative_ref({"path":path,"sha256":"a"*64})
 def test_symlink_out_of_bundle_refused(self):
  x=self.x;target=x.container/x.owner_paths[0];outside=x.root/"outside.json";outside.write_bytes(target.read_bytes())
  target.unlink();target.symlink_to(outside)
  key,b=x.budget()
  with self.assertRaisesRegex(ValueError,"escaped"):accounting.allocation(b,x.owner_document)
 def test_v1_host_admission_and_owner_new_allocation_refused(self):
  x=self.x;d=copy.deepcopy(x.data);d["format"]="cm3-measured-accounting-v1"
  path=x.host/"legacy-ledger.json";path.write_bytes(x.encode(d));x.p["campaign_ledger"]={"local_path":str(path),"sha256":safety.digest(path)}
  with self.assertRaises(ValueError):safety.ledger(x.p,x.reservations_dir)
  key,b=x.budget();b["accounting"]={"path":str(path),"sha256":safety.digest(path)}
  with self.assertRaisesRegex(ValueError,"canonical v2"):accounting.allocation(b,x.document)
 def test_phase2_gate_alias_preserves_exact_selected_refs(self):
  with tempfile.TemporaryDirectory() as root:
   x=PortableFixture(root,"phase2");self.admit(x);key,b=x.budget();safety.fit_budget(x.p,key,b)
   gate=safety.document({"local_path":x.p["phase1_gate"]["local_path"],"sha256":x.p["phase1_gate"]["sha256"]})
   totals=accounting.allocation(b,x.owner_document,required_results=gate["outputs"].values())
   self.assertEqual(totals,x.totals)
   gate["outputs"]["H0"]["sha256"]="0"*64
   ref=x.f.ref(gate);x.p["phase1_gate"].update(ref)
   with self.assertRaisesRegex(ValueError,"selected attempt"):safety.ledger(x.p,x.reservations_dir)
 def test_input_and_host_absolute_owner_aliases_refused(self):
  for path in ("/inputs/owner.json",str(self.x.host/"owner.json"),"owner.json","/outputs/../outside.json"):
   with self.assertRaises(ValueError):accounting.output_ref({"path":path,"sha256":"a"*64})

if __name__=="__main__":unittest.main(verbosity=2)
