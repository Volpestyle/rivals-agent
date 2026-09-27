"""Identity-locked ownership journal and bounded, idempotent cleanup; no fit retries."""
import cm3_timeouts as timeouts
import contextlib,fcntl,json,os,pathlib,re,subprocess,sys,time,uuid
from safety import require,ledger,clock_bound,STARTUP_SECONDS,STOP_SECONDS
OVERRIDES=("MODAL_TOKEN_ID","MODAL_TOKEN_SECRET","MODAL_OAUTH_REFRESH_TOKEN","MODAL_OAUTH_CLIENT_ID","MODAL_OAUTH_CLIENT_SECRET","MODAL_CONFIG_PATH","MODAL_SERVER_URL","MODAL_ENVIRONMENT")
MODAL="/Users/james/.local/bin/modal"
def selected_environment():
    env=dict(os.environ);env["MODAL_PROFILE"]="rivals"
    # Explicit profile credentials, never inherited token overrides. Never log credentials.
    for key in OVERRIDES:env.pop(key,None)
    return env
def select_environment():
    os.environ["MODAL_PROFILE"]="rivals"
    for key in OVERRIDES:os.environ.pop(key,None)
def connect_verified(expected):
    select_environment()
    import modal
    import modal.config,modal.client
    require(modal.client._Client._client_from_env is None,"identity connection requires a fresh SDK client process")
    require("rivals" in modal.config.config_profiles(),"rivals profile missing")
    modal.config._set_profile("rivals") # in-memory selection; never rewrites user config
    require(modal.config._profile=="rivals","SDK profile selection failed")
    client=modal.Client.from_env()
    return client,verify_client(client,expected)
def verify_client(client,expected):
    from modal._utils.async_utils import synchronizer
    from modal_proto import api_pb2
    @synchronizer.create_blocking
    async def inspect(client):
        response=await client.stub.TokenInfoGet(api_pb2.TokenInfoGetRequest())
        return {"profile":"rivals","workspace":response.workspace_name,"workspace_id":response.workspace_id}
    identity=inspect(client)
    require(identity==expected,"authenticated Modal identity differs from authorized workspace")
    return identity
def atomic(path,data):
    path=pathlib.Path(path);tmp=path.with_name(path.name+"."+uuid.uuid4().hex+".tmp")
    with tmp.open("x") as f:
        json.dump(data,f,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
    tmp.replace(path)
@contextlib.contextmanager
def locked(path):
    with pathlib.Path(path).open("a") as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        try:yield
        finally:fcntl.flock(f,fcntl.LOCK_UN)
def update_inventory(local,change):
    local=pathlib.Path(local)
    with locked(local/"inventory.lock"):
        path=local/"inventory.json";value=json.loads(path.read_bytes());change(value);atomic(path,value)
    return value
def reserve(p,state_root,identity):
    campaign=pathlib.Path(state_root)/p["campaign_id"];campaign.mkdir(parents=True,exist_ok=True)
    reservations=campaign/"reservations";reservations.mkdir(exist_ok=True)
    with locked(campaign/"campaign.lock"):
        ledger(p,reservations)
        allocations={k:v["attempt_receipts"][0] for k,v in p["tasks"].items()}
        ids=[a["attempt_id"] for a in allocations.values()]
        require(len(set(ids))==len(ids) and all(re.fullmatch(r"[A-Za-z0-9_-]{1,80}",a) for a in ids),"invalid/duplicate attempt ID")
        require(all(not (reservations/(a+".json")).exists() for a in ids),"attempt already reserved")
        local=campaign/p["run_id"];local.mkdir(exist_ok=False)
        bound=clock_bound(p)
        # Every slot is funded and journaled before any app may be created.
        refs={}
        for key in sorted(allocations):
            allocation=allocations[key];attempt=allocation["attempt_id"]
            task_local=local/key;task_local.mkdir()
            overhead=p["overhead_reserve_usd"] if key==min(allocations) else 0
            task_bound=dict(bound["tasks"][key],rate_usd_second=p["resource_rate_usd_second"],overhead_usd=overhead)
            hold=p["task_holds"][key]
            reservation={"format":"cm3-task-reservation-v1","campaign_id":p["campaign_id"],
                "run_id":attempt,"attempt_id":attempt,"phase_run_id":p["run_id"],"task":key,"phase":p["phase"],
                "ledger_sha256":p["campaign_ledger"]["sha256"],"concurrent_slots":1,
                "attempt_receipt":allocation,"reserved_usd":timeouts.hold_usd(hold)+overhead,
                "reserved_compute_seconds":hold["total_seconds"],"bounds":task_bound}
            path=reservations/(attempt+".json")
            with path.open("x") as f:
                json.dump(reservation,f,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
            from safety import digest
            ref={"path":str(path.resolve()),"sha256":digest(path)}
            refs[key]=ref
            atomic(task_local/"inventory.json",{"format":"cm3-owned-inventory-v1","identity":identity,
                "app_name":"rivals-cm3-"+attempt+"-"+uuid.uuid4().hex[:12],"task":key,"attempt_id":attempt,
                "reservation":ref,"apps":[],"calls":{},"creation_started":False,"creation_finished":False,
                "driver_pid":os.getpid(),"supervisor_pid":os.getpid(),"bounds":task_bound})
        atomic(local/"phase.json",{"format":"cm3-phase-inventory-v1","identity":identity,"reservations":refs,
                                   "bounds":bound,"separately_charged":False})
    return local,bound
class Backend:
    def __init__(self,identity):self.expected=identity
    def run(self,args,timeout):
        p=subprocess.run(args,env=selected_environment(),capture_output=True,text=True,timeout=timeout)
        require(p.returncode==0,"Modal command failed: "+p.stderr[-1000:])
        return p.stdout
    def identity(self,timeout):
        output=self.run([sys.executable,str(pathlib.Path(__file__).with_name("identity_probe.py")),json.dumps(self.expected)],timeout)
        return json.loads(output)
    def apps(self,timeout):return json.loads(self.run([MODAL,"app","list","--profile","rivals","--json"],timeout))
    def containers(self,timeout):return json.loads(self.run([MODAL,"container","list","--profile","rivals","--json"],timeout))
    def stop(self,app_id,timeout):self.run([MODAL,"app","stop",app_id,"--profile","rivals","--yes"],timeout)
    def cancel(self,call_id,timeout):
        self.run([sys.executable,"-c","import modal,sys; modal.FunctionCall.from_id(sys.argv[1]).cancel(terminate_containers=True)",call_id],timeout)
def cleanup(local,backend=None,clock=time.monotonic,pause=time.sleep,budget_seconds=STOP_SECONDS):
    local=pathlib.Path(local);inv=json.loads((local/"inventory.json").read_bytes())
    backend=backend or Backend(inv["identity"]);events=[];end=clock()+budget_seconds
    def invoke(kind,arg=None):
        remain=end-clock();require(remain>0,"cleanup time bound exhausted")
        method=getattr(backend,kind);timeout=min(5,remain)
        return method(timeout) if arg is None else method(arg,timeout)
    terminal=False
    try:
        require(invoke("identity")==inv["identity"],"cleanup identity mismatch")
        for round_ in range(3):
            try:
                apps=invoke("apps");containers=invoke("containers")
                # Recover an app created just before the driver died, before it could journal its ID.
                discovered={a["app_id"] for a in apps if a["description"]==inv["app_name"]}
                inv=update_inventory(local,lambda x:x.update(apps=sorted(set(x["apps"])|discovered)))
                owned=set(inv["apps"]);states={a["app_id"]:a for a in apps}
                terminal=(not inv.get("creation_started") or inv.get("creation_finished") or bool(owned)) and all(a in states and states[a]["state"]=="stopped" and int(states[a]["tasks"])==0 for a in owned) and not any(c["app_id"] in owned for c in containers)
                if terminal:
                    events.append({"round":round_,"terminal_apps":sorted(owned),"containers":0});break
                for call in sorted(set(inv["calls"].values())):
                    try:invoke("cancel",call)
                    except Exception as exc:events.append({"call":call,"cancel_error":str(exc)})
                for app in sorted(owned):
                    try:invoke("stop",app)
                    except Exception as exc:events.append({"app":app,"stop_error":str(exc)})
                pause(min(1,max(0,end-clock())))
            except Exception as exc:events.append({"round":round_,"inspection_error":str(exc)})
        # Always inspect after last stop as well.
        if not terminal:
            apps=invoke("apps");containers=invoke("containers");states={a["app_id"]:a for a in apps}
            terminal=(not inv.get("creation_started") or inv.get("creation_finished") or bool(inv["apps"])) and all(a in states and states[a]["state"]=="stopped" and int(states[a]["tasks"])==0 for a in inv["apps"]) and not any(c["app_id"] in inv["apps"] for c in containers)
    except Exception as exc:events.append({"fatal":str(exc)})
    if terminal and not any(e.get("terminal_apps")==sorted(inv["apps"]) and e.get("containers")==0 for e in events):
        events.append({"terminal_apps":sorted(inv["apps"]),"containers":0,"final_inspection":True})
    result={"status":"TERMINAL" if terminal else "INCOMPLETE_CLEANUP","identity":inv["identity"],
            "apps":inv["apps"],"events":events,"checked_at_unix":time.time()}
    atomic(local/"cleanup.json",result)
    return result
def driver_alive(pid):
    try:os.kill(pid,0);return True
    except ProcessLookupError:return False
def guard_reason(inv,alive=driver_alive,wall=time.time,mono=time.monotonic):
    if wall()>=inv["bounds"]["stop_at_unix"] or mono()>=inv["bounds"]["stop_monotonic"]:return "funded deadline"
    if not alive(inv["driver_pid"]) or not alive(inv.get("supervisor_pid",inv["driver_pid"])):return "driver death"
    return None


def finish_task(local,worker=None,reason=None,backend=None,wall=time.time,mono=time.monotonic):
    """One immutable accounting result, only after independently verified teardown.
    Absent apps or unknown teardown retain the full hold; they never settle as zero.
    Scientific PASS remains owned by cm3_run, never by this wrapper.
    """
    from safety import digest
    local=pathlib.Path(local)
    with locked(local/"finalize.lock"):
        path=local/"wrapper-result.json"
        if path.exists():return json.loads(path.read_bytes())
        inv=json.loads((local/"inventory.json").read_bytes())
        status=cleanup(local,backend=backend)
        bound=inv["bounds"]
        seconds=max(0,wall()-bound["started_at_unix"],mono()-bound["started_monotonic"])
        worker=worker or {}
        complete=worker.get("exit")==0 and worker.get("status")=="COMPLETE" and bool(worker.get("result"))
        measurable=status["status"]=="TERMINAL" and bool(status["apps"]) and seconds>0
        result={"format":"cm3-inputs-wrapper-result-v1","attempt_id":inv["attempt_id"],"task":inv["task"],
            "status":"COMPLETE" if complete and measurable else "INCOMPLETE",
            "owner_result":worker.get("result") if complete else None,"worker":worker,
            "reason":reason,"reservation":inv["reservation"],"teardown":status,
            "creation_started":inv["creation_started"],"hold_released":False,
            "measured_settlement_eligible":measurable,
            "spend":{"seconds_through_cleanup":seconds,
                     "estimated_conservative_usd":bound["overhead_usd"]+seconds*bound["rate_usd_second"]},
            "over_hold":seconds>bound["hold"]["total_seconds"],
            "artifacts_collected":False}
        atomic(path,result)
        return result
