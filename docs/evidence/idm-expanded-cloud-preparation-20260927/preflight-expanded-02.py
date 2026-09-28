import json,sys,time
from pathlib import Path
root=Path('/Users/james/dev/idm-data/expanded-refit-d4f05e0')
sys.path.insert(0,str(root/'runtime-authority10/code/cloud/idm_payload'))
from policy import idm_targets as T
from policy.idm import explore as E,match_targets as M,temporal
from scripts.job_status import write
job='idm-expanded-table-preflight-02-d4f05e0'
write(job,owner='idm-owner',host='mac',stage='running',evidence=str(root/'table-preflight-02.json'))
start=time.monotonic()
try:
    m=E.read_pinned(root/'source-sessions.json','5e1834e6eac34b7048d33a0e393c7cf890d0a0af76928d5af801c5a5fa01923c')
    deny=T.load_denylist()
    admission=M.load_references(m['match_admissions'],registry=T.REGISTRY,denylist=deny)
    loaded=E.preflight(m,registry=T.REGISTRY,denylist=deny,admission=admission)
    platform=E.require_decode_platform(loaded)
    rows=[]
    for item,target in loaded:
        pairs,counts=temporal.context_rows(target,tuple(range(-8,9)))
        rows.append({'session_id':target.session_id,'role':item['role'],'training_rows':len(T.training_rows(target)),
                     'context_rows':len(pairs),'context_counts':counts})
        write(job,progress={'n':len(rows),'total':len(loaded)})
    result={'status':'PASS','seconds':time.monotonic()-start,'decode_platform':platform,'sessions':rows,
        'train_context_rows':sum(r['context_rows'] for r in rows if r['role']=='train'),
        'heldout_context_rows':sum(r['context_rows'] for r in rows if r['role']=='heldout'),
        'pixels_read':False,'media_read':False}
    E.write_json(root/'table-preflight-02.json',result)
    (root/'table-preflight-02.exit').write_text('0\n')
    write(job,stage='done')
    print(json.dumps(result),flush=True)
except BaseException:
    (root/'table-preflight-02.exit').write_text('1\n')
    write(job,stage='failed')
    raise
