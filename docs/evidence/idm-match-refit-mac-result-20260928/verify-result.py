from pathlib import Path
import json,hashlib,ctypes,gc,math
from types import SimpleNamespace
ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x4000)
import numpy as np
import torch
torch.set_num_threads(2)
from policy import idm_targets as T
from policy.idm import temporal,match_diagnostic as D,mac_refit as M,press_diagnostic as P,epoch_resume as ER
from policy.range_bc import vocab
B=Path('data/idm/match-refit-mac-20260928');C=B/'collected';R=C/'result'
manifest=json.loads((C/'manifest-a1.json').read_bytes());complete=json.loads((R/'complete.json').read_bytes())
assert T.sha256(C/'manifest-a1.json')==complete['manifest_sha256']=='73d486da67f85e87041567cd4d90b553c24a40e22c0cff05a63136e29f771d5c'
M.validate_roster(manifest)
original=json.loads(Path('docs/evidence/idm-pitch-deadband-freeze-20260928/manifest.json').read_bytes())
for item in manifest['transfer']:
 old=next(x for x in original['sessions'] if x['session_id']==item['session_id'])
 assert old['selection']==item['selection']
inv=json.loads((C/'collection-receipt.json').read_bytes())
for rel,pin in inv['files'].items():
 f=C/rel;assert f.stat().st_size==pin['bytes'] and T.sha256(f)==pin['sha256'],rel
assert inv['active_processes']==[]
for phase in ('fit','press','evaluate'):assert (C/(phase+'.exit')).read_text().strip()=='0'
model=torch.load(R/'fit/refit.pt',map_location='cpu',weights_only=True)
assert T.sha256(R/'fit/refit.pt')=='1ddf84b5486973ef65387d65d9304daf507d58deb0ab026117c618739bab8efb'
assert set(M.TRANSFER).isdisjoint(model['meta']['targets'])
for p in sorted((R/'fit/epochs').glob('*.complete.json')):
 rec=json.loads(p.read_bytes());j=ER.EpochJournal(p.parent,identity=rec['contract']['identity'],provenance=rec['contract']['provenance'],commit=lambda:None);j.contract=rec['contract'];state,_=j.read(p)
 if rec['completed_epochs']==3:
  assert all(torch.equal(model['model'][k],state['model'][k]) for k in model['model'])
max_delta=0.0
def equal(a,b):
 global max_delta
 if isinstance(a,dict):
  assert a.keys()==b.keys()
  for k in a:equal(a[k],b[k])
 elif isinstance(a,list):
  assert len(a)==len(b)
  for x,y in zip(a,b):equal(x,y)
 elif isinstance(a,float):
  assert math.isfinite(a) and math.isfinite(b);max_delta=max(max_delta,abs(a-b));assert abs(a-b)<=1e-12,(a,b)
 else:assert a==b,(a,b)
def read(item,transfer):
 sid=item['session_id'];T.refuse_sealed(sid,None,T.load_denylist())
 path=Path('data/idm/range-to-match-20260928')/sid/(sid+'.idm.jsonl') if transfer else Path('data/idm/targets')/(sid+'.idm.jsonl')
 assert T.sha256(path)==item['targets_sha256']
 with path.open() as f:
  head=json.loads(next(f));rows=[json.loads(x) for x in f if x.strip()]
 assert head['session_id']==sid;T.refuse_sealed(sid,head['media_sha256'],T.load_denylist())
 pairs,_=temporal.context_rows(T.Targets(head,rows),tuple(range(-8,9)));by={r['i']:r for r,_ in pairs}
 ids=item['selection']['row_ids'] if transfer else list(by)
 return T.Targets(head,[by[i] for i in ids])
verified={};dev=[]
for phase in ('range_dev','transfer'):
 report=json.loads((R/phase/'report.json').read_bytes())
 assert T.sha256(R/phase/'report.json')==complete['results'][phase]['report_sha256']
 assert T.sha256(R/phase/'predictions.json')==complete['results'][phase]['predictions_sha256']
 pred=json.loads((R/phase/'predictions.json').read_bytes());pred={n:{s:{int(i):v for i,v in p.items()} for s,p in ss.items()} for n,ss in pred.items()}
 items=manifest['transfer'] if phase=='transfer' else [i for i in manifest['sessions'] if i['role']=='heldout']
 targets=[read(i,phase=='transfer') for i in items]
 for t in targets:
  for n in pred:assert set(pred[n][t.session_id])=={r['i'] for r in t.rows}
 for n,p in pred.items():equal(D.summaries(targets,p),report['own_coverage'][n])
 common=M.shared(pred)
 for n,p in common.items():equal(D.summaries(targets,p),report['shared_answered_rows'][n])
 verified[phase]={'rows':{t.session_id:len(t.rows) for t in targets},'all_camera_metrics_recomputed':True}
 if phase=='range_dev':dev=targets
 del pred,common,targets;gc.collect()
press=json.loads((R/'press/report.json').read_bytes());cal=json.loads((R/'press/calibration.json').read_bytes())
assert cal==press['calibration'];assert set(cal['sessions'])=={i['session_id'] for i in manifest['sessions'] if i['role']=='train'}
prob=np.load(R/'press/train-probabilities.npy',allow_pickle=False);assert prob.shape==(722074,3) and prob.dtype==np.float32 and np.isfinite(prob).all()
for k,a in enumerate(P.ACTIONS):
 n=model['meta']['train_press_counts'][a];cut=float(np.sort(prob[:,k])[-n]);assert cut==cal['thresholds'][a]
 assert cal['rates'][a]['target']==n/len(prob);assert cal['rates'][a]['achieved']==float(np.mean(prob[:,k]>=cut))
rows=json.loads((R/'press/heldout-row-ids.json').read_bytes());assert rows==[[t.session_id,r['i']] for t in dev for r in t.rows]
oldrows=json.loads(Path('data/idm/cloud-20260927/full03-result-collected/artifacts/real/row-ids.json').read_bytes());assert rows==oldrows
cols=[vocab.INDEX[a] for a in P.ACTIONS];items=[(t,None,r,None) for t in dev for r in t.rows]
view=SimpleNamespace(actions=P.ACTIONS,items=items,y=torch.tensor([[float(r['press'][c]>0) for c in cols] for _,_,r,_ in items]),mask=torch.tensor([[bool(r['held_known'][c]) for c in cols] for _,_,r,_ in items]))
supported=[bool(model['meta']['supported'][a]) for a in P.ACTIONS]
for control in ('real','zero_visuals'):
 scores=np.load(R/'press'/(control+'-probabilities.npy'),allow_pickle=False)
 assert scores.shape==(49080,3) and scores.dtype==np.float32 and np.isfinite(scores).all()
 for name,cuts in [('fixed_0.5',[.5]*3),('train_rate',[cal['thresholds'][a] for a in P.ACTIONS])]:
  equal(P.score(view,scores,cuts,supported),press['controls'][control][name])
verified.update(files_verified=len(inv['files']),epochs_verified=3,complete_model_equals_epoch3=True,train_calibration_recomputed=True,press_scores_chance_recomputed=True,baseline_dev_row_order_identical=True,max_numeric_difference=max_delta,heldout_no_tuning=True)
(B/'verification.json').write_text(json.dumps(verified,indent=2)+'\n',newline='\n');print(json.dumps(verified,indent=2))
