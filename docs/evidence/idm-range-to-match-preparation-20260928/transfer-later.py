"""Serial immutable relocation; current admission rechecked before each session."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).parent/'transfer-code'))
from policy.idm import match_targets as M
from policy import idm_targets as T
import relocate_later as R
base=Path(__file__).parent
pins=json.loads((base/'transfer-code/origin.json').read_bytes())['files']
for name,pin in pins.items():
    assert hashlib.sha256((base/'transfer-code'/name).read_bytes()).hexdigest()==pin
identity=R.remote("import json,getpass,platform; print(json.dumps([getpass.getuser(),platform.system(),platform.machine()]))")
assert identity==['james','Darwin','arm64'],identity
receipts=[]
for sid,(_,rel,pin) in R.ALLOWED.items():
    M.load(ROOT/rel,pin,registry=T.REGISTRY,denylist=T.load_denylist())
    out=base/'relocations'/sid;out.mkdir(parents=True,exist_ok=False)
    receipt=out/'relocation.json'
    sys.argv=['relocate_later.py',sid,str(receipt)]
    R.main()
    receipts.append({'session_id':sid,'path':str(receipt),'sha256':R.sha(receipt)})
(base/'relocations-complete.json').write_text(json.dumps(receipts,indent=2)+'\n')
