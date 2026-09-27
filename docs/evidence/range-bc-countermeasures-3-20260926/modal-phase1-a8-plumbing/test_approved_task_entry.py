import pathlib,json,tempfile,unittest
from unittest.mock import patch
import approved_task_entry as entry
from safety import digest
class EntryBoundary(unittest.TestCase):
 def setUp(self):
  entry.task_driver.DRAFT_LAUNCH_ENABLED=False
  entry.modal_app.DEPLOYMENT_ENABLED=False
 def tearDown(self):self.setUp()
 def invoke(self,pin=None,approval_error=None):
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp)/"runtime.json";p.write_text(json.dumps({"plan":{"attempt":"synthetic"}}))
   with patch.object(entry.sys,"argv",["entry","/synthetic/task",str(p),pin or digest(p)]),patch.object(entry,"validate_authority",side_effect=approval_error) as authority,patch.object(entry.task_driver,"execute") as execute:
    entry.main()
    authority.assert_called_once_with({"attempt":"synthetic"})
    execute.assert_called_once_with("/synthetic/task",{"path":str(p),"sha256":digest(p)})
 def test_good_approval_enables_process_flags(self):
  self.invoke()
  self.assertTrue(entry.task_driver.DRAFT_LAUNCH_ENABLED and entry.modal_app.DEPLOYMENT_ENABLED)
 def test_bad_runtime_pin_never_enables(self):
  with self.assertRaises(ValueError):self.invoke(pin="0"*64)
  self.assertFalse(entry.task_driver.DRAFT_LAUNCH_ENABLED or entry.modal_app.DEPLOYMENT_ENABLED)
 def test_rejected_authority_never_enables(self):
  with self.assertRaisesRegex(ValueError,"missing approval"):self.invoke(approval_error=ValueError("missing approval"))
  self.assertFalse(entry.task_driver.DRAFT_LAUNCH_ENABLED or entry.modal_app.DEPLOYMENT_ENABLED)
 def test_original_driver_remains_byte_exact(self):
  b=pathlib.Path(__file__).resolve().parent
  import hashlib
  self.assertEqual(hashlib.sha256(pathlib.Path(entry.task_driver.__file__).read_bytes()).hexdigest(),'262a7bcabd435e18edd4d03ae6e99549b580be76d3d1e73d26ca5eb53a7d3d17')
 def test_child_entry_is_explicit(self):
  b=pathlib.Path(__file__).resolve().parent
  self.assertIn('approved_task_entry.py',(b/"modal_app.py").read_text())
if __name__=="__main__":unittest.main()
