import ctypes,json,pathlib,hashlib,shutil,statistics
from PIL import Image,ImageDraw
ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x4000)
r=pathlib.Path('D:/rivals-agent-evidence/idm-hud-alignment-20260929');p=pathlib.Path('docs/evidence/idm-hud-alignment-20260929');m=json.loads((r/'feed-decode.json').read_text())
EVENTS=[{'incoming':'S.t4rfir3 -> ShadowFox594','preceding':'Stylestw -> Paainter','live':[139.688,139.696],'replay':[109.071,109.079],'identity_at':{'live':140.004,'replay':109.396}}, {'incoming':'cowboyboopbop -> Yoitscolin','preceding':'S.t4rfir3 -> ShadowFox594','live':[140.954,140.963],'replay':[110.338,110.346],'identity_at':{'live':142.004,'replay':111.396}}, {'incoming':'cowboyboopbop -> Carsonred','preceding':'cowboyboopbop -> Yoitscolin','live':[145.188,145.196],'replay':[114.588,114.596],'identity_at':{'live':145.404,'replay':115.396}}, {'incoming':'cowboyboopbop -> taytpwk','preceding':'cowboyboopbop -> Carsonred','live':[146.896,146.904],'replay':[116.288,116.296],'identity_at':{'live':147.004,'replay':116.396}}, {'incoming':'SmellyArea6 -> Weird dude','preceding':'cowboyboopbop -> taytpwk','live':[150.404,150.413],'replay':[119.804,119.813],'identity_at':{'live':151.004,'replay':120.396}}]
for e in EVENTS:
 e['status']='owner_visually_verified';e['human_verified']=False;e['boundary_definition']='First recorded frame where the existing identity-matched preceding row moves downward; incoming identity verified later. Not first fade-in of incoming row.';e['crops']={}
 for tag in ['live','replay']:
  w=next(x for x in m if x['label']==tag+'-feed');e['crops'][tag]=[]
  for t in e[tag]+[e['identity_at'][tag]]:
   s=min(w['samples'],key=lambda s:abs(s['pts']-t));assert abs(s['pts']-t)<.002
   dest=p/'crops'/f"{tag}-feed-{s['pts']:.3f}.png";shutil.copyfile(s['path'],dest);e['crops'][tag].append({'path':str(dest.relative_to(p)).replace('\\','/'),'pts':s['pts'],'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
 e['offset_midpoint']=statistics.mean(e['replay'])-statistics.mean(e['live'])
 e['offset_interval']=[e['replay'][0]-e['live'][1],e['replay'][1]-e['live'][0]]
median=statistics.median(e['offset_midpoint'] for e in EVENTS)
for e in EVENTS:e['residual_about_own_median_seconds']=e['offset_midpoint']-median
out={'scope':'Development owner video-only annotations. Independent human verification pending.','matched_shifted_arrivals':5,'empty_feed_arrivals_excluded':1,'empty_feed_arrival':'Stylestw -> Paainter, first feed entry near live 136-137 s; no preceding row to shift','killfeed_median_offset_seconds':median,'timer_offset_seconds':json.loads((p/'timer-fit.json').read_text())['slope1_median_offset_seconds'],'max_abs_residual_seconds':max(abs(e['residual_about_own_median_seconds']) for e in EVENTS),'criterion':'Residual about the kill-feed own per-span median, <=2 recorded 120-fps frames (16.6667 ms), unchanged. Timer fit is never shifted to agree.','pass':all(abs(e['residual_about_own_median_seconds'])<=2/120 for e in EVENTS),'events':EVENTS}
out['killfeed_minus_timer_effect_seconds']=median-out['timer_offset_seconds']
(p/'feed-annotations.json').write_text(json.dumps(out,indent=2))
# Paired native onset contacts: each event, live/replay last-unshifted and first-shifted.
sheet=Image.new('RGB',(1080,5*430),'#141820');draw=ImageDraw.Draw(sheet)
for k,e in enumerate(EVENTS):
 y=k*430;draw.text((5,y+4),e['incoming']+'  preceding: '+e['preceding'],fill='yellow')
 for col,tag in enumerate(['live','replay']):
  for row,s in enumerate(e['crops'][tag][:2]):
   x=col*540;yy=y+25+row*200;sheet.paste(Image.open(p/s['path']),(x,yy+20));draw.text((x+4,yy+3),f"{tag} {s['pts']:.3f} {'last unshifted' if row==0 else 'first shifted'}",fill='white')
sheet.save(p/'contacts'/'paired-feed-boundaries.png');shutil.copyfile(r/'fade-context.png',p/'contacts'/'fade-context.png')
context=[]
for w in m:
 if 'context' not in w['label']:continue
 s=w['samples'][0];h=hashlib.sha256(pathlib.Path(s['path']).read_bytes()).hexdigest();context.append({'source':w['source'],'pts':s['pts'],'path':s['path'],'sha256':h})
 if w['label'] in ['live-context-155.6','replay-context-125.0','live-context-156.4','replay-context-125.8']:
  dest=p/'crops'/(w['label']+'.png');shutil.copyfile(s['path'],dest);context[-1]['packet_path']=str(dest.relative_to(p)).replace('\\','/')
ctx={'observation':'Live 155.604 and 156.004 show a scoreboard overlay; not a death. Replay 125.004 and 125.404 retain cowboyboopbop Spider-Man POV and have no scoreboard. Both sides show the same roof/wall and 250 HP around it. Live scoreboard gone by 156.404. Sparse context samples do not certify every frame or exact overlay edges.','decision':'Keep pre-result conservative selection: exclude live [155,160) / replay [124.39,129.39); no post-fade anchors are fitted.','samples':context}
(p/'context-annotations.json').write_text(json.dumps(ctx,indent=2));print({k:v for k,v in out.items() if k!='events'})
