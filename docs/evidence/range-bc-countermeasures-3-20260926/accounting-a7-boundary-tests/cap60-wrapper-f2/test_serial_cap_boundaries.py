import importlib.util,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
SOURCE=Path(os.environ.get("SERIAL_SAFETY_SOURCE",str(Path(__file__).resolve().parent.parent/"cap60-wrapper/serial-runtime/safety.py")))
spec=importlib.util.spec_from_file_location("serial_safety_f2",SOURCE)
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
class Boundaries(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.p=dict(cap_usd=60,resource_rate_usd_second=s.MIN_RATE,attempt_timeout_seconds=600,
   expected_fit_seconds=100,spent_before_usd=2,spent_before_compute_seconds=0,overhead_reserve_usd=.75,
   startup_shutdown_reserve_seconds=420,attempts_max=1,phase="phase1",tasks={k:{} for k in s.PHASE1},campaign_id="f2")
 def ref(self,name,obj):
  p=self.root/name;p.write_text(json.dumps(obj));return dict(local_path=str(p),sha256=s.digest(p))
 def test_60_accepts(self):s.numeric_plan(self.p)
 def test_60_01_refuses(self):
  self.p["cap_usd"]=60.01
  with self.assertRaisesRegex(ValueError,"cap/timeout"):s.numeric_plan(self.p)
 def aggregate(self,total):
  prior=total-s.projection(self.p)["remaining_compute_seconds"];self.p["spent_before_compute_seconds"]=prior
  ref=self.ref("phase-a-spend.json",dict(conservative_total_upper_usd=1))
  data=dict(format="cm3-campaign-ledger-v1",approved_by="herdr-lead",campaign_id="f2",
   profile="rivals",workspace="volpestyle",coverage=dict(phase_a=True,preflight=True,failed_attempts=True),
   charges=[dict(id="a",kind="phase_a",gross_usd=1,compute_seconds=3824,evidence=ref),
   dict(id="p",kind="preflight",gross_usd=1,compute_seconds=prior-3824,evidence=ref)])
  self.p["campaign_ledger"]=self.ref("ledger.json",data)
  # Relocate only the synthetic anchor: real document/hash/projection/ledger checks execute.
  with patch.object(s,"__file__",str(self.root/"safety.py")):
   return s.ledger(self.p,self.root/"campaigns/test/reservations")
 def test_69120_accepts(self):self.assertEqual(self.aggregate(69120)["campaign_id"],"f2")
 def test_69121_refuses(self):
  with self.assertRaisesRegex(ValueError,"aggregate compute"):self.aggregate(69121)
if __name__=="__main__":unittest.main(verbosity=2)
