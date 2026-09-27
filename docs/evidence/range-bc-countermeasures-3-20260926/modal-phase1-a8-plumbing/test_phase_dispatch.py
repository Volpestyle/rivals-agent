import unittest,tempfile,pathlib,json,hashlib,types,sys,time,contextlib
from unittest.mock import patch
import phase_transport as t,lifecycle
class Dispatch(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=pathlib.Path(self.tmp.name)
  self.local=self.root/"phase/A-0";self.local.mkdir(parents=True);(self.local/"inventory.json").write_text("{}")
  for n in ("manifest.json","witness.json"):(self.root/n).write_text("{}")
  self.payload=b'{"stage":"fit"}';(self.root/"receipt.json").write_bytes(self.payload)
  m={"files":{"/outputs/.modal-control/phase1-02/receipts/A-0.json":{"local_path":"receipt.json"}}};(self.root/"control.json").write_text(json.dumps(m))
  def ref(n):
   q=self.root/n;return {"local_path":str(q),"sha256":hashlib.sha256(q.read_bytes()).hexdigest()}
  self.p={"verified_identity":t.IDENTITY,"selected_task":"A-0","owned_app_name":"test","image_id":"im-test","output_volume_id":"vo-out","input_volume_id":"vo-in",
    "attempt_timeout_seconds_by_arm":{"A":5813,"H":600},"task_local_directory":str(self.local),"absolute_deadline_unix":time.time()+300,
    "control_manifest":ref("control.json"),"input_manifest":ref("manifest.json"),"input_witness":ref("witness.json")}
 def run_case(self,key="A-0",deadline=False,ready_pin=None):
  events=[];p=dict(self.p,selected_task=key)
  test=self
  class Image:
   @staticmethod
   def from_id(*a,**kw):return Image()
   def add_local_python_source(self,*a):return self
  class Volume:
   @staticmethod
   def from_id(*a,**kw):return Volume()
   def read_only(self):events.append("readonly");return self
  class Function:
   def __init__(self,name):self.name=name
   def remote(self,spec):
    events.append("control");test.assertEqual(spec["manifest_bytes"],(test.root/"control.json").read_bytes())
    return {"status":"PASS","manifest_sha256":p["control_manifest"]["sha256"]}
   def spawn(self,*args):events.append("fit");return "call"
  class App:
   app_id="ap-test"
   def __init__(self,name):events.append("app")
   def function(self,**kw):
    events.append(("options",kw))
    return lambda fn:Function(fn.__name__)
  class Backend:
   def __init__(self,identity):pass
   def containers(self,timeout):events.append("containers-empty");return []
  if ready_pin is not None:(self.local.parent/"controls-ready.json").write_text(json.dumps({"manifest_sha256":ready_pin}))
  fake=types.SimpleNamespace(Image=Image,Volume=Volume,App=App)
  with patch.dict(sys.modules,modal=fake),patch.object(t,"ROOT",self.root),patch.object(t,"verify_client"),patch.object(t,"Backend",Backend),patch.object(lifecycle,"guard_reason",return_value="funded deadline" if deadline else None):
   _,function=t.build_app_v4(p,t.IDENTITY,object(),key)
   if deadline or (ready_pin is not None and ready_pin!=p["control_manifest"]["sha256"]):
    with self.assertRaises(ValueError):function.spawn(key[0],0,"registered",p)
   else:self.assertEqual(function.spawn(key[0],0,"registered",p),"call")
  return events
 def test_a0_control_stops_before_gpu(self):
  events=self.run_case();self.assertLess(events.index("control"),events.index("containers-empty"));self.assertLess(events.index("containers-empty"),events.index("fit"))
  self.assertTrue((self.local.parent/"controls-ready.json").exists());self.assertEqual(events.count("fit"),1)
 def test_other_task_waits_for_exact_control(self):
  events=self.run_case("H-0",ready_pin=self.p["control_manifest"]["sha256"])
  self.assertNotIn("control",events);self.assertEqual(events.count("fit"),1)
 def test_control_pin_mismatch_refuses_gpu(self):
  events=self.run_case("H-0",ready_pin="0"*64);self.assertNotIn("fit",events)
 def test_guard_deadline_refuses_gpu_and_control(self):
  events=self.run_case(deadline=True);self.assertNotIn("fit",events);self.assertNotIn("control",events)
 def test_gpu_and_cpu_timeouts_remain_inside_slot(self):
  events=self.run_case();options=[v[1] for v in events if isinstance(v,tuple)]
  gpu=next(o for o in options if o.get("gpu"));cpu=next(o for o in options if not o.get("gpu"))
  self.assertEqual((gpu["gpu"],gpu["cpu"],gpu["memory"],gpu["timeout"],gpu["startup_timeout"],gpu["retries"]),("L40S",(8,8),(32768,32768),5813,150,0))
  self.assertEqual((cpu["timeout"],cpu["startup_timeout"],cpu["retries"]),(150,150,0));self.assertEqual(set(cpu["volumes"]),{"/outputs"})
if __name__=="__main__":unittest.main(verbosity=2)
