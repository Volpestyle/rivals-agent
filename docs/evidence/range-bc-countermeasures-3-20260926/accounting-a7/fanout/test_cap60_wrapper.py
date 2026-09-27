"""Offline cap-boundary mutations; no Modal calls or corpus access."""
import ast,copy,hashlib,importlib.util,json,pathlib,tempfile,unittest
from unittest.mock import patch
import safety as s
import cm3_accounting as accounting
import cm3_timeouts as timing
ROOT=pathlib.Path(__file__).resolve().parent

class Cap60(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=pathlib.Path(self.tmp.name)
  smoke={a:{"smoke":{"updates":32,"full_schedule_updates":100,"seconds_per_update":1},
   "timing":{"dev_scores":False,"per_epoch_dev_loss_seconds":1,"teacher_seconds":1,
   "self_seconds":1,"teacher_metric_seconds":1,"self_metric_seconds":1}} for a in timing.ARMS}
  measured=timing.measured_seconds(smoke);limits=timing.work_limits(measured)
  self.p=dict(cap_usd=60,resource_rate_usd_second=s.MIN_RATE,spent_before_usd=20,
   spent_before_compute_seconds=24860,overhead_reserve_usd=s.MIN_OVERHEAD_USD,
   startup_shutdown_reserve_seconds=420,smoke_timing=self.ref("smoke.json",smoke),
   expected_fit_seconds_by_arm=measured,attempt_timeout_seconds_by_arm=limits,
   attempts_max=1,phase="phase1",tasks={k:{} for k in s.PHASE1},campaign_id="synthetic")
  self.p["task_holds"]=timing.holds(self.p["tasks"],limits,s.MIN_RATE)
 def ref(self,name,obj):
  p=self.root/name;p.write_text(json.dumps(obj));return dict(local_path=str(p),sha256=s.digest(p))
 def budget(self):
  p=self.p;k="A-0";h=p["task_holds"][k]
  return dict(stage_seconds=h["owner_stage_seconds"],hold_seconds=h["total_seconds"],
   hold_usd=timing.hold_usd(h)+p["overhead_reserve_usd"],hourly_usd=s.MIN_RATE*3600,
   stage_overhead_usd=p["overhead_reserve_usd"],cap_seconds=69120,cloud_cap_usd=60,
   spent_seconds=p["spent_before_compute_seconds"],spent_usd=p["spent_before_usd"],
   accounting={"sha256":"a"*64})
 def test_owner_helper_exact_caps(self):
  self.assertEqual(accounting.CAP_SECONDS,69120);self.assertEqual(str(accounting.CAP_USD),"60")
 def test_new_and_lower_caps_accepted(self):
  for cap in (50,60):
   self.p["cap_usd"]=cap;s.numeric_plan(self.p)
 def test_invalid_caps_refused(self):
  for cap in (60.000001,0,-1,float("nan"),float("inf"),True):
   with self.subTest(cap=cap),self.assertRaises(ValueError):
    s.numeric_plan(dict(self.p,cap_usd=cap))
 def test_all_thirteen_and_verification_still_reserved(self):
  self.assertEqual(len(s.ALL),13);self.assertIn("H-repeat-0",s.ALL)
  for phase,tasks in (("phase1",s.PHASE1),("phase2",s.PHASE2)):
   p=copy.deepcopy(self.p);p.update(phase=phase,tasks={k:{} for k in tasks})
   p["task_holds"]=timing.holds(tasks,p["attempt_timeout_seconds_by_arm"],s.MIN_RATE)
   out=s.projection(p)
   self.assertEqual(out["remaining_compute_seconds"],len(tasks)*1020+300)
   b=s.clock_bound(p,wall=1000,mono=100)
   self.assertAlmostEqual(b["cap_usd"],60-s.verification_reserve_usd(p))
 def test_owner_budget_accepts_boundary_rejects_over_or_substitution(self):
  self.p["campaign_ledger"]={"sha256":"a"*64};b=self.budget()
  s.fit_budget(self.p,"A-0",b)
  for key,bad in (("cap_seconds",69121),("cloud_cap_usd",60.01),("spent_usd",0),
   ("cap_seconds",float("nan")),("cap_seconds",True)):
   with self.subTest(key=key,bad=bad),self.assertRaises(ValueError):
    s.fit_budget(self.p,"A-0",dict(b,**{key:bad}))
 def test_measured_ledger_compute_and_dollar_boundaries(self):
  self.p["campaign_ledger"]=self.ref("ledger.json",{"format":"cm3-measured-accounting-v2","campaign_id":"synthetic"})
  out=s.projection(self.p)
  for seconds,usd,ok in ((69120-out["remaining_compute_seconds"],20,True),
   (69121-out["remaining_compute_seconds"],20,False),
   (24860,60-out["reserved_max_usd"]-0.000001,True),
   (24860,60-out["reserved_max_usd"]+0.000001,False)):
   p=dict(self.p,spent_before_compute_seconds=seconds,spent_before_usd=usd)
   with patch.object(s,"measured_inventory",return_value={}),patch.object(accounting,"ledger",return_value={"spent_seconds":seconds,"spent_usd":usd}):
    if ok:s.ledger(p,self.root/"reservations")
    else:
     with self.assertRaises(ValueError):s.ledger(p,self.root/"reservations")
 def test_prior_spend_mismatch_still_refused(self):
  self.p["campaign_ledger"]=self.ref("ledger.json",{"format":"cm3-measured-accounting-v2","campaign_id":"synthetic"})
  with patch.object(s,"measured_inventory",return_value={}),patch.object(accounting,"ledger",return_value={"spent_seconds":0,"spent_usd":0}):
   with self.assertRaisesRegex(ValueError,"prior spend"):s.ledger(self.p,self.root/"reservations")
 def test_legacy_ledger_compute_boundary(self):
  anchor=self.ref("phase-a-spend.json",{"conservative_total_upper_usd":1})
  out=s.projection(self.p)
  for total,ok in ((69120,True),(69121,False)):
   seconds=total-out["remaining_compute_seconds"]
   data=dict(format="cm3-campaign-ledger-v1",approved_by="herdr-lead",campaign_id="synthetic",
    profile="rivals",workspace="volpestyle",coverage=dict(phase_a=True,preflight=True,failed_attempts=True),
    charges=[dict(id="a",kind="phase_a",gross_usd=1,compute_seconds=3824,evidence=anchor),
     dict(id="pre",kind="preflight",gross_usd=19,compute_seconds=seconds-3824,evidence=anchor)])
   p=dict(self.p,campaign_ledger=self.ref("legacy.json",data),spent_before_compute_seconds=seconds)
   with patch.object(s,"__file__",str(self.root/"safety.py")):
    if ok:s.ledger(p,self.root/"campaign/reservations")
    else:
     with self.assertRaisesRegex(ValueError,"19.2 hours"):s.ledger(p,self.root/"campaign/reservations")
 def test_funded_clock_refuses_reserve_overrun(self):
  out=s.projection(self.p)
  self.p["spent_before_usd"]=60-out["reserved_max_usd"]+0.000001
  with self.assertRaisesRegex(ValueError,"funded"):s.clock_bound(self.p,wall=1000,mono=100)
 def test_running_spend_stop_retains_cleanup_and_verify(self):
  b=s.clock_bound(self.p,wall=1000,mono=100)
  b["prior_usd"]=b["cap_usd"]-b["overhead_usd"]-5*120*s.MIN_RATE-0.000001
  s.running_bound(b,wall=1000,mono=100)
  with self.assertRaisesRegex(ValueError,"spend stop"):s.running_bound(b,wall=1000.01,mono=100.01)
 def test_running_deadline_still_enforced(self):
  b=s.clock_bound(self.p,wall=1000,mono=100)
  with self.assertRaisesRegex(ValueError,"deadline"):s.running_bound(b,wall=1900,mono=1000)
 def test_serial_guard_uses_passed_cap(self):
  spec=importlib.util.spec_from_file_location("serial_safety",ROOT/"serial-runtime/safety.py")
  m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  b=dict(prior_usd=59,overhead_usd=0,all_calls_rate=.001,started_monotonic=100,
   started_at_unix=1000,stop_monotonic=10000,stop_at_unix=10000,cap_usd=60)
  m.running_bound(b,mono=100,wall=1000)
  with self.assertRaises(ValueError):m.running_bound(b,mono=981,wall=1881)
 def test_only_requested_source_substitutions(self):
  lineage=json.loads((ROOT/"lineage.json").read_text())
  for name,row in lineage.items():
   source=pathlib.Path(row["source"])
   self.assertEqual(s.digest(source),row["before_sha256"])
   self.assertEqual(s.digest(ROOT/name),row["sha256"])
   if name in ("safety.py","canonical_safety.py","serial-runtime/safety.py"):
    expected=source.read_text().replace("<=50","<=60").replace("57600","69120").replace("16 hours","19.2 hours")
    self.assertEqual((ROOT/name).read_text(),expected)
   if name.startswith("templates/"):
    self.assertEqual((ROOT/name).read_text(),source.read_text().replace("57600","69120").replace('"cap_usd":50','"cap_usd":60').replace("cap_usd=50","cap_usd=60"))
 def test_serial_driver_literal_cap_contract(self):
  tree=ast.parse((ROOT/"templates/stage_driver.py").read_text())
  budgets=[ast.literal_eval(n) for n in ast.walk(tree) if isinstance(n,ast.Dict) and any(isinstance(k,ast.Constant) and k.value=="cap_seconds" for k in n.keys)]
  self.assertEqual(len(budgets),1);self.assertEqual(budgets[0]["cap_seconds"],69120);self.assertEqual(budgets[0]["cap_usd"],60)
if __name__=="__main__":unittest.main(verbosity=2)
