"""Verify retained payload integrity, annotation/value joins and recorded criteria."""
import ctypes,json,pathlib,hashlib,statistics,math
from PIL import Image
ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x4000)
R=pathlib.Path('D:/rivals-agent-evidence/idm-hud-alignment-20260929');P=pathlib.Path('docs/evidence/idm-hud-alignment-20260929')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
base=json.loads((R/'decode.json').read_text());feed=json.loads((R/'feed-decode.json').read_text());files=[]
for w in base['decode']+feed:
 rows=w['samples'];lo,hi=base['frozen_intervals'][w['source']]
 assert all(lo<=s['pts']<hi for s in rows)
 assert all(a['pts']<b['pts'] for a,b in zip(rows,rows[1:]))
 for s in rows:
  path=pathlib.Path(s['path']);files.append({'path':str(path),'pts':s['pts'],'bytes':path.stat().st_size,'sha256':sha(path)})
(R/'collection.json').write_text(json.dumps({'files':files},indent=2));print('retained files hashed',len(files),flush=True)
a=json.loads((P/'timer-annotations.json').read_text());count=0
for tag,rows in a['sources'].items():
 assert len(rows)==40
 for row in rows:
  if row['status']=='owner_visually_verified':
   assert row['first_new']>row['last_old'];assert row['old'] is not None and row['new'] is not None
  else:assert row['first_new'] is None and not row['use_for_fit']
  for s in row['crops']:
   pp=P/s['path'];assert sha(pp)==s['sha256'];assert Image.open(pp).size==(280,150);count+=1
f=json.loads((P/'feed-annotations.json').read_text())
for e in f['events']:
 for tag in ['live','replay']:
  cs=e['crops'][tag];assert [round(c['pts'],3) for c in cs[:2]]==e[tag]
  for c in cs:assert sha(P/c['path'])==c['sha256'];assert Image.open(P/c['path']).size==(540,180)
t=json.loads((P/'timer-fit.json').read_text());pairs=t['paired_timer_anchors'];assert len(pairs)==35
for pair in pairs:
 for tag,field in [('live','live_bracket'),('replay','replay_bracket')]:
  hits=[x for x in a['sources'][tag] if x['use_for_fit'] and (x['old'],x['new'])==(pair['old'],pair['new'])]
  assert len(hits)==1 and [hits[0]['last_old'],hits[0]['first_new']]==pair[field]
assert statistics.median(x['offset_midpoint'] for x in pairs)==t['slope1_median_offset_seconds']
assert statistics.median(x['offset_midpoint'] for x in f['events'])==f['killfeed_median_offset_seconds']
assert f['pass'] and f['max_abs_residual_seconds']<=2/120
assert t['criteria']['free_slope']['pass'] and t['timer_anchors']>=30
assert all(not x['human_verified'] for rows in a['sources'].values() for x in rows)
# Compact provenance pins full D: manifests without committing raw PNGs.
provenance={'retained_root':str(R),'decode_manifest_sha256':sha(R/'decode.json'),'feed_manifest_sha256':sha(R/'feed-decode.json'),'collection_manifest_sha256':sha(R/'collection.json'),'retained_file_count':len(files),'retained_bytes':sum(x['bytes'] for x in files),'denylist_sha256':base['denylist_sha256'],'sources':base['sources'],'metadata_only_source_identity':'Registry media digests retained; originals not fully rehashed during this bounded decode.','bands':[{'source':w['source'],'bounds':w.get('bounds',base['frozen_intervals'][w['source']]),'crop':w.get('crop'),'files':len(w['samples']),'first_pts':w['samples'][0]['pts'],'last_pts':w['samples'][-1]['pts']} for w in base['decode']+feed]}
(P/'provenance.json').write_text(json.dumps(provenance,indent=2))
(P/'verification.json').write_text(json.dumps({'result':'PASS packet integrity and selected-value join checks','native_retained_files_hashed':len(files),'timer_crop_references_verified':count,'feed_events':5,'timer_pairs':35,'all_crop_hashes_and_dimensions_match':True,'all_retained_pts_in_freeze_and_monotonic':True,'human_verification':'pending','limitations':'Integrity and arithmetic checks do not establish truth of annotations, full-span continuity or human verification.'},indent=2))
print('packet verification passed',flush=True)
