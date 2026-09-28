import sys,json,hashlib,time,os
from pathlib import Path
os.nice(10)
sys.path.insert(0,"/Users/james/dev/range-bc-data/explore/nitrogen-spatial-yaw-20260927/guard-integration/probe-03/code")
from cloud.modal_guard.provider import connect
from cloud.modal_guard import release
from cloud.modal_guard.common import DEFAULT_ROOT
client=connect()
release.reviewed(DEFAULT_ROOT,"5c0e979227738363bfceaef792d9852d2578fcc149f77d2f9cde61510dc8a8fd")
import modal
name="rivals-yaw-extract-20260927-01-outputs"
try:
 v=modal.Volume.from_name(name,create_if_missing=False);v.hydrate(client=client)
except modal.exception.NotFoundError:
 pass
else:
 raise RuntimeError("fresh extraction volume already exists")
base=Path("/Users/james/dev/range-bc-data/explore")
assets=[(base/"encoder-historyoff-20260927/nitrogen/collected/assets/vision.safetensors","/assets/vision.safetensors","2fceee7b828e737e459b39aa5d11e01362ce38210033f6f885b9974d7a0d6e79"),(base/"encoder-inference-handoff-20260927/config.json","/assets/config.json","172e39dbf0143b8fe22d2f08921730eb8c397967e58cb37d133161e28aa34104")]
checkpoint=["9f3dfd1a9a2edb1c280f0a2a86a18cb34cfe2a7ce172931823ababca41eebf24","99f17cd5e105a96dc1b89face1145ec037606c329cc7a2710c081f4dc7c495b7","b52c3aef493118b8275bc8f291719b54efaae16d9e4d45caea0313aea6aa6c51"]
cutoffs=["1399b086450478335e9c9b63bb4d99d8cc028f0705ebaab6ba90211a5f9b783c","cacc25bbadf15e146cfef36a485d1c69783af36be639914ebfc8fa755b1e59a1","89e0f132bcac4052301381e907410d87045b0f7c066c66252c057cffb5a320fb"]
for s in range(1,4):
 for f,pin in [("epoch-26.pt",checkpoint[s-1]),("evaluation.json",cutoffs[s-1])]:
  assets.append((base/f"nitrogen-nohistory-confirm-20260927/evaluation-recovery/candidate-s{s}/{f}",f"/assets/candidate-s{s}/{f}",pin))
rows=[]
for path,dest,pin in assets:
 with path.open("rb") as stream: actual=hashlib.file_digest(stream,"sha256").hexdigest()
 assert actual==pin,(str(path),actual)
 rows.append({"source":str(path),"remote":dest,"bytes":path.stat().st_size,"sha256":pin})
v=modal.Volume.from_name(name,create_if_missing=True);v.hydrate(client=client)
receipt={"name":name,"id":v.object_id,"created_at":time.time(),"files":rows,"profile":"rivals","workspace":"volpestyle"}
root=base/"nitrogen-spatial-yaw-20260927/cloud-extraction-01"
root.mkdir(exist_ok=False)
(root/"volume-created.json").write_text(json.dumps(receipt,indent=2))
print("CREATED",v.object_id,flush=True)
with v.batch_upload() as batch:
 for path,dest,pin in assets: batch.put_file(str(path),dest)
receipt["upload_completed_at"]=time.time()
(root/"assets-uploaded.json").write_text(json.dumps(receipt,indent=2))
print("UPLOAD COMPLETE",json.dumps(receipt),flush=True)
