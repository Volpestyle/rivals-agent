import sys
sys.dont_write_bytecode = True
import ctypes, datetime, hashlib, importlib.util, json, time
from pathlib import Path
P = Path(__file__).resolve().parent
ROOT = P.parents[2]
OUT = Path('D:/rivals-agent-evidence/idm-paired-camera-distillation-20260929')
def deadline():
    assert datetime.datetime.now(datetime.timezone.utc) < datetime.datetime.fromisoformat('2026-09-30T02:37:18+00:00'), 'two-hour stop'
def block(row, stores):
    times = [stores['live']['pts'][i] for i in row['live']] + [stores['replay']['pts'][i]+30.600 for i in row['replay']]
    return 'fit' if min(times)>=120 and max(times)<145 else 'report' if min(times)>=145 and max(times)<155 else 'purged'
def fit(z, target, np):
    mean=z.mean(0); std=np.maximum(z.std(0),1e-6); x=(z-mean)/std
    c=target.mean(0)
    b=np.linalg.solve(x.T@x/len(x)+np.eye(x.shape[1]), x.T@(target-c)/len(x))
    return mean,std,b,c
def metrics(y,p,np):
    active=np.abs(y)>=.1; n=int(active.sum()); good=int(((np.sign(y)==np.sign(p)) & (np.abs(p)>=.1) & active).sum())
    return dict(n=len(y),mae=float(np.abs(p-y).mean()),rmse=float(np.sqrt(np.mean((p-y)**2))),mean_abs=float(np.abs(p).mean()),rms=float(np.sqrt(np.mean(p*p))),centered_std=float(p.std()),signed_bias=float((p-y).mean()),active_n=n,sign_correct=good,sign_recall=good/n if n else None,active_mean_abs=float(np.abs(p[active]).mean()) if n else None)
def main():
    deadline()
    k=ctypes.WinDLL('kernel32',use_last_error=True); k.GetCurrentProcess.restype=ctypes.c_void_p; k.SetPriorityClass.argtypes=(ctypes.c_void_p,ctypes.c_ulong)
    assert k.SetPriorityClass(k.GetCurrentProcess(),0x4000)
    spec=importlib.util.spec_from_file_location('reviewed_v3',ROOT/'docs/evidence/idm-paired-camera-phase2-20260929-v3/paired.py'); v=importlib.util.module_from_spec(spec); spec.loader.exec_module(v)
    reg=v.read(P/'preregistration.json'); assert v.sha(Path(v.__file__))==reg['loader_sha256']
    for name,pin in v.read(P/'freeze.json').items(): assert v.sha(P/name)==pin
    OUT.mkdir(parents=True,exist_ok=True)
    v.write(OUT/'run-start.json',dict(started=datetime.datetime.now(datetime.timezone.utc).isoformat(),prereg_sha256=v.sha(P/'preregistration.json'),code_sha256=v.sha(__file__)))
    # Exact reviewed v3 access sequence, fixed existing paths; no new source paths.
    v.boundary()
    rp=v.OUT/'review-v2.json'; assert v.sha(rp)==reg['review_sha256']
    intervals=v.check_review(v.read(rp),v.sha(v.OUT/'prepared.json'))
    stores=v.read(v.OUT/'prepared.json'); assert set(stores)=={'live','replay'}
    for name,info in stores.items():
        assert v.sha(v.OUT/(name+'.grey'))==info['grey_sha256']
        assert v.sha(v.OUT/(name+'.rgb'))==info['rgb_sha256']
    rows=v.pairs(stores['live']['pts'],stores['replay']['pts'],intervals)
    assert v.sha(v.CHECKPOINT)==v.CHECKPOINT_SHA
    sys.path.insert(0,str(v.CLOSURE))
    import numpy as np, torch
    from policy.idm import train
    from policy import idm_targets
    from policy.idm import model as mm
    provenance=v.module_provenance(train,idm_targets,mm)
    torch.set_num_threads(2); torch.set_num_interop_threads(1)
    model,payload=train.load_checkpoint(v.CHECKPOINT,device='cpu'); model.eval(); model.requires_grad_(False)
    assert model.config.window==8 and model.config.height==252 and model.config.width==448
    arrays={name:np.memmap(v.OUT/(name+'.grey'),dtype=np.uint8,mode='r',shape=(len(info['pts']),252,448)) for name,info in stores.items()}
    groups={name:[i for i,r in enumerate(rows) if block(r,stores)==name] for name in ('fit','report','purged')}
    for store in ('live','replay'):
        a={j for i in groups['fit'] for j in rows[i][store]}; b={j for i in groups['report'] for j in rows[i][store]}; assert not a&b
    predictions={'live':[],'replay':[]}; features=[]; hidden=[]
    handle=model.camera[1].register_forward_hook(lambda m,i,o:hidden.append(o.detach().cpu().numpy().copy()))
    cal={'yaw_deg_per_count':.0330738,'pitch_deg_per_count':.0330738}
    with torch.inference_mode():
        for n,row in enumerate(rows):
            deadline()
            for name in ('live','replay'):
                hidden.clear(); motion=np.diff(arrays[name][row[name]].astype(np.float32)/255.,axis=0)
                _,camera=model(torch.from_numpy(motion[None]),torch.zeros((1,6,80,200)))
                raw=camera[0].tolist(); predictions[name].append(train._camera(raw[0],raw[1],raw[2:],{'t0_ns':0,'t1_ns':row['duration_ns']},cal))
                if name=='replay': features.append(hidden[0][0])
            if n%100==0: print('frozen extraction',n,'/',len(rows),flush=True)
    handle.remove()
    axes=('yaw_deg','pitch_deg')
    joint=[i for i in range(len(rows)) if all(predictions[s][i][a] is not None for s in predictions for a in axes)]
    fi=[i for i in groups['fit'] if i in joint]; hi=[i for i in groups['report'] if i in joint]; assert len(fi)>128 and hi
    f=np.array(features,dtype=np.float64); y=np.array([[predictions['live'][i][a] if predictions['live'][i][a] is not None else 0 for a in axes] for i in range(len(rows))]); r=np.array([[predictions['replay'][i][a] if predictions['replay'][i][a] is not None else 0 for a in axes] for i in range(len(rows))])
    deadline(); v.write(OUT/'fit-start.json',dict(fit_rows=len(fi),report_rows=len(hi),time=datetime.datetime.now(datetime.timezone.utc).isoformat()))
    mean,std,b,c=fit(f[fi],y[fi]-r[fi],np) # ONE real-data residual solve.
    xv=r[fi]-r[fi].mean(0); var=(xv*xv).mean(0); slope=np.divide((xv*(y[fi]-y[fi].mean(0))).mean(0),var,out=np.zeros(2),where=var>1e-12); intercept=y[fi].mean(0)-slope*r[fi].mean(0)
    methods={'unchanged':r[hi],'affine':r[hi]*slope+intercept,'residual':r[hi]+((f[hi]-mean)/std)@b+c,'zero':np.zeros((len(hi),2))}; teacher=y[hi]
    scores={}; gates={}
    for j,a in enumerate(axes):
        scores[a]={'teacher':metrics(teacher[:,j],teacher[:,j],np),**{m:metrics(teacher[:,j],p[:,j],np) for m,p in methods.items()}}
        q=scores[a]; res=q['residual']; t=q['teacher']
        agreement=all(res['mae']<=.99*q[m]['mae'] and res['rmse']<=q[m]['rmse'] for m in ('unchanged','affine')) and res['mae']<q['zero']['mae']
        magnitude=all(t[k]>0 and res[k]>=.8*t[k] for k in ('rms','centered_std','active_mean_abs')) if t['active_n'] else False
        sign=t['active_n']>0 and res['sign_recall']>=.8 and all(res['sign_recall']>=q[m]['sign_recall']-.02 for m in ('unchanged','affine'))
        gates[a]=dict(agreement=bool(agreement),magnitude=bool(magnitude),sign=bool(sign),positive=bool(agreement and magnitude and sign),decision='within-pair agreement only' if agreement and magnitude and sign else 'DO NOT EXPAND AXIS')
    counts={g:{'complete_contexts':len(ids),'joint_known':sum(i in joint for i in ids),'original_known':{s:{a:sum(predictions[s][i][a] is not None for i in ids) for a in axes} for s in predictions}} for g,ids in groups.items()}
    bins=[]
    for sec in range(145,155):
        ii=[k for k,i in enumerate(hi) if sec<=rows[i]['t']<sec+1]
        if ii: bins.append(dict(second=sec,n=len(ii),axes={a:{m:metrics(teacher[ii,j],p[ii,j],np) for m,p in methods.items()} for j,a in enumerate(axes)}))
    deadline()
    v.write(OUT/'result.json',dict(designation=reg['designation'],counts=counts,scores=scores,gates=gates,per_second=bins,runtime_modules=provenance,prepared_sha256=v.sha(v.OUT/'prepared.json'),review_sha256=v.sha(rp),checkpoint_sha256=v.CHECKPOINT_SHA,feature_sha256=hashlib.sha256(f.tobytes()).hexdigest(),fit_report_frame_overlap=False,fit_count=1,report_time_range=[rows[hi[0]]['t'],rows[hi[-1]]['t']],completed=datetime.datetime.now(datetime.timezone.utc).isoformat()))
    v.write(OUT/'parameters.json',dict(designation='scientific non-deployment coefficients; no checkpoint promotion or labels',feature_mean=mean.tolist(),feature_std=std.tolist(),B=b.tolist(),c=c.tolist(),affine_slope=slope.tolist(),affine_intercept=intercept.tolist()))
    print(json.dumps({'counts':counts,'gates':gates,'scores':scores}),flush=True)
if __name__=='__main__': main()
