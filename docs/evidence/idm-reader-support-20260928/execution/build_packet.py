import hashlib,json,subprocess,tarfile
from pathlib import Path
root=Path(__file__).resolve().parent
remote='/Users/james/dev/idm-data/reader-support-20260928'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
paths=set()
for base in ('agent','policy/idm'):
 paths.update(str(p).replace('\\','/') for p in Path(base).glob('*.py'))
paths.update(['policy/__init__.py','policy/idm_targets.py','policy/idm_eval.py',
 'policy/range_bc/__init__.py','policy/range_bc/steps.py','policy/range_bc/vocab.py',
 'policy/idm/receipt-current.json','data/human/patch-equivalence.json','data/human/sealed-denylist.v2.json',
 'data/human/session-splits.corpus.json','perception/match_timer.py','perception/match_timer_glyphs.json',
 'perception/match_timer_contrast.py','perception/killfeed_geometry.py','scripts/idm_reader_support.py','scripts/job_status.py'])
paths.update(json.loads(Path('policy/idm/receipt-current.json').read_bytes())['files'])
for p in sorted(paths):
 dst=root/'code'/p;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(Path(p).read_bytes())
inv={p:sha(root/'code'/p) for p in sorted(paths)}
(root/'inventory.json').write_text(json.dumps(inv,indent=2)+'\n',newline='\n')
m=json.loads(Path('data/idm/match-refit-mac-20260928/manifest-a1.json').read_bytes())
from policy.idm.yaw_support_run import RANGES,DEV,MATCHES
entries=[]
for e in m['sessions']:
 sid=e['session_id']
 if sid not in (*RANGES,*DEV,*MATCHES):continue
 e={k:v for k,v in e.items() if k not in ('selection','old','samples')}
 e['role']='dev' if sid in DEV else 'train';entries.append(e)
refs=[]
for e in m['match_admissions'][:3]:
 relative=e['path'].split('/code/',1)[1]
 refs.append({**e,'path':remote+'/code/'+relative})
support={'sessions':entries,'match_admissions':refs,'registry':remote+'/code/data/human/session-splits.corpus.json',
 'checkpoint':m['checkpoints']['full03']['path'],'code_sha256':sha(root/'inventory.json'),'commit':commit}
(root/'support-manifest.json').write_text(json.dumps(support,indent=2)+'\n',newline='\n')
old=Path('data/idm/yaw-readiness-20260928');comp=json.loads((root/'competitive-excerpt.json').read_bytes())
ex=json.loads((old/'excerpts.json').read_bytes())
excerpts={s['name']:{'path':'/Users/james/dev/idm-data/yaw-readiness-20260928/'+s['excerpt'],
 'sha256':s['excerpt_sha256'],'source_sha256':s['source_sha256']} for s in ex['sources'] if s['name']!='competitive'}
excerpts['competitive']={'path':remote+'/competitive-300.mkv','sha256':comp['excerpt_sha256'],'source_sha256':comp['source_sha256']}
for name in ('native-result.json','human-sample-labels.json'):(root/name).write_bytes((old/name).read_bytes())
readers={'excerpts':excerpts,'native_root':'/Users/james/dev/idm-data/yaw-readiness-20260928',
 'native_manifest':remote+'/native-result.json','native_manifest_sha256':sha(root/'native-result.json'),
 'labels':remote+'/human-sample-labels.json','labels_sha256':sha(root/'human-sample-labels.json'),'commit':commit}
(root/'reader-manifest.json').write_text(json.dumps(readers,indent=2)+'\n',newline='\n')
with tarfile.open(root/'packet.tar.gz','w:gz') as tar:
 for name in ('code','inventory.json','support-manifest.json','reader-manifest.json','native-result.json','human-sample-labels.json','competitive-excerpt.json'):
  tar.add(root/name,arcname=name)
receipt={'commit':commit,'packet_sha256':sha(root/'packet.tar.gz'),'inventory_sha256':sha(root/'inventory.json'),
 'support_manifest_sha256':sha(root/'support-manifest.json'),'reader_manifest_sha256':sha(root/'reader-manifest.json')}
(root/'packet.json').write_text(json.dumps(receipt,indent=2)+'\n',newline='\n');print(json.dumps(receipt))
