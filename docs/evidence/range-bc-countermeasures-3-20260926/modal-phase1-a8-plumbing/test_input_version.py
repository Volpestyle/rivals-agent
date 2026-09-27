import ast,hashlib,json,pathlib,unittest
from unittest.mock import patch
import volume_inventory
B=pathlib.Path(__file__).resolve().parent
class FakePath:
 def __init__(self,value):self.value=str(value)
 def __str__(self):return self.value
 def __truediv__(self,other):return FakePath(self.value+"/"+other)
 def __eq__(self,other):return str(self)==str(other)
 def is_symlink(self):return self.value=="/inputs"
 def is_dir(self):return True
 def readlink(self):return FakePath("/__modal/volumes/vo-NpcsP2imIIon902PW96bTb")
 def resolve(self,strict=True):return self.readlink()
class Version(unittest.TestCase):
 def verify(self,version):
  raw=(B/"fixtures/volume-version-witness.json").read_bytes();w=json.loads(raw)
  with patch.object(volume_inventory.pathlib,"Path",FakePath),patch.object(volume_inventory,"inventory",return_value=w["inventory"]):
   return volume_inventory.verify_metadata("/inputs",raw,hashlib.sha256(raw).hexdigest(),w["volume_id"],version)
 def test_current_inputs07_metadata_accepted(self):self.assertEqual(self.verify("inputs-07")["status"],"PASS")
 def test_old_inputs04_refused(self):
  with self.assertRaises(ValueError):self.verify("inputs-04")
 def test_worker_uses_bound_version(self):
  tree=ast.parse((B/"phase_worker.py").read_text())
  call=next(n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=="verify_metadata")
  self.assertEqual(ast.dump(call.args[-1]),ast.dump(ast.parse('p["input_version_id"]',mode="eval").body))
 def test_collector_and_host_bind_same_version(self):
  self.assertIn('verification["version_id"]==p["input_version_id"]',(B/"collect_phase.py").read_text())
  self.assertIn('witness["version_id"]==p["input_version_id"]',(B/"phase_transport.py").read_text())
  self.assertIn('for key in ("input_version_id",',(B/"phase_transport.py").read_text())
if __name__=="__main__":unittest.main()
