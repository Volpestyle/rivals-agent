import json,pathlib,ctypes,statistics
ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x4000)
p=pathlib.Path('docs/evidence/idm-hud-alignment-20260929');a=json.loads((p/'timer-annotations.json').read_text())
# Selection is fixed in span-selection.json BEFORE residuals. Value identity is the only join key.
L={ (x['old'],x['new']):x for x in a['sources']['live'] if x['status']=='owner_visually_verified' and x['first_new']<155 }
R={ (x['old'],x['new']):x for x in a['sources']['replay'] if x['status']=='owner_visually_verified' and x['first_new']<124.39 }
assert len(L)==len(R)==35 and L.keys()==R.keys()
pairs=[]
for key in L:
 l,r=L[key],R[key];lm=(l['last_old']+l['first_new'])/2;rm=(r['last_old']+r['first_new'])/2
 pairs.append({'old':key[0],'new':key[1],'live_bracket':[l['last_old'],l['first_new']],'replay_bracket':[r['last_old'],r['first_new']],'live_midpoint':lm,'replay_midpoint':rm,'offset_midpoint':rm-lm,'offset_interval':[r['last_old']-l['first_new'],r['first_new']-l['last_old']]})
median=statistics.median(x['offset_midpoint'] for x in pairs)
for x in pairs:x['slope1_residual_seconds']=x['offset_midpoint']-median
xm=statistics.mean(x['live_midpoint'] for x in pairs);ym=statistics.mean(x['replay_midpoint'] for x in pairs)
slope=sum((x['live_midpoint']-xm)*(x['replay_midpoint']-ym) for x in pairs)/sum((x['live_midpoint']-xm)**2 for x in pairs)
result={'scope':'Development conditional timer fit; continuity/context and human verification remain pending. No Gate 2 acceptance.','selected_span':'A: live [120,155), replay [89.39,124.39)','join':'Unique displayed old/new value pair in the same observed MM:SS countdown, not timestamp index','timestamp_convention':'Midpoint of (last-old PTS,first-new PTS] bracket. Millisecond encoded PTS preserved; no resampling.','timer_anchors':len(pairs),'slope1_median_offset_seconds':median,'free_slope':slope,'free_slope_intercept_seconds':ym-slope*xm,'free_slope_abs_deviation':abs(slope-1),'max_abs_timer_residual_seconds':max(abs(x['slope1_residual_seconds']) for x in pairs),'recorded_fps':120,'one_frame_seconds':1/120,'two_frames_seconds':2/120,'criteria':{'timer_support':{'pass':len(pairs)>=30,'criterion':'>=30 per span'},'free_slope':{'pass':abs(slope-1)<=.001,'criterion':'abs(slope-1)<=0.001'},'segment_offset_agreement':{'pass':None,'reason':'Only one MM:SS timer segment before conservative fade exclusion; no between-segment comparison exists. Do not count a vacuous check as observed agreement.'},'killfeed_residual':{'pass':None,'reason':'New feed crops await lead decode release'}},'paired_timer_anchors':pairs}
(p/'timer-fit.json').write_text(json.dumps(result,indent=2))
for tag,rows in a['sources'].items():
 for row in rows:row['use_for_fit']=row['status']=='owner_visually_verified' and (row['old'],row['new']) in L
(p/'timer-annotations.json').write_text(json.dumps(a,indent=2))
print({k:v for k,v in result.items() if k not in ['paired_timer_anchors','criteria']})
