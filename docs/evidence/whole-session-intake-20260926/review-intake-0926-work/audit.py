import hashlib,json,sys,importlib.util,subprocess,tempfile
from pathlib import Path
R=Path.cwd(); O=Path(__file__).parent; H=O.parent
sys.path.insert(0,str(R))
from agent import human_intake as hi, human_demos as hd
files=['agent/human_intake.py','agent/human_demos.py','data/human/sessions/intake_session.py','data/human/sessions/assemble_session.py','data/human/sessions/tally.py','tests/test_human_intake.py','tests/test_human_demos.py','tests/test_gate2_split.py','tests/test_human_intake_timed.py','data/human/session-splits.corpus.json','data/human/sessions/tally.json']
pins={p:dict(raw=hashlib.sha256((R/p).read_bytes()).hexdigest(),lf=hashlib.sha256((R/p).read_bytes().replace(b'\r\n',b'\n')).hexdigest()) for p in files}
reg=json.loads((R/files[-2]).read_text()); tally=json.loads((R/files[-1]).read_text())
den=hi.load_denylist(R/'data/human/sealed-denylist.json',sha256_pin='57cfe01f29f6e1a55293f968ec697aa293c268bd87d7cf247ef648279e2fba7c')
placements=hi.check_registry(R/files[-2],denylist=den)
extra={k:v for k,v in reg.items() if isinstance(v,list) and k!='sessions'}
print('extras',json.dumps(extra,indent=1))
assert all(r['session_id'] not in placements for rows in extra.values() for r in rows)
t=hi.tally(tally['rows'],denylist=den)
assert all(t[k]==tally[k] for k in t)
try:hi.timed_practice_span([(0,'range'),(10,'timed')],[(90,'range'),(100,'timed'),(110,'range')],[(50,'timed')])
except hd.DemoError as ex:f1=str(ex)
else:raise AssertionError('F1 remains')
s=R/'data/human/sessions/20260925T203745-207Z-49728-2'; timed=json.loads((s/'timed-practice.json').read_text())
for x in timed['spans']:
 pairs=lambda rows:[(r['composition_ns'],r['label']) for r in rows]
 assert list(hi.timed_practice_span(pairs(x['start_bracket']),pairs(x['end_bracket']),pairs(x['interior'])))==x['cut_ns']
# No source contents opened for these registry-only adversarial checks.
r2=json.loads(json.dumps(reg)); row=next(iter(extra.values()))[0]; r2['sessions'].append(dict(session_id=row['session_id'],session_group=row['session_id'],split='train',video_path=row['video_path']))
p=O/'cross-category.json';p.write_text(json.dumps(r2))
try:hi.check_registry(p,denylist=den); cross='ACCEPTED'
except Exception as ex:cross=str(ex)
result=dict(pins=pins,registry_entries=len(placements),extra_categories={k:len(v) for k,v in extra.items()},tally=t,f1_refusal=f1,original_timed_cut_unchanged=True,cross_category_repro=cross)
(O/'audit.json').write_text(json.dumps(result,indent=1)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='tally'},indent=1))
