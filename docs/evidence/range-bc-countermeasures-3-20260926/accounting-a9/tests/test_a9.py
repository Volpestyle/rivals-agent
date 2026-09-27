import pathlib,sys,json,unittest,copy
from decimal import Decimal
B=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(B.parent/"fanout"))
import cm3_timeouts as t,cm3_budget_plan as bp,safety
class A9(unittest.TestCase):
 def setUp(self):self.smoke=json.loads((B/"smoke-details.json").read_bytes());self.plan=bp.derive(self.smoke)
 def test_h_only_floor_and_holds(self):
  self.assertEqual(self.plan["attempt_timeout_seconds_by_arm"],{"A":5591,"H":900,"I":4338,"W":600})
  for k in ["H-0","H-repeat-0","H-1","H-2"]:
   h=self.plan["task_holds"][k];self.assertEqual((h["work_seconds"],h["owner_stage_seconds"],h["total_seconds"]),(900,870,1320))
 def test_measured_h_above_floor_still_scales(self):
  self.assertEqual(t.work_limits({"A":1,"H":1000,"I":1,"W":1})["H"],1500)
 def test_exact_current_admission(self):
  current={k:self.plan["task_holds"][k] for k in bp.PHASE1}
  seconds=sum(v["total_seconds"] for v in current.values())+300
  dollars=sum((Decimal(str(t.hold_usd(v))) for v in current.values()),Decimal(0))+Decimal(".75")+Decimal(".483156")
  self.assertEqual(seconds,20973);self.assertEqual(dollars,Decimal("16.073065"))
  self.assertEqual(30651+seconds,51624);self.assertEqual(Decimal("26.24034256")+dollars,Decimal("42.31340756"))
 def test_caps_rate_and_clock_policy_unchanged(self):
  import cm3_accounting as a
  self.assertEqual((a.CAP_SECONDS,a.CAP_USD,bp.RATE),(69120,Decimal("60"),.00071784))
  self.assertEqual((t.STARTUP_SECONDS,t.STOP_SECONDS,t.OWNER_MARGIN_SECONDS),(300,120,30))
  self.assertEqual(bp.EXTRACTION_HOLD_SECONDS,2320)
if __name__=="__main__":unittest.main(verbosity=2)
