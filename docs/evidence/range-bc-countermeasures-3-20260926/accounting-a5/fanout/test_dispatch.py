"""Synthetic task process/app supervision; never contacts Modal."""
import contextlib,json,pathlib,tempfile,types,unittest,sys
from unittest.mock import patch
import lifecycle,modal_app,task_driver,safety,cm3_accounting
from test_fixes import Fixture,FakeBackend

class TaskDispatch(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=pathlib.Path(self.tmp.name)
  self.f=Fixture(self.root);self.p=self.f.p
  self.local,self.bounds=lifecycle.reserve(self.p,self.root/"state",cm3_accounting.IDENTITY)
  self.task=self.local/"H-0"
  lifecycle.atomic(self.task/"guard-pid.json",{"pid":999})
  path=self.local/"runtime.json";lifecycle.atomic(path,{"plan":self.p,"phase_directory":str(self.local.resolve())})
  self.ref={"path":str(path),"sha256":safety.digest(path)}
 def run_task(self,timeout=False):
  calls=[];stops=[];gets=[]
  task=self.task
  class App:
   app_id="ap-own"
   @contextlib.contextmanager
   def run(self,**kw):yield self
  class Call:
   object_id="fc-own"
   def get(self,timeout):
    gets.append(timeout)
    if len(gets)==1 and timeout_mode:raise TimeoutError()
    return {"exit":0,"status":"COMPLETE","result":{"path":"/outputs/H/result.json","sha256":"a"*64}}
  class Function:
   def spawn(self,*args):calls.append(args);return Call()
  timeout_mode=timeout
  real_cleanup=lifecycle.cleanup
  def cleanup(path,backend=None):
   inv=json.loads((pathlib.Path(path)/"inventory.json").read_bytes())
   b=FakeBackend(inv)
   oldstop=b.stop
   def stop(a,t):stops.append(a);oldstop(a,t)
   b.stop=stop
   return real_cleanup(path,b,pause=lambda _:None)
  def reason(inv):
   return "funded deadline" if timeout_mode and gets else None
  fake=types.SimpleNamespace(enable_output=lambda:contextlib.nullcontext())
  with patch.object(modal_app,"DEPLOYMENT_ENABLED",True),patch.object(modal_app,"build_app",return_value=(App(),Function())),patch.dict(sys.modules,modal=fake),patch.object(lifecycle,"connect_verified",return_value=(object(),cm3_accounting.IDENTITY)),patch.object(lifecycle,"driver_alive",return_value=True),patch.object(lifecycle,"guard_reason",side_effect=reason),patch.object(lifecycle,"cleanup",side_effect=cleanup),patch.object(task_driver.time,"sleep",lambda _:None):
   if timeout:
    with self.assertRaisesRegex(ValueError,"incomplete"):task_driver.execute(self.task,self.ref)
   else:task_driver.execute(self.task,self.ref)
  return calls,stops,json.loads((self.task/"wrapper-result.json").read_bytes())
 def test_success_one_spawn_and_terminal_cleanup_before_record(self):
  calls,stops,r=self.run_task()
  self.assertEqual(len(calls),1);self.assertEqual(calls[0][:3],("H",0,"registered"))
  self.assertEqual(stops,["ap-own"]);self.assertEqual(r["teardown"]["status"],"TERMINAL")
  self.assertEqual(r["status"],"COMPLETE");self.assertTrue(r["measured_settlement_eligible"])
 def test_timeout_kills_owned_app_books_failed_compute_no_retry(self):
  calls,stops,r=self.run_task(timeout=True)
  self.assertEqual(len(calls),1);self.assertEqual(stops,["ap-own"])
  self.assertEqual(r["status"],"INCOMPLETE");self.assertIsNone(r["owner_result"])
  self.assertGreater(r["spend"]["seconds_through_cleanup"],0);self.assertGreater(r["spend"]["estimated_conservative_usd"],0)
  self.assertEqual(r["teardown"]["status"],"TERMINAL")
 def test_dead_guard_refuses_app_creation_and_keeps_hold(self):
  with patch.object(modal_app,"DEPLOYMENT_ENABLED",True),patch.object(modal_app,"build_app") as build,patch.object(lifecycle,"connect_verified",return_value=(object(),cm3_accounting.IDENTITY)),patch.object(lifecycle,"driver_alive",return_value=False),patch.object(lifecycle,"cleanup",return_value={"status":"TERMINAL","identity":cm3_accounting.IDENTITY,"apps":[],"events":[{"terminal_apps":[],"containers":0}],"checked_at_unix":1}):
   with self.assertRaises(ValueError):task_driver.execute(self.task,self.ref)
  build.assert_not_called()
  r=json.loads((self.task/"wrapper-result.json").read_bytes())
  self.assertFalse(r["measured_settlement_eligible"]);self.assertFalse(r["creation_started"])

class ParentDispatch(unittest.TestCase):
 def test_all_guards_and_reservations_precede_any_task_process(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);f=Fixture(root);p=f.p;starts=[];guards=[];locals_=[]
   class Proc:
    pid=200
    def __init__(self,code=None):self.code=code
    def poll(self):return self.code
    def wait(self):return self.code
   real_cleanup=lifecycle.cleanup
   def cleanup(path,backend=None):
    inv=json.loads((pathlib.Path(path)/"inventory.json").read_bytes());b=FakeBackend(inv);b.stopped=True
    return real_cleanup(path,b,pause=lambda _:None)
   def popen(args,**kw):
    path=pathlib.Path(args[2]);locals_.append(path.parent)
    if args[1].endswith("guard.py"):
     guards.append(path.name);lifecycle.atomic(path/"guard-ready.json",{"ready":True});return Proc()
    starts.append(path.name)
    self.assertEqual(set(guards),safety.PHASE1)
    phase=json.loads((path.parent/"phase.json").read_bytes())
    self.assertEqual(len(phase["reservations"]),5)
    self.assertTrue(all(pathlib.Path(r["path"]).exists() for r in phase["reservations"].values()))
    lifecycle.update_inventory(path,lambda x:x.update(creation_started=True,creation_finished=True))
    lifecycle.finish_task(path,{"exit":0,"status":"COMPLETE","result":{"path":"/outputs/"+path.name+"/result.json","sha256":"a"*64}})
    return Proc(0)
   with patch.object(modal_app,"ROOT",root),patch.object(modal_app,"DEPLOYMENT_ENABLED",True),patch.object(modal_app,"validate_launch",return_value={"workspace_id":cm3_accounting.IDENTITY["workspace_id"]}),patch.object(modal_app,"connect_verified",return_value=(object(),cm3_accounting.IDENTITY)),patch.object(modal_app.subprocess,"Popen",side_effect=popen),patch.object(lifecycle,"cleanup",side_effect=cleanup),patch.object(modal_app,"report"):
    result=modal_app._orchestrate(p)
   self.assertEqual(set(starts),safety.PHASE1);self.assertEqual(len(starts),5)
   summary=json.loads((result/"phase-result.json").read_bytes())
   self.assertFalse(summary["separately_charged"]);self.assertEqual(summary["status"],"COMPLETE")
   self.assertEqual(len(summary["task_results"]),5)

if __name__=="__main__":unittest.main(verbosity=2)
