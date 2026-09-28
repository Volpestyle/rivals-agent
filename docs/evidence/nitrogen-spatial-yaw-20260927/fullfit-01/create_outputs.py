import sys,json,os,time
from pathlib import Path
os.nice(10)
sys.path.insert(0,"/Users/james/dev/range-bc-data/explore/nitrogen-spatial-yaw-20260927/guard-integration/extract-02/code")
from cloud.modal_guard.provider import connect
client=connect()
import modal
attempts=[f"yaw-fit-grid{g}-s{s}-20260927-01" for g in (4,8) for s in (1,2,3)]
for attempt in attempts:
 try:
  v=modal.Volume.from_name("rivals-"+attempt+"-outputs",create_if_missing=False);v.hydrate(client=client)
 except modal.exception.NotFoundError:pass
 else:raise RuntimeError("nonfresh output: "+attempt)
root=Path("/Users/james/dev/range-bc-data/explore/nitrogen-spatial-yaw-20260927/fullfit-01")
root.mkdir(exist_ok=False)
bindings={}
for attempt in attempts:
 v=modal.Volume.from_name("rivals-"+attempt+"-outputs",create_if_missing=True);v.hydrate(client=client)
 bindings[attempt]=v.object_id
 (root/(attempt+"-volume.json")).write_text(json.dumps({"attempt_id":attempt,"output_volume":"rivals-"+attempt+"-outputs","id":v.object_id,"created_at":time.time()}))
(root/"bindings.json").write_text(json.dumps(bindings,indent=2))
print(json.dumps(bindings))
