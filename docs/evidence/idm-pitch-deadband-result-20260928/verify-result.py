"""Recompute accepted TRAIN grid from archived predictions and pinned TRAIN tables only."""
from pathlib import Path
import hashlib
import json
import math
import statistics
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from policy import idm_targets as T
from policy.idm import pitch_deadband as P

b=ROOT/'data/idm/pitch-deadband-20260928';col=b/'collected'
m=json.loads((b/'manifest.json').read_bytes());c=json.loads((col/'result/calibration.json').read_bytes())
pred=json.loads((col/'result/train-predictions.json').read_bytes())
for rel,pin in json.loads((col/'collected-hashes.json').read_bytes()).items():assert T.sha256(col/rel)==pin
assert set(pred)==set(P.RANGES)
targets={};raw={};scores={tau:{} for tau in P.THRESHOLDS};suppression={};max_delta=0.0
for e in m['sessions']:
    if e['role']!='train':continue
    sid=e['session_id']
    path=ROOT/'data/idm/targets'/(sid+'.idm.jsonl')
    if not path.exists():path=ROOT/'data/idm/cloud-20260927/expanded-range-targets'/(sid+'.idm.jsonl')
    assert T.sha256(path)==e['targets_sha256']
    t=T.load(path);rows,selection=P.select(t,'train');assert selection==e['selection']
    t=T.Targets(t.header,rows);targets[sid]=t
    raw[sid]={int(k):v for k,v in pred[sid].items()}
    assert set(raw[sid])==set(selection['row_ids'])
    assert all(v[a] is None or math.isfinite(v[a]) for v in raw[sid].values() for a in ('pitch_deg','yaw_deg'))
    for tau in P.THRESHOLDS:
        q=P.correct(raw[sid],tau)
        for i,v in q.items():
            assert {k:x for k,x in v.items() if k!='pitch_deg'}=={k:x for k,x in raw[sid][i].items() if k!='pitch_deg'}
            assert (v['pitch_deg'] is None)==(raw[sid][i]['pitch_deg'] is None)
        scores[tau][sid]=P.score(t,q)
        for metric,value in scores[tau][sid].items():
            other=c['candidates'][str(tau)][sid][metric]
            assert value['n']==other['n']
            delta=abs(value['mean']-other['mean']);max_delta=max(max_delta,delta)
            assert delta<1e-12  # Cross-Python summation differs at the last floating-point bit.
        # Separate row arithmetic, independent of score().
        for label,condition in [('all',lambda x:True),('still',lambda x:abs(x)<.5),('moving',lambda x:abs(x)>=.5)]:
            errors=[abs(r['pitch_deg']-q[r['i']]['pitch_deg']) for r in rows
                    if q[r['i']]['pitch_deg'] is not None and condition(r['pitch_deg'])]
            assert len(errors)==scores[tau][sid][label]['n']
            assert abs(sum(errors)/len(errors)-scores[tau][sid][label]['mean'])<1e-12
        suppression.setdefault(str(tau),{})[sid]=sum(raw[sid][i]['pitch_deg']!=q[i]['pitch_deg'] for i in q)
tau,checks=P.choose_candidate(scores)
assert tau==c['tau']==0 and checks==c['checks']
assert not (col/'result/dev.json').exists() and not (col/'result/match-predictions.json').exists()
base=scores[0];summary=[]
for tau,s in scores.items():
    macro={key:statistics.fmean(v[key]['mean'] for v in s.values()) for key in ('all','still','moving','one_second')}
    macro['still_improvement_percent']=100*(1-macro['still']/statistics.fmean(v['still']['mean'] for v in base.values()))
    macro['worst_source_moving_increase_percent']=max(100*(v['moving']['mean']/base[sid]['moving']['mean']-1) for sid,v in s.items())
    macro['worst_source_one_second_increase_percent']=max(100*(v['one_second']['mean']/base[sid]['one_second']['mean']-1) for sid,v in s.items())
    summary.append({'tau':tau,**macro,'suppressed_rows':sum(suppression[str(tau)].values()),'guard':checks.get(str(tau))})
out={'all_collected_hashes_verified':True,'rows':28800,'exact_train_only_roster_and_rows':True,
     'all_ten_candidate_scores_recomputed':True,'independent_row_arithmetic_pass':True,
     'yaw_other_fields_and_abstention_invariant':True,'selected_tau':c['tau'],
     'cross_python_mean_tolerance':1e-12,'max_mean_absolute_difference':max_delta,
     'dev_or_match_predictions':False,'summary':summary,'suppression_per_source':suppression,
     'prediction_sha256':T.sha256(col/'result/train-predictions.json')}
(b/'verification.json').write_text(json.dumps(out,indent=2)+'\n',newline='\n')
print(json.dumps({'verified':True,'selected_tau':c['tau'],'rows':28800,'summary':summary},indent=2))
