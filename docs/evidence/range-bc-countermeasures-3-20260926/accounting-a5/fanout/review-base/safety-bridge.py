"""Offline launch boundaries. External lead SHA pins are the trust roots."""
import hashlib,json,math,pathlib,re,time
import cm3_accounting as accounting
PHASE1=frozenset(("A-0","A-1","A-2","H-0","H-repeat-0"))
PHASE2=frozenset(("H-1","H-2","I-0","I-1","I-2","W-0","W-1","W-2"))
ALL=PHASE1|PHASE2
STARTUP_SECONDS=300
STOP_SECONDS=120
MIN_OVERHEAD_USD=.75
MIN_RATE=.000542+8*.0000131+32*.00000222
def require(ok,message):
    if not ok:raise ValueError(message)
def number(x,name,positive=False):
    require(type(x) in (int,float) and math.isfinite(x) and (x>0 if positive else x>=0),name+" must be finite and "+("positive" if positive else "nonnegative"))
    return x
def sha(x):
    require(isinstance(x,str) and re.fullmatch("[0-9a-f]{64}",x) is not None,"invalid SHA256")
    return x
def digest(path):
    h=hashlib.sha256()
    with pathlib.Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b""):h.update(chunk)
    return h.hexdigest()
def document(ref):
    require(set(ref)=={"local_path","sha256"},"exact external local reference required")
    require(digest(ref["local_path"])==sha(ref["sha256"]),"external pin mismatch")
    return json.loads(pathlib.Path(ref["local_path"]).read_bytes(),parse_constant=lambda _:(_ for _ in ()).throw(ValueError("nonfinite JSON")))
def canonical(doc):
    return hashlib.sha256(json.dumps(doc,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def relative(path):
    require(isinstance(path,str) and path and "\\" not in path,"invalid relative path")
    p=pathlib.PurePosixPath(path)
    require(not p.is_absolute() and ".." not in p.parts and str(p)==path,"noncanonical/traversal path")
    return p
def remote_path(path):
    require(isinstance(path,str) and "\\" not in path,"invalid remote path")
    p=pathlib.PurePosixPath(path)
    require(p.is_absolute() and ".." not in p.parts and str(p)==path and len(p.parts)>2 and p.parts[1] in ("inputs","outputs"),"remote reference outside approved mounts")
    return p
def numeric_plan(p):
    for key in ("cap_usd","resource_rate_usd_second","attempt_timeout_seconds","expected_fit_seconds"):
        number(p[key],key,True)
    for key in ("spent_before_usd","spent_before_compute_seconds","overhead_reserve_usd","startup_shutdown_reserve_seconds"):
        number(p[key],key)
    require(p["cap_usd"]<=50 and p["attempt_timeout_seconds"]>30,"cap/timeout invalid")
    require(p["overhead_reserve_usd"]>=MIN_OVERHEAD_USD,"insufficient non-GPU overhead reserve")
    require(p["startup_shutdown_reserve_seconds"]>=STARTUP_SECONDS+STOP_SECONDS,"startup/stop reserve below enforced timeouts")
    require(p["attempts_max"]==1,"no automatic retry")
    require(p.get("h0_repeat_required",True) is True,"A3 repeat is mandatory")
    require(p.get("spend_started_at_unix",0)==0 and p.get("absolute_deadline_unix",0)==0,"caller cannot supply runtime clocks")
    require(p["resource_rate_usd_second"]>=MIN_RATE,"understated L40S resource rate")
    require(p["phase"] in ("phase1","phase2"),"unknown phase")
    require(set(p["tasks"])==(PHASE1 if p["phase"]=="phase1" else PHASE2),"wrong A3 matrix")
def projection(p):
    numeric_plan(p)
    remaining=ALL if p["phase"]=="phase1" else PHASE2
    per=p["attempt_timeout_seconds"]+STARTUP_SECONDS+STOP_SECONDS
    return {"executions_including_repeat":len(ALL),"remaining_executions":len(remaining),
            "projected_usd":len(ALL)*p["expected_fit_seconds"]*p["resource_rate_usd_second"],
            "reserved_max_usd":len(remaining)*per*p["resource_rate_usd_second"]+p["overhead_reserve_usd"],
            "remaining_compute_seconds":len(remaining)*per}
def validate_binding(p):
    b=document(p["launch_binding"])
    require(b["format"]=="cm3-modal-launch-binding-v1" and b["approved_by"]=="herdr-lead","missing lead launch binding")
    require(b["campaign_id"]==p["campaign_id"] and b["profile"]=="rivals" and b["workspace"]=="volpestyle","campaign/account binding")
    require(isinstance(b["workspace_id"],str) and b["workspace_id"],"workspace ID missing")
    require(p["gpu"]==b["gpu"]=="L40S" and p["device_class"]==b["judge_model"]==b["judge_instance"]=="modal:L40S","only lead-selected L40S allowed")
    require(p["benchmark_provider"]==b["benchmark_provider"]=="modal" and b["runner_class"]=="cuda:L40S","provider/runner class")
    require(p["cpu"]==b["cpu"]==8 and p["memory_mib"]==b["memory_mib"]==32768,"selected resource allocation")
    require(p["resource_rate_usd_second"]==b["resource_rate_usd_second"],"rate not approved")
    for key in ("context_sha256","entrypoint_sha256","reviewed_image_digest","code_directory","input_volume_id","output_volume_id","reviewed_input_volume","output_volume"):
        require(p[key]==b[key],"changed launch binding: "+key)
    for key in ("input_volume_id","output_volume_id"):
        require(isinstance(p[key],str) and p[key].startswith("vo-"),"volume ID missing")
    for key in ("reviewed_input_volume","output_volume"):
        require(isinstance(p[key],str) and p[key],"volume name missing")
    require(p["input_volume_id"]!=p["output_volume_id"],"input/output volumes must be distinct")
    require(p["input_manifest"]["sha256"]==b["input_manifest_sha256"],"manifest not lead bound")
    require(p["campaign_ledger"]["sha256"]==b["campaign_ledger_sha256"],"ledger not lead bound")
    if "bootstrap_campaign_directory" in p:
        require(p["bootstrap_campaign_directory"] == b["bootstrap_campaign_directory"], "bootstrap inventory root not bound")
    context=document(p["approved_context"])
    require(canonical(context)==sha(p["context_sha256"])==b["context_sha256"],"context pin mismatch")
    require(context["amendment"]==3 and context["device"]=="cuda" and context["hardware"]["class"]=="cuda:L40S","approved context not L40S")
    require(context["hardware"]==b["hardware"],"hardware closure changed")
    return b
def ledger(p,reservations_dir):
    data=document(p["campaign_ledger"])
    if data.get("format") == "cm3-measured-accounting-v1":
        require(p["campaign_id"] == data["campaign_id"], "measured campaign mismatch")
        # Called under the existing campaign lock, before a new reservation.
        root=pathlib.Path(reservations_dir).parent.parent
        bootstrap=pathlib.Path(p["bootstrap_campaign_directory"])
        require(bootstrap.is_absolute() and bootstrap.is_dir() and not bootstrap.is_symlink(), "bootstrap inventory root missing")
        inventory={}
        for path in list(root.glob("*/reservations/*.json"))+list(bootstrap.glob("*/reservation.json")):
            row=json.loads(path.read_bytes())
            attempt=row.get("attempt_id",row.get("run_id"))
            require(attempt and attempt not in inventory, "duplicate actual reservation")
            inventory[attempt]={"path":str(path),"sha256":digest(path)}
        def measured_doc(ref):
            return document({"local_path":ref["path"],"sha256":ref["sha256"]})
        ref={"path":p["campaign_ledger"]["local_path"],"sha256":p["campaign_ledger"]["sha256"]}
        totals=accounting.ledger(ref,measured_doc,inventory=inventory)
        require(p["spent_before_usd"] == totals["spent_usd"] and p["spent_before_compute_seconds"] == totals["spent_seconds"], "prior spend differs from measured ledger")
        if p["phase"] == "phase2":
            gate=document({"local_path":p["phase1_gate"]["local_path"],"sha256":p["phase1_gate"]["sha256"]})
            require(set(data["completed_phase1"]) == PHASE1, "phase1 carry-forward incomplete")
            for key,g in {"A-0":"A0","A-1":"A1","A-2":"A2","H-0":"H0","H-repeat-0":"H0_repeat"}.items():
                require(data["completed_phase1"][key] == gate["outputs"][g], "phase1 selected attempt mismatch")
            accounting.ledger(ref,measured_doc,required_results=data["completed_phase1"].values())
        out=projection(p)
        require(totals["spent_usd"]+out["reserved_max_usd"] <= p["cap_usd"], "campaign dollar reservation exceeds cap")
        require(totals["spent_seconds"]+out["remaining_compute_seconds"] <= 57600, "campaign aggregate compute exceeds 16 hours")
        return data
    require(data["format"]=="cm3-campaign-ledger-v1" and data["approved_by"]=="herdr-lead","campaign ledger not approved")
    require(data["campaign_id"]==p["campaign_id"] and data["profile"]=="rivals" and data["workspace"]=="volpestyle","wrong campaign ledger")
    require(data["coverage"]=={"phase_a":True,"preflight":True,"failed_attempts":True},"incomplete campaign accounting coverage")
    charges=data["charges"];ids=set();usd=seconds=0
    for row in charges:
        require(row["id"] not in ids,"duplicate charge");ids.add(row["id"])
        require(row["kind"] in ("phase_a","preflight","failed_attempt","run_reservation"),"unknown charge category")
        usd+=number(row["gross_usd"],"gross charge")
        seconds+=number(row["compute_seconds"],"compute charge")
        document(row["evidence"])
    phase_a=[x for x in charges if x["kind"]=="phase_a"]
    require(len(phase_a)==1 and any(x["kind"]=="preflight" for x in charges),"Phase A and preflight accounting mandatory")
    # This immutable benchmark receipt is part of the previously reviewed 113-file packet.
    anchor=pathlib.Path(__file__).with_name("phase-a-spend.json")
    require(phase_a[0]["evidence"]["sha256"]==digest(anchor),"Phase A receipt substituted")
    require(phase_a[0]["gross_usd"]>=json.loads(anchor.read_bytes())["conservative_total_upper_usd"],"Phase A cost omitted")
    # Conservatively charge 4 x 796s successful app allocation, 120s failed
    # GPU allocation and 520s CPU verification. This is a ledger floor, not billing.
    require(phase_a[0]["compute_seconds"]>=3824,"Phase A compute accounting omitted")
    by_id={x["id"]:x for x in charges}
    # Changing a plan's campaign ID must not hide reservations made by this runner.
    prior_root=pathlib.Path(reservations_dir).parent.parent
    for old in prior_root.glob("*/reservations/*.json"):
        reservation=json.loads(old.read_bytes())
        row=by_id.get(reservation["run_id"])
        require(row is not None and row["kind"]=="run_reservation","unsettled prior paid run")
        require(row["evidence"]["sha256"]==digest(old),"prior reservation evidence changed")
        require(row["gross_usd"]>=reservation["reserved_usd"] and row["compute_seconds"]>=reservation["reserved_compute_seconds"],"prior run/failure reservation undercharged")
    require(p["spent_before_usd"]==usd and p["spent_before_compute_seconds"]==seconds,"prior spend differs from ledger")
    if p["phase"]=="phase2":
        gate=document({"local_path":p["phase1_gate"]["local_path"],"sha256":p["phase1_gate"]["sha256"]})
        expected={"A-0":"A0","A-1":"A1","A-2":"A2","H-0":"H0","H-repeat-0":"H0_repeat"}
        require(set(data["completed_phase1"])==PHASE1,"phase1 carry-forward incomplete")
        for key,g in expected.items():require(data["completed_phase1"][key]==gate["outputs"][g],"phase1 ledger selected attempt mismatch")
    out=projection(p)
    require(usd+out["reserved_max_usd"]<=p["cap_usd"],"campaign dollar reservation exceeds cap")
    require(seconds+out["remaining_compute_seconds"]<=57600,"campaign aggregate compute exceeds 16 hours")
    return data
def clock_bound(p,wall=None,mono=None):
    # Must execute and persist before app/image creation; callers cannot set either clock.
    wall=time.time() if wall is None else wall;mono=time.monotonic() if mono is None else mono
    number(wall,"clock",True);number(mono,"monotonic",True)
    n=len(p["tasks"]);rate=n*p["resource_rate_usd_second"]
    dollars=p["cap_usd"]-p["spent_before_usd"]-p["overhead_reserve_usd"]
    lifetime=min(dollars/rate,p["attempt_timeout_seconds"]+STARTUP_SECONDS+STOP_SECONDS)
    require(lifetime>STARTUP_SECONDS+STOP_SECONDS,"no funded execution window")
    stop=wall+lifetime-STOP_SECONDS
    return {"started_at_unix":wall,"started_monotonic":mono,"stop_at_unix":stop,
            "stop_monotonic":mono+lifetime-STOP_SECONDS,"funded_until_unix":wall+lifetime,
            "all_calls_rate":rate,"prior_usd":p["spent_before_usd"],"cap_usd":p["cap_usd"],
            "overhead_usd":p["overhead_reserve_usd"],"stop_headroom_seconds":STOP_SECONDS}
def running_bound(bounds,mono=None,wall=None):
    mono=time.monotonic() if mono is None else mono;wall=time.time() if wall is None else wall
    elapsed=max(0,mono-bounds["started_monotonic"],wall-bounds["started_at_unix"])
    gross=bounds["prior_usd"]+bounds["overhead_usd"]+elapsed*bounds["all_calls_rate"]
    require(mono<bounds["stop_monotonic"] and wall<bounds["stop_at_unix"] and gross+STOP_SECONDS*bounds["all_calls_rate"]<=bounds["cap_usd"],"funded spend stop")
    return gross
