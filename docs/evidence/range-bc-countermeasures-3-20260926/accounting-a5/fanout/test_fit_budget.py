"""Lead receipt allocations must exactly match the shared per-task plan."""
import copy,pathlib,tempfile,unittest
import safety,cm3_timeouts as timing
from test_fixes import Fixture

class FitBudget(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
 def budget(self,p,key):
  h=p["task_holds"][key];extra=p["overhead_reserve_usd"] if key==min(p["tasks"]) else 0
  return {"stage_seconds":h["owner_stage_seconds"],"hold_seconds":h["total_seconds"],
   "hold_usd":timing.hold_usd(h)+extra,"hourly_usd":p["resource_rate_usd_second"]*3600,
   "stage_overhead_usd":extra,"cap_seconds":57600,"cloud_cap_usd":p["cap_usd"],
   "spent_seconds":p["spent_before_compute_seconds"],"spent_usd":p["spent_before_usd"],
   "accounting":{"path":"/inputs/accounting.json","sha256":p["campaign_ledger"]["sha256"]}}
 def test_exact_all_thirteen_allocations(self):
  n=0
  for phase in ("phase1","phase2"):
   p=Fixture(self.tmp.name,phase).p
   for key in p["tasks"]:
    safety.fit_budget(p,key,self.budget(p,key));n+=1
  self.assertEqual(n,13)
 def test_owner_stage_hold_overhead_rate_prior_and_pin_changes_refused(self):
  p=Fixture(self.tmp.name).p;key="A-0";b=self.budget(p,key)
  changes={"stage_seconds":b["stage_seconds"]-1,"hold_seconds":b["hold_seconds"]-1,
   "hold_usd":b["hold_usd"]-.000001,"stage_overhead_usd":0,
   "hourly_usd":b["hourly_usd"]-.01,"spent_seconds":0,"spent_usd":0,
   "cap_seconds":57601,"cloud_cap_usd":51,"accounting":{"sha256":"0"*64}}
  for name,bad in changes.items():
   with self.subTest(name=name):
    x=copy.deepcopy(b);x[name]=bad
    with self.assertRaises(ValueError):safety.fit_budget(p,key,x)
 def test_nonfinite_and_boolean_receipt_allocations_refused(self):
  p=Fixture(self.tmp.name).p;key="H-0";b=self.budget(p,key)
  for name in ("stage_seconds","hold_seconds","hold_usd","hourly_usd","stage_overhead_usd","spent_seconds","spent_usd","cap_seconds","cloud_cap_usd"):
   for bad in (-1,float("nan"),float("inf"),True):
    x=copy.deepcopy(b);x[name]=bad
    with self.assertRaises(ValueError):safety.fit_budget(p,key,x)
 def test_final_plus300_boundaries(self):
  for phase,prior in (("phase1",36441),("phase2",37311)):
   p=Fixture(self.tmp.name,phase).p
   out=safety.projection(p)
   self.assertEqual(57600-out["remaining_compute_seconds"],prior)
   self.assertEqual(out["verification_reserve_seconds"],300)
   bound=safety.clock_bound(p,wall=1000,mono=100)
   self.assertAlmostEqual(bound["campaign_cap_usd"]-bound["cap_usd"],.483156)
if __name__=="__main__":unittest.main(verbosity=2)
