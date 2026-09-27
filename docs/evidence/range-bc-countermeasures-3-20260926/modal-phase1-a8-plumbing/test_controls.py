"""Offline adapter controls; never creates a Modal client or executes training."""
import unittest,pathlib,json,hashlib,copy,ast,tempfile
from unittest.mock import patch
import phase_transport as transport
from safety import canonical
B=pathlib.Path(__file__).resolve().parent
class Controls(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=pathlib.Path(self.tmp.name)
  self.raw=b'{"stage":"fit"}';(self.root/"receipts").mkdir();(self.root/"receipts/A-0.json").write_bytes(self.raw)
  self.pin=hashlib.sha256(self.raw).hexdigest()
  self.p={"output_volume_id":"vo-test","tasks":{"A-0":{"attempt_receipts":[{"path":"A-0.json","sha256":self.pin}]}},"receipt_root":"/outputs/.modal-control/phase1-02/receipts"}
  self.m={"format":"cm3-phase-control-manifest-v1","approved_by":"herdr-lead","root":"/outputs/.modal-control/phase1-02","identity":transport.IDENTITY,"output_volume_id":"vo-test","tasks_sha256":canonical(self.p["tasks"]),
   "files":{self.p["receipt_root"]+"/A-0.json":{"local_path":"receipts/A-0.json","bytes":len(self.raw),"sha256":self.pin}}}
  for i in range(100):
   rel="accounting/filler-"+str(i)+".json";p=self.root/rel;p.parent.mkdir(exist_ok=True);p.write_bytes(b"{}")
   self.m["files"][self.m["root"]+"/"+rel]={"local_path":rel,"bytes":2,"sha256":hashlib.sha256(b"{}").hexdigest()}
 def check(self):
  with patch.object(transport,"ROOT",self.root):return transport.validate_control_manifest(self.p,self.m)
 def test_valid(self):self.assertEqual(self.check(),self.m)
 def test_changed_payload(self):
  (self.root/"receipts/A-0.json").write_bytes(b"x"*len(self.raw))
  self.assertRaises(ValueError,self.check)
 def test_missing_receipt(self):
  self.m["files"]={};self.assertRaises(ValueError,self.check)
 def test_local_escape(self):
  next(iter(self.m["files"].values()))["local_path"]="../secrets.json";self.assertRaises(ValueError,self.check)
 def test_remote_escape(self):
  self.m["files"]["/outputs/.modal-control/phase1-02/../escape.json"]=self.m["files"].pop(self.p["receipt_root"]+"/A-0.json")
  self.assertRaises(ValueError,self.check)
 def test_changed_workspace(self):
  self.m["identity"]=dict(transport.IDENTITY,workspace="other");self.assertRaises(ValueError,self.check)
 def test_wrong_volume(self):
  self.m["output_volume_id"]="vo-other";self.assertRaises(ValueError,self.check)
 def test_changed_task_routing(self):
  self.m["tasks_sha256"]="0"*64;self.assertRaises(ValueError,self.check)
 def test_symlink_source(self):
  original=self.root/"receipts/A-0.json";original.rename(self.root/"original.json");original.symlink_to(self.root/"original.json")
  self.assertRaises(ValueError,self.check)
