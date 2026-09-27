"""Changed execution/accounting boundary, synthetic only; no Modal RPC."""
import copy,json,pathlib,tempfile,time,types,unittest
from unittest.mock import patch
import cm3_timeouts as timeouts
import safety,lifecycle,modal_app,task_driver,cm3_accounting
from test_fixes import Fixture,FakeBackend

class PerArm(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.root=pathlib.Path(self.temp.name);self.f=Fixture(self.root);self.p=self.f.p
 def test_exact_full_workload_and_matrix(self):
  self.assertEqual(self.p["attempt_timeout_seconds_by_arm"],{"A":5853,"H":600,"I":4543,"W":600})
  allholds=timeouts.holds(safety.ALL,self.p["attempt_timeout_seconds_by_arm"],self.p["resource_rate_usd_second"])
  self.assertEqual(sum(x["total_seconds"] for x in allholds.values()),40848)
  self.assertEqual(sum(x["total_seconds"] for x in self.p["task_holds"].values()),20859)
  self.assertEqual(allholds["H-repeat-0"],allholds["H-0"])
  f=Fixture(self.root,"phase2")
  self.assertEqual(safety.projection(f.p)["remaining_compute_seconds"],20289)
 def test_per_arm_and_per_task_substitution_refused(self):
  for arm in timeouts.ARMS:
   for bad in (0,-1,float("nan"),float("inf"),True,601):
    p=copy.deepcopy(self.p);p["attempt_timeout_seconds_by_arm"][arm]=bad
    with self.assertRaises(ValueError):safety.numeric_plan(p)
  for key in self.p["task_holds"]["A-0"]:
   p=copy.deepcopy(self.p);p["task_holds"]["A-0"][key]=0
   with self.assertRaises(ValueError):safety.numeric_plan(p)
 def test_smoke_numbers_and_pin_validation(self):
  smoke=safety.document(self.p["smoke_timing"])
  for bad in (0,-1,float("nan"),float("inf"),True):
   x=copy.deepcopy(smoke);x["A"]["smoke"]["seconds_per_update"]=bad
   with self.assertRaises(ValueError):timeouts.measured_seconds(x)
  p=copy.deepcopy(self.p);p["smoke_timing"]["sha256"]="0"*64
  with self.assertRaisesRegex(ValueError,"pin"):safety.numeric_plan(p)
  p=copy.deepcopy(self.p);p["expected_fit_seconds_by_arm"]["W"]+=1
  with self.assertRaisesRegex(ValueError,"substitution"):safety.numeric_plan(p)
 def test_each_task_has_funded_stop_and_finished_h_does_not_hold_a(self):
  b=safety.clock_bound(self.p,wall=1000,mono=100)
  self.assertEqual(b["tasks"]["H-0"]["stop_at_unix"],1900)
  self.assertEqual(b["tasks"]["A-0"]["stop_at_unix"],7153)
  with self.assertRaisesRegex(ValueError,"H"):safety.running_bound(b,wall=1901,mono=1001)
  completed={"H-0":400,"H-repeat-0":410}
  cost=safety.running_bound(b,wall=1901,mono=1001,completed=completed)
  self.assertAlmostEqual(cost,self.p["spent_before_usd"]+self.p["overhead_reserve_usd"]+(3*901+810)*self.p["resource_rate_usd_second"])
  b["cap_usd"]=cost
  with self.assertRaisesRegex(ValueError,"spend stop"):safety.running_bound(b,wall=1901,mono=1001,completed=completed)
  with self.assertRaises(ValueError):safety.running_bound(b,wall=1901,mono=1001,completed={"H-0":1021})
 def test_phase_holds_must_fit_compute_cap(self):
  self.f.ledger["charges"][1]["compute_seconds"]=33000;self.f.refresh_ledger()
  with self.assertRaisesRegex(ValueError,"16 hours"):safety.ledger(self.p,self.root/"state/campaign/reservations")
 def make_reservation(self):
  identity=dict(cm3_accounting.IDENTITY)
  local,bounds=lifecycle.reserve(self.p,self.root/"state",identity)
  return local,bounds
 def test_serial_reservations_overhead_once_and_all_before_app_creation(self):
  local,bounds=self.make_reservation();phase=json.loads((local/"phase.json").read_bytes())
  self.assertFalse(phase["separately_charged"])
  rows=[json.loads(pathlib.Path(ref["path"]).read_bytes()) for ref in phase["reservations"].values()]
  self.assertEqual(len(rows),5);self.assertEqual(sum(r["bounds"]["overhead_usd"] for r in rows),self.p["overhead_reserve_usd"])
  self.assertEqual(sum(r["reserved_compute_seconds"] for r in rows),20859)
  self.assertTrue(all(r["concurrent_slots"]==1 for r in rows))
  self.assertEqual([r["task"] for r in rows if r["bounds"]["overhead_usd"]],["A-0"])
  names=[]
  for k in self.p["tasks"]:
   inv=json.loads((local/k/"inventory.json").read_bytes())
   self.assertFalse(inv["creation_started"]);self.assertEqual(inv["apps"],[]);names.append(inv["app_name"])
  self.assertEqual(len(set(names)),5)
 def finish(self,task,seconds,terminal=True,created=True):
  inv=json.loads((task/"inventory.json").read_bytes())
  inv.update(creation_started=created,creation_finished=created);lifecycle.atomic(task/"inventory.json",inv)
  backend=FakeBackend(inv,failures=0 if terminal else 100)
  if not created:backend.apps=lambda _:[];backend.containers=lambda _:[]
  with patch.object(lifecycle.time,"sleep",lambda _:None):
   # cleanup's default pause is captured; backend terminal already, avoids real waits.
   backend.stopped=True if terminal else False
   result=lifecycle.finish_task(task,reason="synthetic failure",backend=backend,
         wall=lambda:inv["bounds"]["started_at_unix"]+seconds,
         mono=lambda:inv["bounds"]["started_monotonic"]+seconds)
  return result
 def settle(self,task,result):
  inv=json.loads((task/"inventory.json").read_bytes())
  res=pathlib.Path(inv["reservation"]["path"]);out=task/"wrapper-result.json"
  row={"attempt_id":inv["attempt_id"],"reservation":{"path":str(res),"sha256":safety.digest(res)},
       "result":{"path":str(out),"sha256":safety.digest(out)}}
  def document(ref):
   self.assertEqual(safety.digest(ref["path"]),ref["sha256"]);return json.loads(pathlib.Path(ref["path"]).read_bytes())
  return cm3_accounting.settle(row,document)
 def test_failed_compute_settles_actual_task_clock_and_result_immutable(self):
  local,b=self.make_reservation();charges=[]
  for key,seconds in (("A-0",3900.25),("H-0",220.5)):
   task=local/key;r=self.finish(task,seconds);self.assertEqual(r["status"],"INCOMPLETE")
   charge=self.settle(task,r);charges.append(charge)
   with patch.object(lifecycle,"cleanup",side_effect=AssertionError("must not rewrite result")):
    self.assertEqual(lifecycle.finish_task(task),r)
  self.assertEqual(sum(c["seconds"] for c in charges),3901+221)
  self.assertLess(sum(c["seconds"] for c in charges),3901*2)
 def test_never_created_cannot_release_hold(self):
  local,b=self.make_reservation();task=local/"H-0";r=self.finish(task,10,created=False)
  self.assertFalse(r["measured_settlement_eligible"]);self.assertFalse(r["hold_released"])
  with self.assertRaisesRegex(ValueError,"app inventory"):self.settle(task,r)
 def test_unknown_teardown_cannot_release_hold(self):
  local,b=self.make_reservation();task=local/"H-0"
  inv=json.loads((task/"inventory.json").read_bytes());inv.update(creation_started=True);lifecycle.atomic(task/"inventory.json",inv)
  backend=FakeBackend(inv);backend.apps=lambda _:[];backend.containers=lambda _:[]
  with patch.object(lifecycle,"cleanup",return_value={"status":"INCOMPLETE_CLEANUP","identity":inv["identity"],"apps":[],"events":[],"checked_at_unix":1}):
   r=lifecycle.finish_task(task,backend=backend)
  self.assertFalse(r["measured_settlement_eligible"])
  with self.assertRaisesRegex(ValueError,"terminal cleanup"):self.settle(task,r)
 def test_supervisor_death_and_short_arm_guard_stop(self):
  local,b=self.make_reservation()
  inv=json.loads((local/"H-0/inventory.json").read_bytes());inv["driver_pid"]=101;inv["supervisor_pid"]=102
  self.assertEqual(lifecycle.guard_reason(inv,alive=lambda pid:pid!=102,wall=lambda:b["started_at_unix"],mono=lambda:b["started_monotonic"]),"driver death")
  self.assertEqual(lifecycle.guard_reason(inv,alive=lambda pid:True,wall=lambda:inv["bounds"]["stop_at_unix"],mono=lambda:b["started_monotonic"]),"funded deadline")
 def test_task_driver_disabled_directly(self):
  with self.assertRaisesRegex(ValueError,"paid launch disabled"):task_driver.execute(self.root,{})
 def test_native_function_timeout_l40s_and_zero_retries_per_arm(self):
  definitions=[]
  class Image:
   @staticmethod
   def from_registry(value):return Image()
   def add_local_python_source(self,*names):return self
  class Volume:
   @staticmethod
   def from_id(value,client):return Volume()
   def read_only(self):return self
  class App:
   def __init__(self,name):self.name=name
   def function(self,**kwargs):
    definitions.append(kwargs);return lambda fn:fn
  fake=types.SimpleNamespace(App=App,Image=Image,Volume=Volume)
  identity=cm3_accounting.IDENTITY
  with patch.dict("sys.modules",modal=fake),patch.object(modal_app,"verify_client",return_value=identity):
   for phase in ("phase1","phase2"):
    p=Fixture(self.root,phase).p
    for key in p["tasks"]:
     runtime=dict(p,verified_identity=identity,owned_app_name=key,selected_task=key)
     modal_app.build_app(runtime,identity,object(),key)
     d=definitions[-1];self.assertEqual(d["timeout"],p["attempt_timeout_seconds_by_arm"][key[0]])
     self.assertEqual(d["gpu"],"L40S");self.assertEqual(d["retries"],0)
     self.assertEqual(d["startup_timeout"],300);self.assertTrue(d["single_use_containers"])
     self.assertEqual(d["cpu"],(8,8));self.assertEqual(d["memory"],(32768,32768))
  self.assertEqual(len(definitions),13)

if __name__=="__main__":unittest.main(verbosity=2)
