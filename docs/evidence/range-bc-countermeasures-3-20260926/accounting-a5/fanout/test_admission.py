"""Phase admission edges and explicit overhead inclusion; no live data or RPC."""
import pathlib,tempfile,unittest
import safety,cm3_timeouts as timing
from test_fixes import Fixture

class Admission(unittest.TestCase):
 def test_explicit_hash_diagnostics_are_inside_owner_limit(self):
  work=timing.work_limits({a:450 for a in timing.ARMS})
  self.assertEqual(work,{a:712 for a in timing.ARMS})
  self.assertEqual(712-timing.OWNER_MARGIN_SECONDS,450+timing.HASH_SECONDS+timing.DIAGNOSTICS_SECONDS)
  for bad in (-1,0,float("inf"),float("nan"),True,1.7e308):
   with self.assertRaises(ValueError):timing.work_limits({a:bad for a in timing.ARMS})
 def test_exact_phase_time_admission_boundary(self):
  with tempfile.TemporaryDirectory() as tmp:
   for phase in ("phase1","phase2"):
    f=Fixture(tmp,phase);p=f.p
    out=safety.projection(p)
    ceiling=57600-out["remaining_compute_seconds"]
    f.ledger["charges"][1]["compute_seconds"]=ceiling-f.ledger["charges"][0]["compute_seconds"]
    f.refresh_ledger()
    safety.ledger(p,pathlib.Path(tmp)/"state"/p["campaign_id"]/"reservations")
    f.ledger["charges"][1]["compute_seconds"]+=1;f.refresh_ledger()
    with self.assertRaisesRegex(ValueError,"16 hours"):safety.ledger(p,pathlib.Path(tmp)/"state"/p["campaign_id"]/"reservations")
 def test_exact_phase_dollar_admission_boundary(self):
  with tempfile.TemporaryDirectory() as tmp:
   for phase in ("phase1","phase2"):
    f=Fixture(tmp,phase);p=f.p
    p["cap_usd"]=p["spent_before_usd"]+safety.projection(p)["reserved_max_usd"]
    safety.ledger(p,pathlib.Path(tmp)/"state"/p["campaign_id"]/"reservations")
    p["cap_usd"]-=.000001
    with self.assertRaisesRegex(ValueError,"dollar reservation"):safety.ledger(p,pathlib.Path(tmp)/"state"/p["campaign_id"]/"reservations")
 def test_phase1_does_not_reserve_phase2_holds(self):
  with tempfile.TemporaryDirectory() as tmp:
   f=Fixture(tmp);out=safety.projection(f.p)
   self.assertEqual(out["fit_compute_seconds"],20859)
   self.assertEqual(out["full_matrix_hold_seconds_informational"],40848)
   self.assertEqual(set(out["current_task_holds"]),safety.PHASE1)
   self.assertLess(out["remaining_compute_seconds"],40848)

if __name__=="__main__":unittest.main(verbosity=2)
