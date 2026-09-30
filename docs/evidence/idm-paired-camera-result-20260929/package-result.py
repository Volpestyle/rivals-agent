"""Archive compact outputs and hash this run's retained D: artifacts only."""
import ctypes
import hashlib
import json
import shutil
import sys
from pathlib import Path
sys.dont_write_bytecode=True
OUT=Path('D:/rivals-agent-evidence/idm-paired-camera-development-20260929')
PACKET=Path(__file__).resolve().parent

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def main():
    k=ctypes.WinDLL('kernel32');k.GetCurrentProcess.restype=ctypes.c_void_p
    k.SetPriorityClass.argtypes=(ctypes.c_void_p,ctypes.c_ulong)
    assert k.SetPriorityClass(k.GetCurrentProcess(),0x4000)
    files=[p for p in OUT.iterdir() if p.is_file()]
    collection={'designation':'provisional, unadmitted development evidence',
                'root':str(OUT),'file_count':len(files),'total_bytes':sum(p.stat().st_size for p in files),
                'files':{p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in files}}
    with (OUT/'collection.json').open('x',encoding='utf-8') as f:json.dump(collection,f,indent=2)
    names=('agreement.json','summary.json','comparison.csv','comparison.svg','absolute-disagreement.svg',
           'absolute-disagreement.png','prepared.json','timing-qc.json','review.json','review-v2.json',
           'context-contacts.json','fine-context.json','fine-context.png','collection.json')
    for name in names:
        target=PACKET/name
        assert not target.exists()
        shutil.copyfile(OUT/name,target)
        assert sha(target)==sha(OUT/name)
    print(f'Archived {len(names)} compact artifacts; {len(files)} retained files hashed on D:. No raw stores copied.')

if __name__=='__main__':main()
