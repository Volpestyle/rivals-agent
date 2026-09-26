import sys,json,hashlib,dataclasses
from pathlib import Path
R=Path.cwd();sys.path.insert(0,str(R));from agent import human_intake as hi,human_demos as hd
O=Path(__file__).parent
reg=O/'gate2-reg.json';reg.write_text(json.dumps(dict(schema_version=1,sessions=[dict(session_id='synthetic-gate2',session_group='synthetic-pair',split='gate2',sealed=True,video_path=str(O/'absent.mkv'),recorded_video_path=str(O/'absent.mkv'),expected_media_sha256='1'*64)])))
h=dict(format=hd.FORMAT,**dataclasses.asdict(hd.read_splits(reg)[0]),sealed=False,media_sha256='1'*64,payload_sha256='0'*64)
p=O/'gate2-artifact.jsonl';p.write_text(json.dumps(h)+'\nSYNTHETIC PAYLOAD MUST NOT BE READ\n')
try:hi.load_dataset_relocated(p,splits=reg,denylist={'sessions':[]},relocation={})
except Exception as e:print(type(e).__name__,str(e))
