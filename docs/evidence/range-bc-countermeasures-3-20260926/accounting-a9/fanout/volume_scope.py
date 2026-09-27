"""Read-only volume-isolation admission using authenticated Modal app dependency layouts."""
import asyncio,hashlib,json,time
def require(value,message):
 if not value:raise ValueError(message)
def layout_summary(layout):
 # SDK 1.5.5 _functions._deps includes every explicit Volume mount, and
 # Function.object_dependencies sends those IDs to the server AppLayout closure.
 ids=[o.object_id for o in layout.objects]
 functions=dict(layout.function_ids);classes=dict(layout.class_ids)
 require(functions and ids,"mounts unknown: empty app/function layout")
 require(all(isinstance(i,str) and i for i in ids),"mounts unknown: malformed object ID")
 require(set(functions.values())<=set(ids),"mounts unknown: missing function objects")
 require(set(classes.values())<=set(ids),"mounts unknown: missing class objects")
 require(not any(i.startswith("sb-") for i in ids),"mounts unknown: sandbox layout")
 for obj in layout.objects:
  if obj.object_id.startswith("fu-"):
   require(obj.HasField("function_handle_metadata"),"mounts unknown: missing function metadata")
   target=obj.function_handle_metadata.use_function_id
   require(not target or target in ids,"mounts unknown: unresolved routed function")
 volumes=sorted({i for i in ids if i.startswith("vo-")})
 require(volumes,"mounts unknown: no explicit volume dependency evidence")
 value=dict(functions=functions,classes=classes,object_ids=sorted(set(ids)),volume_ids=volumes)
 value["layout_sha256"]=hashlib.sha256(layout.SerializeToString(deterministic=True)).hexdigest()
 return value
def snapshot(apps,containers,owned=()):
 owned=set(owned);by_id={a["app_id"]:a for a in apps}
 require(len(by_id)==len(apps),"duplicate app inventory")
 active={a["app_id"] for a in apps if a["state"]!="stopped" or int(a["tasks"])!=0}
 active.update(c["app_id"] for c in containers)
 require(active<=set(by_id),"mounts unknown: container app absent from app inventory")
 return {a:by_id[a] for a in sorted(active-owned)}
def check_scoped(apps,containers,protected,owned,inspect):
 active=snapshot(apps,containers,owned);observed=[]
 require(len(protected)==2 and all(x.startswith("vo-") for x in protected),"invalid protected volumes")
 for app_id,app in active.items():
  evidence=inspect(app_id)
  volumes=evidence.get("volume_ids")
  require(isinstance(volumes,list) and volumes and all(isinstance(x,str) and x.startswith("vo-") for x in volumes),"mounts unknown")
  overlap=set(volumes)&set(protected)
  require(not overlap,"round-3 volume conflict: "+app_id+" "+",".join(sorted(overlap)))
  observed.append(dict(app_id=app_id,description=app["description"],state=app["state"],
    container_ids=sorted(c["container_id"] for c in containers if c["app_id"]==app_id),mount_evidence=evidence))
 return observed
def no_volume_conflicts(client,backend,protected,owned=()):
 from modal._utils.async_utils import synchronizer
 from modal_proto import api_pb2
 @synchronizer.create_blocking
 async def inspect(client,app_id):
  async def read():
   response=await client.stub.AppGetLayout(api_pb2.AppGetLayoutRequest(app_id=app_id))
   require(response.HasField("app_layout"),"mounts unknown: no app layout")
   return layout_summary(response.app_layout)
  first=await asyncio.wait_for(read(),10)
  second=await asyncio.wait_for(read(),10)
  require(first==second,"mounts unknown: app layout changed during inspection")
  return first
 apps=backend.apps(10);containers=backend.containers(10)
 observed=check_scoped(apps,containers,protected,owned,lambda app_id:inspect(client,app_id))
 after_apps=backend.apps(10);after_containers=backend.containers(10)
 require(snapshot(apps,containers,owned)==snapshot(after_apps,after_containers,owned),"active app inventory changed")
 before={(c["app_id"],c["container_id"]) for c in containers if c["app_id"] not in owned}
 after={(c["app_id"],c["container_id"]) for c in after_containers if c["app_id"] not in owned}
 require(before==after,"active container inventory changed")
 return dict(status="PASS",scope="round-3-volume-isolation",protected_volume_ids=sorted(protected),
   co_tenants=observed,apps=[dict(app_id=a["app_id"],state=a["state"]) for a in apps],
   containers=containers,checked_at_unix=time.time())
