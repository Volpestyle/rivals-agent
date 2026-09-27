"""One approved fit in one independently owned app. Never retries or promotes science."""
import json,pathlib,sys,time,os
import lifecycle
from safety import require,digest,numeric_plan,validate_binding,canonical
ROOT=pathlib.Path(__file__).resolve().parent

def execute(local,runtime_ref):
    import modal_app
    require(modal_app.DEPLOYMENT_ENABLED,"DRAFT: paid launch disabled pending independent delta review and lead approval")
    local=pathlib.Path(local)
    require(digest(runtime_ref["path"])==runtime_ref["sha256"],"runtime pin mismatch")
    runtime=json.loads(pathlib.Path(runtime_ref["path"]).read_bytes())
    inv=json.loads((local/"inventory.json").read_bytes())
    key=inv["task"];p=runtime["plan"];bound=inv["bounds"]
    # Each fresh local process rechecks approved routing and source bytes before
    # connection/app construction. Parent alone owns campaign admission under lock.
    numeric_plan(p)
    binding=validate_binding(p);modal_app.validate_harness(binding)
    require(binding["tasks"]==p["tasks"] and binding["tasks_sha256"]==canonical(p["tasks"]),"task routing changed")
    require(bound["hold"]==p["task_holds"][key],"task reservation hold changed")
    require(bound["rate_usd_second"]==p["resource_rate_usd_second"],"task rate changed")
    require(bound["overhead_usd"]==(p["overhead_reserve_usd"] if key==min(p["tasks"]) else 0),"overhead allocation changed")
    for start,stop in (("started_at_unix","stop_at_unix"),("started_monotonic","stop_monotonic")):
        require(abs((bound[stop]-bound[start])-(bound["hold"]["total_seconds"]-bound["hold"]["cleanup_seconds"]))<.000001,
                "task deadline extended")
    require(runtime["phase_directory"]==str(local.parent.resolve()),"task directory mismatch")
    require(inv["attempt_id"]==p["tasks"][key]["attempt_receipts"][0]["attempt_id"],"attempt binding")
    lifecycle.update_inventory(local,lambda x:x.update(driver_pid=os.getpid()))
    worker=None;failure=None
    try:
        client,identity=lifecycle.connect_verified(inv["identity"])
        def funded():
            current=json.loads((local/"inventory.json").read_bytes())
            require(lifecycle.guard_reason(current) is None,"task deadline or supervisor death")
            require(not (local/"guard-trigger.json").exists(),"task watchdog triggered")
            require(lifecycle.driver_alive(json.loads((local/"guard-pid.json").read_bytes())["pid"]),"task watchdog died")
        funded()
        task_plan=dict(p,absolute_deadline_unix=bound["stop_at_unix"],verified_identity=identity,
                       owned_app_name=inv["app_name"],selected_task=key)
        app,function=modal_app.build_app(task_plan,identity,client,key)
        import modal
        # Journal intent immediately before the possible external side effect.
        funded()
        lifecycle.update_inventory(local,lambda x:x.update(creation_started=True))
        with modal.enable_output(),app.run(client=client):
            lifecycle.update_inventory(local,lambda x:x.update(apps=[app.app_id],creation_finished=True))
            funded()
            arm,seed=key.rsplit("-",1)
            call=function.spawn(arm.split("-")[0],int(seed),"repeat" if arm=="H-repeat" else "registered",task_plan)
            lifecycle.update_inventory(local,lambda x:x["calls"].update({key:call.object_id}))
            while True:
                funded()
                try:worker=call.get(timeout=0);break
                except TimeoutError:time.sleep(.25)
            lifecycle.atomic(local/"worker.json",worker)
            require(worker.get("exit")==0 and worker.get("status")=="COMPLETE","fit incomplete; no retry")
    except BaseException as exc:
        failure=str(exc)
    finally:
        result=lifecycle.finish_task(local,worker,reason=failure)
    require(result["status"]=="COMPLETE" and result["teardown"]["status"]=="TERMINAL" and not result["over_hold"],
            "incomplete fit/cleanup or exceeded hold; no retry")
    return result

if __name__=="__main__":
    execute(sys.argv[1],{"path":sys.argv[2],"sha256":sys.argv[3]})
