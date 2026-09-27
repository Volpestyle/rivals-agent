"""Offline launch boundaries. External lead SHA pins are the trust roots."""
import hashlib,json,math,pathlib,re,time
from decimal import Decimal
import cm3_accounting as accounting
import cm3_timeouts as timeouts
import cm3_budget_plan as budget_plan
PHASE1=frozenset(budget_plan.PHASE1)
PHASE2=frozenset(budget_plan.PHASE2)
ALL=PHASE1|PHASE2
STARTUP_SECONDS=300
STOP_SECONDS=120
MIN_OVERHEAD_USD=budget_plan.PHASE_OVERHEAD_USD
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
    for key in ("cap_usd","resource_rate_usd_second"):
        number(p[key],key,True)
    for key in ("spent_before_usd","spent_before_compute_seconds","overhead_reserve_usd","startup_shutdown_reserve_seconds"):
        number(p[key],key)
    require(p["cap_usd"]<=50,"cap invalid")
    require("attempt_timeout_seconds" not in p and "expected_fit_seconds" not in p,"uniform timeout/forecast forbidden")
    measured=timeouts.measured_seconds(document(p["smoke_timing"]))
    require(p["expected_fit_seconds_by_arm"]==measured,"smoke timing substitution")
    require(p["attempt_timeout_seconds_by_arm"]==timeouts.work_limits(measured),"per-arm timeout differs from pinned smoke")
    require(p["task_holds"]==timeouts.holds(p["tasks"],p["attempt_timeout_seconds_by_arm"],p["resource_rate_usd_second"]),"task hold substitution")
    require(p["overhead_reserve_usd"]==MIN_OVERHEAD_USD,"phase overhead differs from shared policy")
    require(p["startup_shutdown_reserve_seconds"]>=STARTUP_SECONDS+STOP_SECONDS,"startup/stop reserve below enforced timeouts")
    require(p["attempts_max"]==1,"no automatic retry")
    require(p.get("h0_repeat_required",True) is True,"A3 repeat is mandatory")
    require(p.get("spend_started_at_unix",0)==0 and p.get("absolute_deadline_unix",0)==0,"caller cannot supply runtime clocks")
    require(p["resource_rate_usd_second"]>=MIN_RATE,"understated L40S resource rate")
    require(p["phase"] in ("phase1","phase2"),"unknown phase")
    require(set(p["tasks"])==(PHASE1 if p["phase"]=="phase1" else PHASE2),"wrong A3 matrix")
def verification_reserve_usd(p):
    return float(accounting.usd_up(Decimal(str(budget_plan.VERIFICATION_HOLD_SECONDS))*Decimal(str(p["resource_rate_usd_second"]))+Decimal(str(budget_plan.VERIFY_OVERHEAD_USD))))
def projection(p):
    numeric_plan(p)
    # Final lead rule 83b5b0c6: current phase plus verification300.
    # Phase2 re-admission uses settled phase1 evidence. Full13 is informational.
    current=p["task_holds"]
    all_holds=timeouts.holds(ALL,p["attempt_timeout_seconds_by_arm"],p["resource_rate_usd_second"])
    return {"executions_including_repeat":len(ALL),"admitted_phase":p["phase"],
            "remaining_executions":len(current),"admission_basis":"current phase plus 300-second verification reserve",
            "projected_usd":sum(p["expected_fit_seconds_by_arm"][timeouts.task_arm(k)] for k in ALL)*p["resource_rate_usd_second"],
            "reserved_max_usd":sum(timeouts.hold_usd(r) for r in current.values())+p["overhead_reserve_usd"]+verification_reserve_usd(p),
            "remaining_compute_seconds":sum(r["total_seconds"] for r in current.values())+budget_plan.VERIFICATION_HOLD_SECONDS,
            "fit_compute_seconds":sum(r["total_seconds"] for r in current.values()),
             "verification_reserve_seconds":budget_plan.VERIFICATION_HOLD_SECONDS,
            "verification_overhead_usd":budget_plan.VERIFY_OVERHEAD_USD,
            "contingency_usd_informational":budget_plan.CONTINGENCY_USD,
            "full_matrix_hold_seconds_informational":sum(r["total_seconds"] for r in all_holds.values()),
            "current_task_holds":current}
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
    require(p["campaign_ledger"]["local_path"]==b["campaign_ledger_local_path"],"ledger resolution root not lead bound")
    require(pathlib.Path(p["campaign_ledger"]["local_path"]).is_absolute(),"absolute host ledger reference required")
    if "bootstrap_campaign_directory" in p:
        require(p["bootstrap_campaign_directory"] == b["bootstrap_campaign_directory"], "bootstrap inventory root not bound")
    for key in ("smoke_timing","expected_fit_seconds_by_arm","attempt_timeout_seconds_by_arm","task_holds","overhead_reserve_usd"):
        require(p[key]==b[key],"timeout/hold not lead bound: "+key)
    context=document(p["approved_context"])
    require(canonical(context)==sha(p["context_sha256"])==b["context_sha256"],"context pin mismatch")
    require(context["amendment"]==3 and context["device"]=="cuda" and context["hardware"]["class"]=="cuda:L40S","approved context not L40S")
    require(context["hardware"]==b["hardware"],"hardware closure changed")
    return b
def measured_inventory(p,reservations_dir):
    """Hash every live reservation, then name it in the portable ledger namespace.
    Copies in the evidence bundle never substitute for this live inventory scan.
    """
    campaign_root=pathlib.Path(reservations_dir).parent.parent
    bootstrap=pathlib.Path(p["bootstrap_campaign_directory"])
    require(campaign_root.is_absolute(),"absolute campaign inventory root required")
    require(bootstrap.is_absolute() and bootstrap.is_dir() and not bootstrap.is_symlink(),"bootstrap inventory root missing")
    inventory={}
    for root,pattern in ((campaign_root,"*/reservations/*.json"),(bootstrap,"*/reservation.json")):
        require(not root.is_symlink(),"symlink inventory root")
        require(not root.exists() or root.is_dir(),"inventory root is not directory")
        for path in root.glob(pattern):
            rel=path.relative_to(root)
            child=root
            for part in rel.parts:
                child=child/part
                require(not child.is_symlink(),"symlink actual reservation")
            require(path.is_file(),"actual reservation is not a file")
            row=json.loads(path.read_bytes())
            attempt=row.get("attempt_id",row.get("run_id"))
            require(isinstance(attempt,str) and re.fullmatch(r"[A-Za-z0-9_-]{1,80}",attempt) and attempt not in inventory,"duplicate/invalid actual reservation")
            inventory[attempt]=accounting.reservation_ref(attempt,digest(path))
    return inventory

def ledger(p,reservations_dir):
    data=document(p["campaign_ledger"])
    if data.get("format") == "cm3-measured-accounting-v2":
        require(p["campaign_id"] == data["campaign_id"], "measured campaign mismatch")
        # Called under the existing campaign lock, before a new reservation.
        inventory=measured_inventory(p,reservations_dir)
        def measured_doc(ref):
            return document({"local_path":ref["path"],"sha256":ref["sha256"]})
        ref={"path":p["campaign_ledger"]["local_path"],"sha256":p["campaign_ledger"]["sha256"]}
        totals=accounting.ledger(ref,measured_doc,inventory=inventory)
        require(p["spent_before_usd"] == totals["spent_usd"] and p["spent_before_compute_seconds"] == totals["spent_seconds"], "prior spend differs from measured ledger")
        if p["phase"] == "phase2":
            gate=document({"local_path":p["phase1_gate"]["local_path"],"sha256":p["phase1_gate"]["sha256"]})
            require(set(data["completed_phase1"]) == PHASE1, "phase1 carry-forward incomplete")
            for key,g in {"A-0":"A0","A-1":"A1","A-2":"A2","H-0":"H0","H-repeat-0":"H0_repeat"}.items():
                require(data["completed_phase1"][key] == accounting.output_ref(gate["outputs"][g]), "phase1 selected attempt mismatch")
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
    numeric_plan(p)
    wall=time.time() if wall is None else wall;mono=time.monotonic() if mono is None else mono
    number(wall,"clock",True);number(mono,"monotonic",True)
    total=sum(timeouts.hold_usd(r) for r in p["task_holds"].values())+p["overhead_reserve_usd"]
    verify_reserve=verification_reserve_usd(p)
    require(p["spent_before_usd"]+total+verify_reserve<=p["cap_usd"],"no funded task windows")
    tasks={}
    for key,hold in p["task_holds"].items():
        lifetime=hold["total_seconds"]
        tasks[key]={"started_at_unix":wall,"started_monotonic":mono,
         "stop_at_unix":wall+lifetime-STOP_SECONDS,"stop_monotonic":mono+lifetime-STOP_SECONDS,
         "funded_until_unix":wall+lifetime,"funded_until_monotonic":mono+lifetime,
         "hold":hold}
    return {"started_at_unix":wall,"started_monotonic":mono,"tasks":tasks,
      "stop_at_unix":max(t["stop_at_unix"] for t in tasks.values()),
      "stop_monotonic":max(t["stop_monotonic"] for t in tasks.values()),
      "funded_until_unix":max(t["funded_until_unix"] for t in tasks.values()),
      "all_calls_rate":len(tasks)*p["resource_rate_usd_second"],"rate_usd_second":p["resource_rate_usd_second"],
      "prior_usd":p["spent_before_usd"],"cap_usd":p["cap_usd"]-verify_reserve,"campaign_cap_usd":p["cap_usd"],"verification_reserve_usd":verify_reserve,
      "overhead_usd":p["overhead_reserve_usd"],"stop_headroom_seconds":STOP_SECONDS}
def running_bound(bounds,mono=None,wall=None,completed=None):
    mono=time.monotonic() if mono is None else mono;wall=time.time() if wall is None else wall
    completed={} if completed is None else completed
    require(set(completed)<=set(bounds["tasks"]),"unknown settled task")
    total=0;active=0
    for key,task in bounds["tasks"].items():
        if key in completed:
            elapsed=number(completed[key],"settled duration")
            require(elapsed<=task["hold"]["total_seconds"],"settled task exceeded hold")
        else:
            require(mono<task["stop_monotonic"] and wall<task["stop_at_unix"],"task funded deadline: "+key)
            elapsed=max(0,mono-task["started_monotonic"],wall-task["started_at_unix"]);active+=1
        total+=elapsed
    gross=bounds["prior_usd"]+bounds["overhead_usd"]+total*bounds["rate_usd_second"]
    require(gross+active*STOP_SECONDS*bounds["rate_usd_second"]<=bounds["cap_usd"],"funded spend stop")
    return gross


def fit_budget(p,key,budget):
    """Check exact lead-filled allocation; never rewrite a receipt."""
    hold=p["task_holds"][key]
    overhead=p["overhead_reserve_usd"] if key==min(p["tasks"]) else 0
    for name in ("stage_seconds","hold_seconds","hold_usd","hourly_usd","cap_seconds","cloud_cap_usd"):
        number(budget[name],"fit budget "+name,True)
    for name in ("stage_overhead_usd","spent_seconds","spent_usd"):
        number(budget[name],"fit budget "+name)
    require(budget["stage_seconds"]==hold["owner_stage_seconds"],"owner stage differs from per-arm timeout")
    require(budget["hold_seconds"]==hold["total_seconds"],"owner inclusive hold differs from task")
    require(budget["stage_overhead_usd"]==overhead,"owner overhead allocation mismatch")
    require(budget["hold_usd"]>=timeouts.hold_usd(hold)+overhead,"owner hold dollars underfunded")
    require(budget["hourly_usd"]==p["resource_rate_usd_second"]*3600,"owner resource rate differs")
    require(budget["cap_seconds"]<=57600 and budget["cloud_cap_usd"]==p["cap_usd"],"owner cap differs")
    require(budget["spent_seconds"]==p["spent_before_compute_seconds"] and budget["spent_usd"]==p["spent_before_usd"],"owner prior spend differs")
    require(budget["accounting"]["sha256"]==p["campaign_ledger"]["sha256"],"owner accounting pin differs")
