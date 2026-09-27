"""Independent driver-death and dollar-derived-deadline guard. Never resubmits a fit."""
import json,pathlib,sys,time
from lifecycle import atomic,cleanup,guard_reason
import job_status,os
def watch(local):
    local=pathlib.Path(local)
    name="cm3-guard-"+local.name
    def report(stage,progress):
        job_status.write(name,owner="modal-port",host="modal",stage=stage,progress=progress,
                         eta=None,evidence=str((local/"inventory.json").resolve()))
    report("running","Monitoring funded deadline and driver liveness")
    last_report=time.monotonic()
    atomic(local/"guard-ready.json",{"ready":True})
    while True:
        inv=json.loads((local/"inventory.json").read_bytes())
        prior=local/"cleanup.json"
        if prior.exists() and json.loads(prior.read_bytes())["status"]=="TERMINAL":
            report("done","Owned apps verified terminal");return
        reason=guard_reason(inv)
        if reason:
            atomic(local/"guard-trigger.json",{"reason":reason})
            result=cleanup(local)
            report("failed",reason+"; cleanup "+result["status"])
            if reason=="driver death":
                job_status.write("cm3-"+local.name,owner="modal-port",host="modal",stage="failed",
                                 progress="Driver died; cleanup "+result["status"],eta=None,
                                 evidence=str((local/"cleanup.json").resolve()))
            if result["status"]!="TERMINAL":raise SystemExit("INCOMPLETE_CLEANUP: manual reconciliation required; paid work stays disabled")
            return
        if time.monotonic()-last_report>=30:
            report("running","Monitoring funded deadline and driver liveness");last_report=time.monotonic()
        time.sleep(1)
if __name__=="__main__":watch(sys.argv[1])
