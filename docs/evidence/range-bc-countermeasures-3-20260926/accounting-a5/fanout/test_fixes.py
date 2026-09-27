"""Synthetic-only regression tests for independent review F1-F5. No cloud/data/accelerator calls."""
import copy,datetime,hashlib,json,os,pathlib,tempfile,time,unittest,uuid
from unittest.mock import patch
import safety,lifecycle,input_closure,collector,modal_app
import cm3_timeouts as timeouts
ROOT=pathlib.Path(__file__).parent
def encoded(value):return json.dumps(value,sort_keys=True,allow_nan=False).encode()
def h(data):return hashlib.sha256(data).hexdigest()
class Fixture:
    def __init__(self,root,phase="phase1"):
        self.root=pathlib.Path(root);self.n=0
        self.p=json.loads((ROOT/"launch-plan.json").read_bytes());p=self.p
        p.update(integration_review_pass=True,fixes2_review_pass=True,entrypoint_supports_arm_seed=True,
          campaign_id="synthetic-"+uuid.uuid4().hex,run_id="synthetic-phase-"+uuid.uuid4().hex,phase=phase,
          reviewed_image_digest="example.invalid/synthetic@sha256:"+"a"*64,
          reviewed_input_volume="synthetic-inputs",input_volume_id="vo-synthetic-inputs",
          output_volume="synthetic-outputs",output_volume_id="vo-synthetic-outputs",code_directory="code",
          spent_before_usd=0,spent_before_compute_seconds=0)
        context={"amendment":3,"device":"cuda","hardware":{"class":"cuda:L40S","driver":"synthetic","cuda_runtime":"synthetic","cudnn":"synthetic"},
                 "code":{"policy/range_bc/cm3_run.py":p["entrypoint_sha256"]},"sources":{},"assets":{"directory":"/inputs/assets","config_sha256":h(b"{}")}}
        files=[]
        def file(path,kind,data=b"synthetic",**kwargs):
            row={"path":path,"kind":kind,"sha256":h(data),"bytes":len(data),**kwargs};files.append(row);return {"path":"/inputs/"+path,"sha256":row["sha256"]}
        for sid in input_closure.TRAIN+input_closure.DEV:
            kind="train" if sid in input_closure.TRAIN else "frozen-dev"
            table=file("steps/"+sid+".jsonl",kind,session_id=sid)
            cache="caches/"+sid
            manifest=None
            for name in ("global.u8","crop.u8","hud.u8","cache.json"):
                ref=file(cache+"/"+name,kind,session_id=sid)
                if name=="cache.json":manifest=ref["sha256"]
            context["sources"][sid]={"role":"train" if kind=="train" else "dev","table":table,"sidecar":file("sidecars/"+sid+".jsonl",kind,session_id=sid) if kind=="train" else None,"cache":"/inputs/"+cache,"cache_manifest_sha256":manifest}
        file("code/policy/range_bc/cm3_run.py","code")
        files[-1]["sha256"]=p["entrypoint_sha256"] # synthetic remote-verification stand-in, not real code bytes
        file("assets/config.json","asset",b"{}");file("assets/model.safetensors","asset")
        p["context_sha256"]=safety.canonical(context);p["approved_context"]=self.ref(context)
        p["tasks"]={}
        for key in sorted(safety.PHASE1 if phase=="phase1" else safety.PHASE2):
            ref=file("receipts/"+key+".json","receipt",encoded({"synthetic":key}))
            p["tasks"][key]={"attempt_receipts":[{"path":ref["path"].removeprefix("/inputs/"),"sha256":ref["sha256"],"attempt_id":key+"-first","output":"/outputs/run/"+key}]}
        p["task_holds"]=timeouts.holds(p["tasks"],p["attempt_timeout_seconds_by_arm"],p["resource_rate_usd_second"])
        completed={}
        if phase=="phase2":
            outputs={k:{"path":"/outputs/phase1/"+k+"/result.json","sha256":"f"*64} for k in ("A0","A1","A2","H0","H0_repeat")}
            identity={"checkpoint_sha256":"1"*64,"content_sha256":"2"*64}
            gate={"format":"cm3-phase1-gate-v1","status":"PASS","approved_by":"herdr-lead","context_sha256":p["context_sha256"],
                  "completed":(datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(seconds=10)).isoformat(),
                  "outputs":outputs,"A_control_gate":{"status":"PASS","controls":{str(s):identity for s in range(3)}},
                  "H0_repeat":{"status":"PASS","repeat_identical":True,"H0":identity,"repeat":identity}}
            local=self.ref(gate);remote=file("receipts/phase1-gate.json","receipt",encoded(gate))
            p["phase1_gate"]={"local_path":local["local_path"],"sha256":local["sha256"],"remote_ref":remote}
            completed={key:outputs[out] for key,out in {"A-0":"A0","A-1":"A1","A-2":"A2","H-0":"H0","H-repeat-0":"H0_repeat"}.items()}
        m={"format":"cm3-input-closure-v1","status":"FROZEN","approved_by":"herdr-lead","sealed_excluded":True,"train_sessions":list(input_closure.TRAIN),
           "frozen_dev_sessions":list(input_closure.DEV),"profile":"rivals","workspace":"volpestyle","volume_name":p["reviewed_input_volume"],
           "volume_id":p["input_volume_id"],"code_directory":"code","asset_directory":"assets","context_sha256":p["context_sha256"],"files":files}
        p["input_manifest"]=self.ref(m)
        p["input_verification"]=self.ref({"format":"cm3-volume-verification-v1","status":"PASS","exact_inventory":True,"sealed_excluded":True,
          "profile":"rivals","workspace":"volpestyle","volume_name":m["volume_name"],"volume_id":m["volume_id"],"manifest_sha256":p["input_manifest"]["sha256"],
          "files":len(files),"bytes":sum(x["bytes"] for x in files),"verifier_sha256":safety.digest(ROOT/"input_closure.py")})
        prior=json.loads((ROOT/"phase-a-spend.json").read_bytes())
        self.ledger={"format":"cm3-campaign-ledger-v1","approved_by":"herdr-lead","campaign_id":p["campaign_id"],"profile":"rivals","workspace":"volpestyle",
          "coverage":{"phase_a":True,"preflight":True,"failed_attempts":True},"completed_phase1":completed,
          "charges":[{"id":"phase-a","kind":"phase_a","gross_usd":prior["conservative_total_upper_usd"],"compute_seconds":3824,
                     "evidence":{"local_path":str(ROOT/"phase-a-spend.json"),"sha256":safety.digest(ROOT/"phase-a-spend.json")}},
                    {"id":"preflight","kind":"preflight","gross_usd":1,"compute_seconds":1000,"evidence":self.ref({"synthetic":"preflight"})}]}
        self.refresh_ledger()
    def ref(self,obj):
        self.n+=1;p=self.root/(str(self.n)+".json");p.write_bytes(encoded(obj));return {"local_path":str(p),"sha256":safety.digest(p)}
    def refresh_binding(self):
        p=self.p;context=safety.document(p["approved_context"])
        b={k:p[k] for k in ("campaign_id","run_id","phase","profile","workspace","gpu","cpu","memory_mib","benchmark_provider","resource_rate_usd_second",
                            "context_sha256","entrypoint_sha256","reviewed_image_digest","code_directory","input_volume_id","output_volume_id","reviewed_input_volume","output_volume","smoke_timing","expected_fit_seconds_by_arm","attempt_timeout_seconds_by_arm","task_holds","overhead_reserve_usd")}
        b.update(format="cm3-modal-launch-binding-v1",approved_by="herdr-lead",workspace_id="wk-synthetic",judge_model=p["device_class"],judge_instance=p["device_class"],
          runner_class=context["hardware"]["class"],hardware=context["hardware"],input_manifest_sha256=p["input_manifest"]["sha256"],
          campaign_ledger_sha256=p["campaign_ledger"]["sha256"],campaign_ledger_local_path=p["campaign_ledger"]["local_path"],tasks_sha256=safety.canonical(p["tasks"]),tasks=p["tasks"],
          harness_code={n:safety.digest(ROOT/n) for n in ("modal_app.py","safety.py","lifecycle.py","guard.py","identity_probe.py","input_closure.py","collector.py","packet_adapter.py","map_metrics.py","job_status.py","cm3_timeouts.py","cm3_budget_plan.py","cm3_accounting.py","task_driver.py","judge_entry.py")})
        p["launch_binding"]=self.ref(b)
    def refresh_ledger(self):
        self.p["campaign_ledger"]=self.ref(self.ledger)
        self.p["spent_before_usd"]=sum(x["gross_usd"] for x in self.ledger["charges"])
        self.p["spent_before_compute_seconds"]=sum(x["compute_seconds"] for x in self.ledger["charges"])
        self.refresh_binding()
class Boundaries(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.f=Fixture(self.temp.name);self.p=self.f.p
    def test_valid_phase1(self):modal_app.validate_launch(self.p);self.assertEqual(safety.projection(self.p)["executions_including_repeat"],13)
    def test_valid_phase2(self):
        f=Fixture(self.temp.name,"phase2");modal_app.validate_launch(f.p)
    def test_fit_review_49_dollar_reproduction(self):
        p=copy.deepcopy(self.p);p.update(spent_before_usd=49,overhead_reserve_usd=-40)
        with self.assertRaisesRegex(ValueError,"nonnegative"):modal_app.validate_launch(p)
    def test_nonfinite_negative_and_boolean_numbers(self):
        for key in ("cap_usd","resource_rate_usd_second","attempt_timeout_seconds","expected_fit_seconds","spent_before_usd",
                    "spent_before_compute_seconds","overhead_reserve_usd","startup_shutdown_reserve_seconds"):
            for bad in (-1,float("nan"),float("inf"),float("-inf"),True):
                with self.subTest(key=key,bad=str(bad)):
                    p=copy.deepcopy(self.p);p[key]=bad
                    with self.assertRaises(ValueError):modal_app.validate_launch(p)
    def test_positive_durations(self):
        for key in ("attempt_timeout_seconds","expected_fit_seconds"):
            p=copy.deepcopy(self.p);p[key]=0
            with self.assertRaises(ValueError):modal_app.validate_launch(p)
    def test_no_caller_clocks(self):
        for key in ("spend_started_at_unix","absolute_deadline_unix"):
            p=copy.deepcopy(self.p);p[key]=time.time()+99999
            with self.assertRaisesRegex(ValueError,"runtime clocks"):modal_app.validate_launch(p)
    def test_mandatory_repeat_reproduction(self):
        p=copy.deepcopy(self.p);p.update(h0_repeat_required=False,spent_before_usd=10)
        with self.assertRaisesRegex(ValueError,"repeat"):modal_app.validate_launch(p)
    def test_current_phase_reservation_exceeds_cap(self):
        self.f.ledger["charges"][1]["gross_usd"]=40-self.f.ledger["charges"][0]["gross_usd"]
        self.f.refresh_ledger()
        self.assertEqual(safety.projection(self.p)["executions_including_repeat"],13)
        with self.assertRaisesRegex(ValueError,"dollar reservation"):modal_app.validate_launch(self.p)
    def test_startup_matches_function_timeout(self):
        p=copy.deepcopy(self.p);p["startup_shutdown_reserve_seconds"]=60
        with self.assertRaises(ValueError):modal_app.validate_launch(p)
    def test_cost_and_time_ledger_bindings(self):
        for key in ("spent_before_usd","spent_before_compute_seconds"):
            p=copy.deepcopy(self.p);p[key]=0
            with self.assertRaisesRegex(ValueError,"ledger"):modal_app.validate_launch(p)
    def test_failed_coverage_required(self):
        self.f.ledger["coverage"]["failed_attempts"]=False;self.f.refresh_ledger()
        with self.assertRaises(ValueError):modal_app.validate_launch(self.p)
    def test_phase_a_cannot_be_omitted(self):
        self.f.ledger["charges"][0]["gross_usd"]=0;self.f.refresh_ledger()
        with self.assertRaisesRegex(ValueError,"Phase A"):modal_app.validate_launch(self.p)
    def test_pending_reservation_cannot_be_reused(self):
        state=pathlib.Path(self.temp.name)/"state"
        identity={"profile":"rivals","workspace":"volpestyle","workspace_id":"wk-synthetic"}
        lifecycle.reserve(self.p,state,identity)
        self.p["run_id"]="another";self.f.refresh_binding()
        with self.assertRaisesRegex(ValueError,"unsettled"):lifecycle.reserve(self.p,state,identity)
        old=sorted((state/self.p["campaign_id"]/"reservations").glob("*.json"))[0];r=json.loads(old.read_bytes())
        another=copy.deepcopy(self.p);another["campaign_id"]="new-campaign"
        with self.assertRaisesRegex(ValueError,"unsettled"):
            safety.ledger(self.p,state/"new-campaign"/"reservations")
        for path in old.parent.glob("*.json"):
            r=json.loads(path.read_bytes())
            self.f.ledger["charges"].append({"id":r["run_id"],"kind":"run_reservation","gross_usd":r["reserved_usd"]-(.01 if path==old else 0),"compute_seconds":r["reserved_compute_seconds"],"evidence":{"local_path":str(path),"sha256":safety.digest(path)}})
        self.f.refresh_ledger()
        with self.assertRaisesRegex(ValueError,"undercharged"):safety.ledger(self.p,old.parent)
    def test_phase2_selected_attempts_carried(self):
        f=Fixture(self.temp.name,"phase2");f.ledger["completed_phase1"]["H-0"]["sha256"]="0"*64;f.refresh_ledger()
        with self.assertRaisesRegex(ValueError,"selected attempt"):modal_app.validate_launch(f.p)
    def test_dollar_deadline_and_monotonic_stop(self):
        b=safety.clock_bound(self.p,wall=1000,mono=50)
        self.assertLessEqual(sum(timeouts.hold_usd(t["hold"]) for t in b["tasks"].values()),self.p["cap_usd"]-self.p["spent_before_usd"]-self.p["overhead_reserve_usd"])
        self.assertEqual(safety.running_bound(b,mono=50,wall=1000),self.p["spent_before_usd"]+self.p["overhead_reserve_usd"])
        with self.assertRaises(ValueError):safety.running_bound(b,mono=b["stop_monotonic"],wall=1000)
        with self.assertRaises(ValueError):safety.running_bound(b,mono=50,wall=b["stop_at_unix"])
    def test_consistent_other_classes_refused(self):
        for gpu in ("L4","A10"):
            p=copy.deepcopy(self.p);p.update(gpu=gpu,device_class="modal:"+gpu)
            b=safety.document(p["launch_binding"]);b.update(gpu=gpu,judge_model=p["device_class"],judge_instance=p["device_class"],runner_class="cuda:"+gpu)
            p["launch_binding"]=self.f.ref(b)
            with self.assertRaisesRegex(ValueError,"L40S"):modal_app.validate_launch(p)
    def test_null_volume_extra_files_and_changed_verification(self):
        p=copy.deepcopy(self.p);p["reviewed_input_volume"]=None
        with self.assertRaises(ValueError):modal_app.validate_launch(p)
        v=safety.document(self.p["input_verification"]);v["files"]+=1;self.p["input_verification"]=self.f.ref(v)
        with self.assertRaisesRegex(ValueError,"exact verification"):modal_app.validate_launch(self.p)
    def test_traversal_and_duplicate_receipts(self):
        for field,value in (("path","../outside"),("output","/outputs/.modal-journal/test"),("attempt_id","A-0-first")):
            p=copy.deepcopy(self.p);p["tasks"]["A-1"]["attempt_receipts"][0][field]=value
            with self.assertRaises(ValueError):modal_app.validate_launch(p)
    def test_frozen_manifest_wrong_session_and_hash(self):
        m=safety.document(self.p["input_manifest"]);m["files"][0]["session_id"]="sealed-session"
        with self.assertRaises(ValueError):input_closure.schema(m)
        m=safety.document(self.p["input_manifest"]);m["files"][0]["path"]="../secret"
        with self.assertRaises(ValueError):input_closure.schema(m)
    def test_actual_inventory_corruption_missing_extra_symlink(self):
        # Tiny synthetic bytes only; use schema-valid roster/categories, no corpus read.
        m=safety.document(self.p["input_manifest"]);root=pathlib.Path(self.temp.name)/"stage";root.mkdir()
        for row in m["files"]:
            path=root/row["path"];path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b"x");row.update(sha256=h(b"x"),bytes=1)
        input_closure.check_bytes(m,root)
        extra=root/"sealed.bin";extra.write_bytes(b"DO NOT READ")
        with self.assertRaisesRegex(ValueError,"extra"):input_closure.check_bytes(m,root)
        extra.unlink();target=root/m["files"][0]["path"];target.write_bytes(b"y")
        with self.assertRaisesRegex(ValueError,"changed"):input_closure.check_bytes(m,root)
        target.unlink()
        with self.assertRaisesRegex(ValueError,"missing"):input_closure.check_bytes(m,root)
        target.symlink_to(root/m["files"][1]["path"])
        with self.assertRaisesRegex(ValueError,"symlink"):input_closure.check_bytes(m,root)
    def test_direct_orchestrator_disabled(self):
        with self.assertRaisesRegex(ValueError,"paid launch disabled"):modal_app._orchestrate(self.p)
    def test_default_disabled_without_cloud_import(self):
        import subprocess,sys
        result=subprocess.run([sys.executable,str(ROOT/"modal_app.py"),"--launch"],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0);self.assertIn("paid launch disabled",result.stderr)
class FakeBackend:
    def __init__(self,inv,failures=0,cancel_error=False,wrong_identity=False):
        self.inv=inv;self.failures=failures;self.cancel_error=cancel_error;self.wrong_identity=wrong_identity;self.stops=0;self.stopped=False
    def identity(self,t):return {**self.inv["identity"],"workspace":"wrong"} if self.wrong_identity else self.inv["identity"]
    def apps(self,t):return [{"app_id":"ap-own","description":self.inv["app_name"],"state":"stopped" if self.stopped else "running","tasks":"0" if self.stopped else "1"}]
    def containers(self,t):return [] if self.stopped else [{"app_id":"ap-own"}]
    def cancel(self,c,t):
        if self.cancel_error:raise TimeoutError("synthetic cancellation timeout")
    def stop(self,a,t):
        self.stops+=1
        if self.stops<=self.failures:raise TimeoutError("synthetic stop failure/nonzero")
        self.stopped=True
class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=pathlib.Path(self.temp.name)
        self.inv={"identity":{"profile":"rivals","workspace":"volpestyle","workspace_id":"wk-synthetic"},"app_name":"unique-owned",
                  "apps":[],"calls":{"A-0":"fc-own"},"creation_started":True,"creation_finished":False,"driver_pid":99,
                  "bounds":{"stop_at_unix":2000,"stop_monotonic":500}}
        lifecycle.atomic(self.root/"inventory.json",self.inv)
    def test_conflicting_profile_and_token_override_removed(self):
        with patch.dict(os.environ,{"MODAL_PROFILE":"other-profile","MODAL_TOKEN_ID":"synthetic","MODAL_TOKEN_SECRET":"synthetic"}):
            lifecycle.select_environment();self.assertEqual(os.environ["MODAL_PROFILE"],"rivals");self.assertNotIn("MODAL_TOKEN_SECRET",os.environ)
    def test_identity_failure_refuses_cleanup_in_wrong_account(self):
        backend=FakeBackend(self.inv,wrong_identity=True)
        self.assertEqual(lifecycle.cleanup(self.root,backend,pause=lambda _:None)["status"],"INCOMPLETE_CLEANUP")
        self.assertEqual(backend.stops,0)
    def test_stop_retries_cancel_failure_and_terminal_verification(self):
        backend=FakeBackend(self.inv,failures=2,cancel_error=True)
        result=lifecycle.cleanup(self.root,backend,pause=lambda _:None)
        self.assertEqual(result["status"],"TERMINAL");self.assertEqual(backend.stops,3)
        self.assertTrue(any("cancel_error" in e for e in result["events"]))
        lifecycle.cleanup(self.root,backend,pause=lambda _:None);self.assertEqual(backend.stops,3)
    def test_failed_stop_stays_conspicuously_incomplete(self):
        result=lifecycle.cleanup(self.root,FakeBackend(self.inv,failures=100),pause=lambda _:None)
        self.assertEqual(result["status"],"INCOMPLETE_CLEANUP")
        self.assertEqual(json.loads((self.root/"cleanup.json").read_bytes())["status"],"INCOMPLETE_CLEANUP")
    def test_cli_profile_position_and_clean_environment(self):
        backend=lifecycle.Backend(self.inv["identity"])
        commands=[]
        def run(args,timeout):commands.append(args);return "[]"
        backend.run=run;backend.apps(1);backend.containers(1);backend.stop("ap-own",1)
        for command in commands:
            self.assertEqual(command[command.index("--profile")+1],"rivals")
            self.assertGreater(command.index("--profile"),2)
    def test_dashboard_start_progress_terminal_receipts(self):
        import job_status
        real=job_status.write
        def write(name,**kw):return real(name,root=self.root/"jobs",**kw)
        with patch.object(job_status,"write",side_effect=write),patch.object(modal_app,"ROOT",self.root):
            with self.assertRaisesRegex(ValueError,"paid launch disabled"):modal_app.orchestrate({"run_id":"offline-disabled"})
            status=json.loads((self.root/"jobs/cm3-offline-disabled.status.json").read_bytes())
            self.assertEqual(status["stage"],"failed");self.assertEqual(status["host"],"modal")
            with patch.object(modal_app,"_orchestrate",return_value=self.root/"synthetic-run"):
                modal_app.orchestrate({"run_id":"synthetic-complete"})
            status=json.loads((self.root/"jobs/cm3-synthetic-complete.status.json").read_bytes())
            self.assertEqual(status["stage"],"done");self.assertEqual(status["owner"],"modal-port")
            modal_app.report({"run_id":"synthetic-progress"},"running",{"n":2,"total":5},self.root/"evidence.log")
            status=json.loads((self.root/"jobs/cm3-synthetic-progress.status.json").read_bytes())
            self.assertEqual(status["progress"],{"n":2,"total":5})
    def test_driver_death_and_deadline(self):
        self.assertEqual(lifecycle.guard_reason(self.inv,alive=lambda _:False,wall=lambda:1000,mono=lambda:100),"driver death")
        self.assertEqual(lifecycle.guard_reason(self.inv,alive=lambda _:True,wall=lambda:1000,mono=lambda:501),"funded deadline")
    def test_unknown_creation_not_falsely_terminal(self):
        backend=FakeBackend(self.inv);backend.apps=lambda _:[];backend.containers=lambda _:[]
        self.assertEqual(lifecycle.cleanup(self.root,backend,pause=lambda _:None)["status"],"INCOMPLETE_CLEANUP")
class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=pathlib.Path(self.temp.name);self.data={};self.fixture=Fixture(self.root)
        def add(path,obj=None,data=None,kind="json"):
            raw=encoded(obj) if data is None else data;self.data[path]=(raw,kind);return {"path":path,"sha256":h(raw)}
        context=safety.document(self.fixture.p["approved_context"]);context_sha=safety.canonical(context)
        for ref in collector.refs(context):
            add(ref["path"],data=b"synthetic",kind="opaque")
        approval=add("/inputs/receipts/H0.json",{"attempt_id":"H0-first","output":"/outputs/H0","context":context})
        checkpoint=add("/outputs/H0/model.pt",data=b"synthetic checkpoint",kind="checkpoint")
        details=add("/outputs/H0/details.json",{"checkpoint_file":checkpoint,"checkpoint_sha256":checkpoint["sha256"]})
        result=add("/outputs/H0/result.json",{"format":"cm3-stage-result-v1","status":"PASS","stage":"fit","arm":"H","seed":0,"purpose":"registered",
          "attempt_id":"H0-first","context_sha256":context_sha,"approval":approval,"hardware":{"class":"cuda:L40S"},"artifacts":{"details":details}})
        self.m={"format":"cm3-collection-v1","approved_by":"herdr-lead","identity":{"profile":"rivals","workspace":"volpestyle","workspace_id":"wk-synthetic"},
                "runner_class":"cuda:L40S","max_files":20,"max_bytes":100000,"timeout_seconds":10,"volume_ids":{"inputs":"vo-in","outputs":"vo-out"},
                "selected":[{"arm":"H","seed":0,"purpose":"registered","attempt_id":"H0-first","context_sha256":context_sha,
                             "result_ref":result,"approval_ref":approval,"output":"/outputs/H0"}],"verification_ref":None}
        self.refresh()
    def refresh(self):
        f=self.fixture
        manifest=safety.document(f.p["input_manifest"])
        manifest["files"]=[x for x in manifest["files"] if x["kind"]!="receipt"]
        tasks={}
        for selected in self.m["selected"]:
            key="H-repeat-0" if selected["purpose"]=="repeat" else selected["arm"]+"-"+str(selected["seed"])
            a=selected["approval_ref"];raw=self.data[a["path"]][0]
            manifest["files"].append({"path":a["path"].removeprefix("/inputs/"),"kind":"receipt","sha256":h(raw),"bytes":len(raw)})
            tasks[key]={"attempt_receipts":[{"path":a["path"].removeprefix("/inputs/"),"sha256":a["sha256"],"attempt_id":selected["attempt_id"],"output":selected["output"]}]}
        manifest["volume_id"]=self.m["volume_ids"]["inputs"]
        manifest_ref=f.ref(manifest)
        binding=safety.document(f.p["launch_binding"])
        binding.update(input_manifest_sha256=manifest_ref["sha256"],tasks=tasks,tasks_sha256=safety.canonical(tasks),
                       input_volume_id=self.m["volume_ids"]["inputs"],output_volume_id=self.m["volume_ids"]["outputs"])
        self.m.update(input_manifests=[manifest_ref],launch_bindings=[f.ref(binding)])
        self.m["files"]=[{"path":p,"sha256":h(raw),"bytes":len(raw),"kind":kind} for p,(raw,kind) in self.data.items()]
        path=self.root/("manifest-"+uuid.uuid4().hex+".json");path.write_bytes(encoded(self.m));self.ref={"local_path":str(path),"sha256":h(path.read_bytes())}
    def reader(self,path):yield self.data[path][0]
    def test_good_download_preserves_bytes_and_no_judge_without_owner_verify(self):
        dest=self.root/"good";receipt=collector.collect(self.ref,dest,self.reader)
        self.assertEqual(receipt["status"],"ARTIFACTS_VERIFIED")
        for path,(raw,_) in self.data.items():self.assertEqual((dest/"artifacts"/path.removeprefix("/")).read_bytes(),raw)
        with self.assertRaisesRegex(ValueError,"matrix"):collector.load_verified(dest,self.ref)
    def test_corruption(self):
        def bad(path):yield self.data[path][0]+b"corrupt"
        dest=self.root/"bad"
        with self.assertRaises(ValueError):collector.collect(self.ref,dest,bad)
        self.assertFalse((dest/"collection.json").exists());self.assertTrue((dest/"INCOMPLETE.json").exists())
    def test_interruption(self):
        def broken(path):yield self.data[path][0][:1];raise ConnectionError("synthetic interruption")
        dest=self.root/"interrupted"
        with self.assertRaises(ConnectionError):collector.collect(self.ref,dest,broken)
        self.assertFalse((dest/"collection.json").exists())
    def test_repeated_destination(self):
        dest=self.root/"same";collector.collect(self.ref,dest,self.reader)
        with self.assertRaises(FileExistsError):collector.collect(self.ref,dest,self.reader)
    def test_missing_reference(self):
        self.m["files"]=[f for f in self.m["files"] if not f["path"].endswith("model.pt")]
        path=self.root/"missing.json";path.write_bytes(encoded(self.m))
        with self.assertRaisesRegex(ValueError,"absent"):collector.collect({"local_path":str(path),"sha256":h(path.read_bytes())},self.root/"missing",self.reader)
    def test_substituted_attempt(self):
        self.m["selected"][0]["attempt_id"]="different";self.refresh()
        with self.assertRaisesRegex(ValueError,"attempt"):collector.collect(self.ref,self.root/"substituted",self.reader)
    def full_matrix(self):
        original=copy.deepcopy(self.m["selected"][0])
        approval=json.loads(self.data[original["approval_ref"]["path"]][0]);context=approval["context"]
        for arm,seed,purpose in sorted({(a,s,"registered") for a in ("A","H","I","W") for s in range(3)}|{("H",0,"repeat")}):
            if (arm,seed,purpose)==("H",0,"registered"):continue
            key=arm+str(seed)+("-repeat" if purpose=="repeat" else "");output="/outputs/"+key
            def add(path,obj=None,data=None,kind="json"):
                raw=encoded(obj) if data is None else data;self.data[path]=(raw,kind);return {"path":path,"sha256":h(raw)}
            a=add("/inputs/receipts/"+key+".json",{"attempt_id":key+"-first","output":output,"context":context})
            c=add(output+"/model.pt",data=b"synthetic checkpoint",kind="checkpoint")
            d=add(output+"/details.json",{"checkpoint_file":c,"checkpoint_sha256":c["sha256"]})
            row=dict(original,arm=arm,seed=seed,purpose=purpose,attempt_id=key+"-first",output=output,approval_ref=a)
            r=add(output+"/result.json",{"format":"cm3-stage-result-v1","status":"PASS","stage":"fit","arm":arm,"seed":seed,"purpose":purpose,
                     "attempt_id":row["attempt_id"],"context_sha256":row["context_sha256"],"approval":a,"hardware":{"class":"cuda:L40S"},"artifacts":{"details":d}})
            row["result_ref"]=r;self.m["selected"].append(row)
        raw=encoded({"format":"cm3-matrix-verification-v1","status":"PASS","context_sha256":original["context_sha256"],"outputs":[x["result_ref"] for x in self.m["selected"]]})
        self.data["/outputs/verify.json"]=(raw,"json")
        self.m.update(verification_ref={"path":"/outputs/verify.json","sha256":h(raw)},max_files=100,max_bytes=1000000)
        self.refresh()
    def test_full_matrix_and_changed_checkpoint_refused(self):
        self.full_matrix();dest=self.root/"matrix"
        self.assertEqual(collector.collect(self.ref,dest,self.reader)["status"],"MATRIX_VERIFIED")
        verification,rows=collector.load_verified(dest,self.ref);self.assertEqual(len(rows),13)
        (dest/"artifacts/outputs/H0/model.pt").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError,"changed"):collector.load_verified(dest,self.ref)
    def test_matrix_missing_repeat_refused(self):
        self.full_matrix();self.m["selected"]=[r for r in self.m["selected"] if r["purpose"]!="repeat"];self.ref=self.fixture.ref(self.m)
        with self.assertRaisesRegex(ValueError,"matrix"):collector.collect(self.ref,self.root/"matrix",self.reader)
    def test_source_volume_and_input_pin_refused(self):
        self.m["volume_ids"]["inputs"]="vo-other"
        path=self.root/"bad-source.json";path.write_bytes(encoded(self.m))
        with self.assertRaisesRegex(ValueError,"volume"):collector.collect({"local_path":str(path),"sha256":h(path.read_bytes())},self.root/"bad-source",self.reader)
    def test_supervisor_kills_blocked_reader_and_withholds_promotion(self):
        import subprocess
        class Proc:
            pid=123
            def wait(self,timeout=None):
                if timeout is not None:raise subprocess.TimeoutExpired("synthetic",timeout)
                return -9
            def poll(self):return None
        dest=self.root/"blocked"
        with patch.object(collector.subprocess,"Popen",return_value=Proc()),patch.object(collector.os,"killpg") as kill:
            with self.assertRaises(subprocess.TimeoutExpired):collector.supervised_collect(self.ref,dest)
        kill.assert_called_once_with(123,collector.signal.SIGKILL)
        self.assertTrue((dest/"INCOMPLETE.json").exists());self.assertFalse((dest/"collection.json").exists())
    def test_transfer_deadline(self):
        counter=iter((0,1,11,12,13,14))
        with self.assertRaisesRegex(ValueError,"deadline"):collector.collect(self.ref,self.root/"timeout",self.reader,clock=lambda:next(counter))
if __name__=="__main__":unittest.main(verbosity=2)
