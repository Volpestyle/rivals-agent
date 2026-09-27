"""Exercise real parent orchestration with synthetic child processes; no Modal client."""
import contextlib,importlib.util,json,pathlib,tempfile,unittest,sys
from unittest.mock import patch
B=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(B.parent/"fanout"))
spec=importlib.util.spec_from_file_location("isolation_modal_app",B.parent/"fanout/modal_app.py");app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)
KEYS={"A-0","A-1","A-2","H-0","H-repeat-0"}
class Isolation(unittest.TestCase):
 def scenario(self,mode):
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);local=root/"phase";local.mkdir()
   for k in KEYS:(local/k).mkdir()
   calls=[];killed=[];ticks=[0];completed=[];guard_count=[]
   def result(k):
    failed=k=="H-0" and mode!="success"
    return {"status":"INCOMPLETE" if failed else "COMPLETE","measured_settlement_eligible":not (failed and mode=="cleanup"),"over_hold":failed and mode=="overhold","spend":{"seconds_through_cleanup":20},"worker":{},"teardown":{"status":"TERMINAL"}}
   class Proc:
    def __init__(self,key=None):self.key=key;self.pid=100+(sorted(KEYS).index(key) if key else 20);self.killed=False
    def poll(self):
     if self.key is None:return 1 if mode=="deadguard" and ticks[0]>0 else None
     if self.killed:return -9
     if self.key in ("H-0","H-repeat-0") or ticks[0]>=2:
      if self.key not in completed:completed.append(self.key)
      return 1 if self.key=="H-0" and mode!="success" else 0
     return None
    def wait(self):return self.poll()
   procs={}
   def popen(args,**kw):
    key=pathlib.Path(args[2]).name
    if args[1].endswith("guard.py"):
     guard_count.append(key);(local/key/"guard-ready.json").write_text("{}");return Proc()
    self.assertEqual(set(guard_count),KEYS);calls.append(key);p=Proc(key);procs[p.pid]=p
    (local/key/"wrapper-result.json").write_text(json.dumps(result(key)));return p
   def kill(pid,sig):killed.append(procs[pid].key);procs[pid].killed=True
   def tick(_):ticks[0]+=1
   def bound(*args,**kwargs):
    if mode=="spend" and ticks[0]>=1:raise ValueError("running spend stop")
    return 1
   p={"tasks":{k:{} for k in KEYS},"campaigns_directory":str(root)}
   with contextlib.ExitStack() as s:
    for name,value in [("DEPLOYMENT_ENABLED",True),("ROOT",root)]:s.enter_context(patch.object(app,name,value))
    for name,kwargs in [
     ("validate_launch",{"return_value":{"workspace_id":"workspace"}}),
     ("connect_verified",{"return_value":(object(),{"profile":"rivals"})}),
     ("reserve",{"return_value":(local,{})}),
     ("running_bound",{"side_effect":bound}),
     ("finish_task",{"side_effect":lambda path,*a,**kw:result(pathlib.Path(path).name)}),
     ("report",{})]:s.enter_context(patch.object(app,name,**kwargs))
    s.enter_context(patch.object(app.subprocess,"Popen",side_effect=popen))
    s.enter_context(patch.object(app.time,"sleep",side_effect=tick))
    s.enter_context(patch("os.killpg",side_effect=kill))
    if mode=="success":app._orchestrate(p)
    else:
     with self.assertRaises(ValueError):app._orchestrate(p)
   summary=json.loads((local/"phase-result.json").read_bytes())
   return calls,killed,completed,summary
 def test_terminal_failed_fit_allows_independent_siblings_to_finish(self):
  calls,killed,completed,summary=self.scenario("scientific")
  self.assertEqual(set(calls),KEYS);self.assertEqual(len(calls),5)
  self.assertEqual(killed,[]);self.assertEqual(set(completed),KEYS)
  self.assertEqual(summary["status"],"INCOMPLETE");self.assertFalse(summary["artifacts_collected"])
  self.assertIn("H-0",summary["failure"])
 def test_all_pass_remains_complete(self):
  _,killed,completed,summary=self.scenario("success")
  self.assertEqual(killed,[]);self.assertEqual(set(completed),KEYS);self.assertEqual(summary["status"],"COMPLETE")
 def test_unknown_cleanup_still_stops_siblings(self):
  _,killed,_,summary=self.scenario("cleanup")
  self.assertTrue(set(killed)&{"A-0","A-1","A-2"});self.assertEqual(summary["status"],"INCOMPLETE");self.assertIn("cleanup unverified",summary["failure"])
 def test_over_hold_still_stops_siblings(self):
  _,killed,_,s=self.scenario("overhold");self.assertTrue(set(killed)&{"A-0","A-1","A-2"});self.assertIn("funded hold",s["failure"])
 def test_dead_guard_still_stops_siblings(self):
  _,killed,_,s=self.scenario("deadguard");self.assertTrue(set(killed)&{"A-0","A-1","A-2"});self.assertIn("watchdog died",s["failure"])
 def test_running_spend_stop_still_stops_siblings(self):
  _,killed,_,s=self.scenario("spend");self.assertTrue(set(killed)&{"A-0","A-1","A-2"});self.assertIn("running spend stop",s["failure"])
if __name__=="__main__":unittest.main(verbosity=2)
