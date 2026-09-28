"""Accepted a065c99: TRAIN-range-only pitch deadband; strict sequential vetoes."""
import argparse
import copy
import json
import math
from pathlib import Path
import statistics

from policy import idm_eval as E, idm_targets as T
from policy.idm import match_diagnostic as D

THRESHOLDS = (0, .025, .05, .075, .10, .15, .20, .30, .40, .50)
RANGES = ('20260923T051828-422Z-33696-1', '20260923T200129-346Z-33696-6',
          '20260924T232304-170Z-12024-1', '20260925T021320-371Z-7804-1',
          '20260925T025230-605Z-7804-2', '20260925T203745-207Z-49728-2',
          '20260926T035932-508Z-63684-14', '20260926T045729-166Z-79780-1')
DEV = ('20260923T171533-187Z-33696-5', '20260923T205528-900Z-45572-3')


def correct(pred, tau):
    if tau not in THRESHOLDS:
        raise ValueError('threshold outside accepted grid')
    out = copy.deepcopy(pred)
    if tau:
        for p in out.values():
            value = p['pitch_deg']
            if value is not None and abs(value) <= tau:
                p['pitch_deg'] = 0.0
    return out


def runs(rows):
    result, current = [], []
    for row in rows:
        if current and (row['run'] != current[-1]['run'] or row['segment'] != current[-1]['segment']
                        or row['t0_ns'] != current[-1]['t1_ns']):
            result.append(current)
            current = []
        current.append(row)
    if current:
        result.append(current)
    return result


def blocks(rows, size):
    return [run[k:k+size] for run in runs(rows) for k in range(0, len(run)-size+1, size)]


def context(row):
    f = row['frame1']['frame_index']
    # Grey offsets plus both HUD frames; range includes unsampled intervening frames conservatively.
    return min(f-16, row['frame0']['frame_index']), f+16


def overlap(a, b):
    return a[0] <= b[1] and b[0] <= a[1]


def select(target, mode, old=None, samples=()):
    from policy.idm.temporal import context_rows
    pairs, counts = context_rows(target, tuple(range(-8, 9)))
    rows = [r for r, _ in pairs]
    if mode == 'train':
        if target.session_id not in RANGES or target.header['split'] != 'train':
            raise ValueError('only eight TRAIN ranges choose thresholds')
        candidates = blocks(rows, 900)
        indices = [j*(len(candidates)-1)//3 for j in range(4)]
        if len(set(indices)) != 4 or min(indices) < 0:
            raise ValueError('four distinct range blocks required')
        selected = [r for k in indices for r in candidates[k]]
    elif mode == 'dev':
        if target.session_id not in DEV:
            raise ValueError('wrong range dev')
        selected = rows
    elif mode == 'match':
        if target.session_id not in D.SESSIONS or target.header['split'] != 'idm_train':
            raise ValueError('wrong match roster/role')
        old_ids = set(old['row_ids'])
        previous = [r for r in target.rows if r['i'] in old_ids]
        if len(previous) != len(old_ids):
            raise ValueError('old rows absent')
        forbidden = [(min(context(r)[0] for r in run), max(context(r)[1] for r in run))
                     for run in runs(previous)]
        embargo = [(v['t0_ns']-1_000_000_000, v['t1_ns']+1_000_000_000) for v in old['blocks']]
        keep = [r for r in rows if r['i'] not in old_ids
                and not any(r['t0_ns'] < hi and r['t1_ns'] > lo for lo, hi in embargo)
                and not any(overlap(context(r), span) for span in forbidden)
                and not any(context(r)[0] <= f <= context(r)[1] for f in samples)]
        selected = [r for block in blocks(keep, 60) for r in block]
        if not selected:
            raise ValueError('empty unread complement')
    else:
        raise ValueError('unknown selection role')
    return selected, {'mode': mode, 'counts': counts, 'selected': len(selected),
                      'row_ids': [r['i'] for r in selected],
                      'runs': [{'first_i': g[0]['i'], 'last_i': g[-1]['i'],
                                't0_ns': g[0]['t0_ns'], 't1_ns': g[-1]['t1_ns'],
                                'context_frames': [min(context(r)[0] for r in g), max(context(r)[1] for r in g)]}
                               for g in runs(selected)]}


def score(target, pred):
    pairs = [(r['pitch_deg'], pred[r['i']]['pitch_deg']) for r in target.rows
             if r['pitch_deg'] is not None and pred[r['i']]['pitch_deg'] is not None]
    def stats(p):
        return {'n': len(p), 'mean': statistics.fmean(abs(a-b) for a, b in p) if p else None}
    windows = []
    for group in blocks(target.rows, 60):
        if all(r['pitch_deg'] is not None and pred[r['i']]['pitch_deg'] is not None for r in group):
            windows.append(abs(sum(pred[r['i']]['pitch_deg']-r['pitch_deg'] for r in group)))
    return {'all': stats(pairs), 'still': stats([(a,b) for a,b in pairs if abs(a)<.5]),
            'moving': stats([(a,b) for a,b in pairs if abs(a)>=.5]),
            'one_second': {'n': len(windows), 'mean': statistics.fmean(windows) if windows else None}}


def gate(base, candidate, *, match=False):
    if not base or set(base) != set(candidate):
        return False, 'source set differs'
    for sid, b in base.items():
        c = candidate[sid]
        if b['moving']['n'] < 30 or b['one_second']['n'] < 5 or not b['still']['n']:
            return False, 'insufficient support: '+sid
        if any(c[k]['n'] != b[k]['n'] or c[k]['mean'] is None or not math.isfinite(c[k]['mean']) for k in b):
            return False, 'coverage/finite refusal: '+sid
        if c['moving']['mean'] > b['moving']['mean']*(1.05 if match else 1.02):
            return False, 'moving guard: '+sid
        if not match and c['one_second']['mean'] > b['one_second']['mean']*1.02:
            return False, 'one-second guard: '+sid
    def macro(x, key):
        return statistics.fmean(s[key]['mean'] for s in x.values())
    if macro(candidate, 'still') > .95*macro(base, 'still'):
        return False, 'still reduction below five percent'
    if macro(candidate, 'all') > macro(base, 'all'):
        return False, 'macro overall worsens'
    if match and (macro(candidate, 'one_second') > macro(base, 'one_second')
                  or macro(candidate, 'moving') > 1.02*macro(base, 'moving')):
        return False, 'match macro guard'
    return True, 'qualifies'


def choose_candidate(candidates):
    base = candidates[0]
    qualified, checks = [], {}
    for tau in THRESHOLDS[1:]:
        ok, why = gate(base, candidates[tau])
        checks[str(tau)] = {'qualifies': ok, 'reason': why}
        if ok:
            qualified.append((statistics.fmean(s['all']['mean'] for s in candidates[tau].values()), tau))
    return min(qualified)[1] if qualified else 0, checks


def main():
    import torch
    from policy.idm import train, frames, match_targets as M
    from policy.idm.telemetry import emit
    from scripts.job_status import write
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=('prepare','run'));p.add_argument('manifest');p.add_argument('sha256');p.add_argument('output')
    args=p.parse_args();torch.set_num_threads(2)
    if T.sha256(args.manifest)!=args.sha256:raise ValueError('manifest pin')
    m=json.loads(Path(args.manifest).read_bytes());out=Path(args.output);out.mkdir(exist_ok=False,parents=True)
    deny=T.load_denylist()
    admission=M.load_references(m['match_admissions'],registry=m['registry'],denylist=deny)
    expected={'train':set(RANGES),'dev':set(DEV),'match':set(D.SESSIONS)}
    for mode,sids in expected.items():
        entries=[e for e in m['sessions'] if e['role']==mode]
        if {e['session_id'] for e in entries}!=sids or len(entries)!=len(sids):raise ValueError('exact role roster')
    targets={};selections={}
    for e in m['sessions']:
        if T.sha256(e['targets'])!=e['targets_sha256']:raise ValueError('target pin')
        t=T.load(e['targets'],denylist=deny,match_admission=admission if e['role']=='match' else None)
        if t.session_id!=e['session_id']:raise ValueError('source identity')
        rows,s=select(t,e['role'],e.get('old'),e.get('samples',()))
        if args.mode=='run' and s!=e['selection']:raise ValueError('frozen rows changed')
        e['selection']=s;targets[t.session_id]=T.Targets(t.header,rows);selections[t.session_id]=s
    if args.mode=='prepare':
        (out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
        print(json.dumps({sid:s['selected'] for sid,s in selections.items()}),flush=True)
        return
    job='idm-pitch-deadband-20260928'
    emit(write,job,owner='idm-owner',host='mac',stage='running',evidence=str(out.resolve()/'result.json'))
    try:
        path=m['checkpoints']['full03']
        if T.sha256(path)!=D.CHECKPOINTS['full03']:raise ValueError('full03 changed')
        model,payload=train.load_checkpoint(path,device='mps')
        if set(D.SESSIONS)&set(payload['meta']['targets']):raise ValueError('match was in fit')
        predictions={};candidate_scores={tau:{} for tau in THRESHOLDS}
        def infer(e, mdl=model):
            sid=e['session_id'];t=targets[sid]
            if T.sha256(Path(e['store'])/'frames.json')!=e['frames_sha256']:raise ValueError('store pin')
            st=frames.FrameStore(e['store'],verify=True,denylist=deny)
            if st.manifest['decode']['platform']!='Darwin arm64':raise ValueError('decode platform')
            ex=train.Examples([(t,st)],mdl.config,mdl.support)
            if len(ex)!=len(t.rows) or ex.missing:raise ValueError('missing complete contexts')
            raw=train.predict(mdl,t,st,device='mps')
            st.frames._mmap.close();st.huds._mmap.close()
            return raw
        for e in [e for e in m['sessions'] if e['role']=='train']:
            sid=e['session_id'];predictions[sid]=infer(e)
            for tau in THRESHOLDS:candidate_scores[tau][sid]=score(targets[sid],correct(predictions[sid],tau))
            emit(write,job,progress='TRAIN ranges '+str(len(predictions))+'/8')
        tau,checks=choose_candidate(candidate_scores)
        calibration={'tau':tau,'candidates':candidate_scores,'checks':checks,'manifest_sha256':args.sha256,
                     'selection_sources':list(RANGES),'thresholds':THRESHOLDS}
        (out/'calibration.json').write_text(json.dumps(calibration,indent=2)+'\n')
        (out/'train-predictions.json').write_text(json.dumps(predictions)+'\n')
        short_support=any(s['moving']['n']<30 or s['one_second']['n']<5 or not s['still']['n']
                          for s in candidate_scores[0].values())
        result={'scope':'EXPLORATORY; not Gate 2','tau':tau,'manifest_sha256':args.sha256,'stage':'train',
                'status':'undecided_support' if short_support else 'negative_calibration_identity',
                'match_predictions_read':False}
        if tau:
            dev={e['session_id']:infer(e) for e in m['sessions'] if e['role']=='dev'}
            base={sid:score(targets[sid],v) for sid,v in dev.items()}
            changed={sid:score(targets[sid],correct(v,tau)) for sid,v in dev.items()}
            ok,why=gate(base,changed)
            (out/'dev.json').write_text(json.dumps({'raw':base,'corrected':changed,'pass':ok,'reason':why},indent=2)+'\n')
            (out/'dev-predictions.json').write_text(json.dumps(dev)+'\n')
            result.update(stage='range_dev',status='veto_failed',reason=why)
            if ok:
                path=m['checkpoints']['prior']
                if T.sha256(path)!=D.CHECKPOINTS['prior']:raise ValueError('prior changed')
                prior,meta=train.load_checkpoint(path,device='mps')
                if set(D.SESSIONS)&set(meta['meta']['targets']):raise ValueError('match was in prior fit')
                ps={n:{} for n in ('full03','prior','corrected','zero')}
                for e in [e for e in m['sessions'] if e['role']=='match']:
                    sid=e['session_id'];raw=infer(e)
                    ps['full03'][sid]=raw;ps['prior'][sid]=infer(e,prior)
                    ps['corrected'][sid]=correct(raw,tau)
                    ps['zero'][sid]={r['i']:{'yaw_deg':0.0,'pitch_deg':0.0} for r in targets[sid].rows}
                common=D.common_answers(ps);tt=[targets[s] for s in D.SESSIONS]
                metric={n:D.summaries(tt,pr) for n,pr in common.items()}
                base={s:score(targets[s],common['full03'][s]) for s in D.SESSIONS}
                changed={s:score(targets[s],common['corrected'][s]) for s in D.SESSIONS}
                ok,why=gate(base,changed,match=True)
                result.update(stage='match',status='pass' if ok else 'failed',reason=why,
                              match_predictions_read=True,common_rows=metric)
                (out/'match-predictions.json').write_text(json.dumps(ps)+'\n')
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        emit(write,job,stage='done',progress=result['status'])
        print(json.dumps(result),flush=True)
    except BaseException:
        emit(write,job,stage='failed');raise


if __name__=='__main__':main()
