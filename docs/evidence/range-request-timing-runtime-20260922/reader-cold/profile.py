import sys,time,json,hashlib,statistics
from pathlib import Path
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[3]; sys.path.insert(0,str(ROOT))
import cv2
from perception import hud
NAME=sys.argv[1]
assert NAME in ('000000.jpg','000021.jpg','000041.jpg')
p=ROOT/'data/l1/range-request-timing-20260922-1'/NAME
frame=cv2.imread(str(p)); assert frame.shape==(1440,2560,3)
original={n:getattr(hud,n) for n in ('read_hp','read_cooldown','_mask','_classify','classify','_countdown_in','_countdown_char','_segment','read_charges','_read_ability')}
times=defaultdict(list)
def wrap(n,f):
 def run(*a,**kw):
  t=time.perf_counter()
  try:return f(*a,**kw)
  finally:times[n].append((time.perf_counter()-t)*1000)
 return run
for n,f in original.items():setattr(hud,n,wrap(n,f))
results=[]
for kind in ('cold','same_pixels_warm'):
 times.clear(); seen_before=len(hud._SEEN); t=time.perf_counter(); v=hud.read(frame); elapsed=(time.perf_counter()-t)*1000
 results.append({'kind':kind,'elapsed_ms':elapsed,'seen_before':seen_before,'seen_after':len(hud._SEEN),'subcalls':{n:{'count':len(v),'sum_ms':sum(v)} for n,v in times.items()},'hud':{'hp':v.hp,'max_hp':v.max_hp,'webs':v.webs,'abilities':v.abilities,'cooldowns':v.cooldowns}})
assert results[0]['hud']==results[1]['hud']
assert not any(n in sys.modules for n in ('torch','agent.loop','agent.controller','dxcam','vgamepad'))
report={'scope':'cold_and_repeated_saved_JPEG_function_costs_not_original_native_values_or_stages','file':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'hud_sha256':hashlib.sha256((ROOT/'perception/hud.py').read_bytes()).hexdigest(),'opencv_threads':cv2.getNumThreads(),'results':results,'limits':['Nested function costs overlap; do not sum them as disjoint stages.','JPEG pixels differ from original acquisition.','Wrapped timing adds Python overhead and is not a native live benchmark.']}
with Path(__file__).with_name(NAME+'.json').open('x') as f:json.dump(report,f,indent=2)
print(json.dumps(report))
