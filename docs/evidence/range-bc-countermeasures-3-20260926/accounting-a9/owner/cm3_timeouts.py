"""Deterministic per-arm work ceilings and per-task holds; no cloud imports."""
import math
from decimal import Decimal,ROUND_CEILING
ARMS=("A","H","I","W")
FACTOR=1.5
FLOOR_SECONDS=600
H_FLOOR_SECONDS=900
STARTUP_SECONDS=300
STOP_SECONDS=120
OWNER_MARGIN_SECONDS=30
HASH_SECONDS=172
DIAGNOSTICS_SECONDS=60
VERIFICATION_SECONDS=300
def require(ok,message):
 if not ok:raise ValueError(message)
def number(v,name,positive=False):
 require(type(v) in (int,float) and math.isfinite(v) and (v>0 if positive else v>=0),name+" invalid")
 return v
def measured_seconds(smoke):
 measured={}
 for arm in ARMS:
  row=smoke[arm];s=row["smoke"];t=row["timing"]
  require(type(s["updates"]) is int and s["updates"]==32,"not 32-update smoke")
  require(t["dev_scores"] is False,"timing contains dev scores")
  require(type(s["full_schedule_updates"]) is int and s["full_schedule_updates"]>0,"invalid update count")
  value=s["full_schedule_updates"]*number(s["seconds_per_update"],"seconds/update",True)
  value+=13*number(t["per_epoch_dev_loss_seconds"],"dev loss seconds")
  value+=sum(number(t[k],k) for k in ("teacher_seconds","self_seconds","teacher_metric_seconds","self_metric_seconds"))
  measured[arm]=number(value,"measured full workload",True)
 return measured
def work_limits(measured):
 require(set(measured)==set(ARMS),"four arm measurements required")
 out={}
 for a in ARMS:
  raw=number(measured[a],a,True)
  scaled=math.ceil(number(FACTOR*raw,"scaled "+a,True))
  with_allowances=math.ceil(number(raw+HASH_SECONDS+DIAGNOSTICS_SECONDS,"with allowances "+a,True))+OWNER_MARGIN_SECONDS
  out[a]=max(H_FLOOR_SECONDS if a=="H" else FLOOR_SECONDS,scaled,with_allowances)
 return out
def task_arm(task):
 require(task in {f"{a}-{s}" for a in ARMS for s in range(3)}|{"H-repeat-0"},"unregistered task")
 return task[0]
def holds(tasks,limits,rate):
 require(set(limits)==set(ARMS),"four timeouts required")
 number(rate,"rate",True)
 for a in ARMS:require(type(limits[a]) is int and limits[a]>=FLOOR_SECONDS,"integer work timeout below floor")
 out={}
 for task in sorted(tasks):
  arm=task_arm(task);work=limits[arm];total=work+STARTUP_SECONDS+STOP_SECONDS
  out[task]=dict(work_seconds=work,owner_stage_seconds=work-OWNER_MARGIN_SECONDS,
   startup_seconds=STARTUP_SECONDS,cleanup_seconds=STOP_SECONDS,total_seconds=total,
   resource_rate_usd_second=rate)
 return out

def hold_usd(hold):
 return float((Decimal(str(hold["total_seconds"]))*Decimal(str(hold["resource_rate_usd_second"]))).quantize(Decimal("0.000001"),rounding=ROUND_CEILING))
