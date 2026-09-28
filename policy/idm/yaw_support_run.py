"""Bounded TRAIN/range-dev full03 calibration. Metadata freeze precedes pixels."""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

import numpy as np
from policy.idm import yaw_support as S
from policy.idm.pitch_deadband import RANGES, DEV

MATCHES=('20260927T051206-888Z-150600-4','20260927T052001-827Z-150600-5','20260927T053118-260Z-150600-6')


def roster(manifest):
    expected={**{s:'train' for s in (*RANGES,*MATCHES)}, **{s:'dev' for s in DEV}}
    entries=manifest['sessions']
    if len(entries)!=len(expected) or {e['session_id']:e['role'] for e in entries}!=expected:
        raise ValueError('exact full03 TRAIN and two range-dev roster required')


def checkpoint_roster(meta, manifest):
    """Checkpoint provenance includes DEV too; authenticate roles, not keys alone."""
    roster(manifest)
    expected={e['session_id']:e for e in manifest['sessions']}
    if set(meta['targets'])!=set(expected) or set(meta['frame_stores'])!=set(expected):
        raise ValueError('checkpoint provenance roster mismatch')
    trained=set()
    for sid,e in expected.items():
        actual=meta['targets'][sid]
        split='idm_train' if sid in MATCHES else ('val' if sid in DEV else 'train')
        if actual['split']!=split or actual['sha256']!=e['targets_sha256'] \
                or meta['frame_stores'][sid]['manifest_sha256']!=e['frames_sha256']:
            raise ValueError('checkpoint role/target/store pin differs')
        if actual['split'] in ('train','idm_train'):trained.add(sid)
    if trained!=set((*RANGES,*MATCHES)):raise ValueError('checkpoint TRAIN roster mismatch')


def select(target, store_meta, role):
    from policy.idm.temporal import context_rows
    pairs,counts=context_rows(target,tuple(range(-8,9)))
    keys=set(store_meta['frame_indices'])
    rows=[r for r,_ in pairs if all(r['frame1']['frame_index']+2*k in keys for k in range(-8,9))
          and r['frame0']['frame_index'] in keys]
    chosen=[rows[k] for k in S.uniform_indices(len(rows),512 if role=='train' else 4096)]
    return chosen, {'context_counts':counts,'store_complete_rows':len(rows),'row_ids':[r['i'] for r in chosen],
                    'contexts':[[r['frame1']['frame_index']-16,r['frame1']['frame_index']+16] for r in chosen]}


def write_json(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def main():
    import torch
    from policy import idm_targets as T, idm_eval as E
    from policy.idm import frames, train, match_targets as M
    from policy.idm.telemetry import emit
    from scripts.job_status import write
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest');p.add_argument('sha256');p.add_argument('output')
    p.add_argument('--seconds',type=int,default=1800)
    a=p.parse_args()
    if not 1<=a.seconds<=1800:raise ValueError('at most 30 minutes')
    torch.set_num_threads(2)
    start=time.monotonic(); deadline=start+a.seconds
    def check():
        if time.monotonic()>=deadline:raise TimeoutError('support phase time box reached')
    if T.sha256(a.manifest)!=a.sha256:raise ValueError('manifest pin')
    m=json.loads(Path(a.manifest).read_bytes());roster(m)
    out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
    job='idm-yaw-support-20260928'
    emit(write,job,owner='idm-owner',host='mac',stage='running',evidence=str(out/'report.json'))
    result={'scope':'EXPLORATORY calibration, not Gate 2 or source admission','exit':1,'sessions':{}}
    try:
        deny=T.load_denylist()
        admission=M.load_references(m['match_admissions'],registry=m['registry'],denylist=deny)
        if set(admission.sessions)!=set(MATCHES):raise ValueError('unexpected match admission selected')
        if T.sha256(m['checkpoint'])!=S.CHECKPOINT:raise ValueError('full03 pin')
        model,payload=train.load_checkpoint(m['checkpoint'],device='mps')
        checkpoint_roster(payload['meta'],m)
        if model.config.embed!=128:raise ValueError('feature dimension')
        selections={};selected={};rates=[];rate_summary={}
        def load(e):
            if T.sha256(e['targets'])!=e['targets_sha256']:raise ValueError('target pin')
            t=T.load(e['targets'],denylist=deny,match_admission=admission if e['session_id'] in MATCHES else None)
            if t.session_id!=e['session_id']:raise ValueError('session identity')
            split='idm_train' if t.session_id in MATCHES else ('val' if e['role']=='dev' else 'train')
            if t.header['split']!=split:raise ValueError('role mismatch')
            fp=Path(e['store'])/'frames.json'
            if T.sha256(fp)!=e['frames_sha256']:raise ValueError('frame manifest pin')
            sm=json.loads(fp.read_bytes())
            T.refuse_sealed(sm['session_id'],sm['media_sha256'],deny)
            if sm['session_id']!=t.session_id or sm['media_sha256']!=t.header['media_sha256'] \
                    or sm['decode']['platform']!='Darwin arm64':raise ValueError('store provenance')
            return t,sm
        for e in m['sessions']:
            check(); t,sm=load(e)
            rows,selection=select(t,sm,e['role'])
            selections[t.session_id]=selection
            selected[t.session_id]=T.Targets(t.header,rows)
            if e['role']=='train':
                values=[S.rate(r['yaw_deg'],r['t1_ns']-r['t0_ns']) for r in T.training_rows(t) if r['yaw_deg'] is not None]
                rates.extend(values)
                rate_summary[t.session_id]={'n':len(values),'p995':float(np.quantile(values,.995,method='linear'))}
            del t,sm
        rows_path=out/'rows.json';write_json(rows_path,selections)
        rows_sha=T.sha256(rows_path)
        # Durable selection receipt and stdout before any FrameStore pixel map.
        write_json(out/'selection-frozen.json',{'manifest_sha256':a.sha256,'row_manifest_sha256':rows_sha})
        print(json.dumps({'selection_frozen':rows_sha,'counts':{s:len(v['row_ids']) for s,v in selections.items()}}),flush=True)
        embeddings={};raw={};timings={}
        for e in m['sessions']:
            check();sid=e['session_id'];st0=time.monotonic()
            store=frames.FrameStore(e['store'],verify=True,denylist=deny)
            verify=time.monotonic()-st0
            try:
                t=selected[sid];ex=train.Examples([(t,store)],model.config,model.support)
                if len(ex)!=len(t.rows) or ex.missing:raise ValueError('frozen selection contexts missing')
                chunks=[];pred={};infer0=time.monotonic()
                with torch.inference_mode():
                    for k in range(0,len(ex),32):
                        check();idx=list(range(k,min(k+32,len(ex))))
                        motion,_=ex.inputs(idx)
                        z=model.motion(motion.to('mps'))
                        cam=model.camera(z).cpu().numpy(); cam[:,2:]=np.clip(cam[:,2:],-12,8)
                        chunks.append(z.cpu().numpy())
                        for j,i in enumerate(idx):
                            r=ex.items[i][2]
                            pred[r['i']]=train._camera(float(cam[j,0]),float(cam[j,1]),cam[j,2:],r,t.header['calibration'])
                embeddings[sid]=np.concatenate(chunks);raw[sid]=pred
                np.save(out/(sid+'.features.npy'),embeddings[sid],allow_pickle=False)
                write_json(out/(sid+'.raw.json'),pred)
                timings[sid]={'verify_seconds':verify,'infer_seconds':time.monotonic()-infer0,'rows':len(ex)}
                print(json.dumps({'session_complete':sid,**timings[sid]}),flush=True)
                emit(write,job,progress={'n':len(raw),'total':len(m['sessions'])})
            finally:
                store.frames._mmap.close();store.huds._mmap.close()
        check()
        train_x=np.concatenate([embeddings[e['session_id']] for e in m['sessions'] if e['role']=='train'])
        dev_x=np.concatenate([embeddings[e['session_id']] for e in m['sessions'] if e['role']=='dev'])
        artifact=S.calibrate(train_x,dev_x,rates,provenance={'manifest_sha256':a.sha256,
                             'row_manifest_sha256':rows_sha,'code_sha256':m['code_sha256']})
        artifact_path=out/'support.json';write_json(artifact_path,artifact)
        artifact=S.load(artifact_path,T.sha256(artifact_path))
        for e in m['sessions']:
            sid=e['session_id'];t=selected[sid];pr=raw[sid];masked={}
            for r,z in zip(t.rows,embeddings[sid]):masked[r['i']]=S.apply(artifact,z,pr[r['i']],r['t1_ns']-r['t0_ns'])
            slices={}
            for name,rows in [('all',t.rows),('still',[r for r in t.rows if abs(r['yaw_deg'])<E.MOVING_DEG]),
                              ('moving',[r for r in t.rows if abs(r['yaw_deg'])>=E.MOVING_DEG])]+[
                                  (reg,[r for r in t.rows if r['gain_regime']==reg]) for reg in ('calibrated','extrapolated')]:
                reasons=Counter(reason for r in rows for reason in masked[r['i']]['support']['reasons'])
                slices[name]={'rows':len(rows),'answered':sum(masked[r['i']]['yaw_deg'] is not None for r in rows),
                              'reasons_nonexclusive':dict(reasons)}
            # Existing scorer splits discontinuous rows; no invented windows.
            result['sessions'][sid]={'role':e['role'],'coverage':slices,
                                     'raw':E.camera_metrics(t,pr)['yaw_deg'],
                                     'masked':E.camera_metrics(t,masked)['yaw_deg'],
                                     'raw_uncertainty':train.std_coverage(t,pr)['yaw'],
                                     'masked_uncertainty':train.std_coverage(t,masked)['yaw']}
            write_json(out/(sid+'.masked.json'),masked)
        result.update(exit=0,status='calibration_complete_unqualified',artifact_sha256=T.sha256(artifact_path),
                      row_manifest_sha256=rows_sha,rate_by_source=rate_summary,timings=timings)
    except BaseException as exc:
        result.update(status='incomplete',error=repr(exc));raise
    finally:
        result['seconds']=time.monotonic()-start
        write_json(out/'report.json',result)
        (out/'support.exit').write_text(str(result['exit'])+'\n')
        emit(write,job,stage='done' if result['exit']==0 else 'failed')


if __name__=='__main__':main()
