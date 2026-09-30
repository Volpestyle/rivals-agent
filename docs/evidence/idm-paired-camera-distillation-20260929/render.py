"""Render aggregate results only; does not access prepared stores or fit."""
import json, shutil
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
P=Path(__file__).parent; O=Path('D:/rivals-agent-evidence/idm-paired-camera-distillation-20260929')
r=json.loads((O/'result.json').read_text())
im=Image.new('RGB',(1200,720),'white');d=ImageDraw.Draw(im)
f=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',20); small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',16)
d.text((35,20),'Frozen full03 residual probe: held-out teacher agreement only',font=f,fill='black')
d.text((35,52),'Fit 120–145 s; report 145–155 s. Complete contexts purged. Original joint masks.',font=small,fill='black')
colors={'unchanged':'#e18022','affine':'#8364ba','residual':'#2075ba','zero':'#666666'}
for j,a in enumerate(('yaw_deg','pitch_deg')):
    top=105+j*295; bins=r['per_second']; maximum=max(b['axes'][a][m]['mae'] for b in bins for m in colors)*1.1
    d.text((35,top),a+' — MAE versus LIVE teacher (degrees / interval)',font=f,fill='black')
    for k in range(5):
        y=top+210-k*40; d.line((80,y,790,y),fill='#dddddd');d.text((35,y-10),f'{maximum*k/4:.2f}',font=small,fill='black')
    for m,col in colors.items():
        points=[(100+(b['second']-145)*70,top+210-160*b['axes'][a][m]['mae']/maximum) for b in bins]
        d.line(points,fill=col,width=3)
        for x,y in points:d.ellipse((x-3,y-3,x+3,y+3),fill=col)
    for sec in range(145,155):d.text((90+(sec-145)*70,top+220),str(sec),font=small,fill='black')
    t=r['scores'][a]['teacher'];d.text((825,top+38),f'Teacher RMS {t["rms"]:.3f}',font=small,fill='black')
    for k,(m,col) in enumerate(colors.items()):
        q=r['scores'][a][m];d.text((825,top+68+k*32),f'{m}: MAE {q["mae"]:.3f}; RMS {q["rms"]:.3f}',font=small,fill=col)
    d.text((825,top+205),'PASS' if r['gates'][a]['positive'] else 'DO NOT EXPAND',font=f,fill='#237b32' if r['gates'][a]['positive'] else '#b32b2b')
d.text((35,685),'Prior-exposed within-pair evidence. No physical accuracy, generalization or Gate 2 credit.',font=small,fill='black')
im.save(P/'comparison.png')
for n in ('result.json','parameters.json','run-start.json','fit-start.json'):shutil.copyfile(O/n,P/n)
lines=['# Frozen-feature replay-to-live residual probe','', '**Provisional, unadmitted, prior-exposed development evidence. Teacher agreement only.**','']
positive=[a for a,g in r['gates'].items() if g['positive']]
lines += ['The residual passes the preregistered agreement and movement checks for '+(', '.join(positive) if positive else 'neither axis')+'. Failed axes must not be expanded. This discrepancy does not prove replay is worse: the LIVE prediction is a frozen teacher, not physical truth.','', '![Held-out comparison](comparison.png)','', '| Axis / method | MAE | RMSE | Mean absolute | RMS | Centered std | Signed bias | Active sign recall |','|---|---:|---:|---:|---:|---:|---:|---:|']
for a,q in r['scores'].items():
    for m,v in q.items():lines.append(f'| {a} / {m} | {v["mae"]:.4f} | {v["rmse"]:.4f} | {v["mean_abs"]:.4f} | {v["rms"]:.4f} | {v["centered_std"]:.4f} | {v["signed_bias"]:.4f} | {v["sign_correct"]}/{v["active_n"]} ({v["sign_recall"]:.1%}) |')
lines += ['', 'All magnitudes are original head degrees per interval. Active means |teacher| ≥0.1; sign recall also requires predicted magnitude ≥0.1. Zero therefore cannot pass the movement gate. Full active magnitude values and per-axis gate decisions are in [result.json](result.json).','', '| Block | Complete contexts | Joint known |','|---|---:|---:|']
for g,c in r['counts'].items():lines.append(f'| {g} | {c["complete_contexts"]} | {c["joint_known"]} |')
lines += ['', 'Both axes and all four methods use the same joint-known held-out rows. Original per-axis LIVE/replay coverage is in result.json. Fit/report native frame ordinal sets are disjoint in both stores; complete 17-frame contexts crossing live 145 s are purged. Nominal -30.600 s mapping is unchanged, with no offset tuning. The reviewed v3 pairing retains its prior ±1-frame completeness requirement, although this probe uses nominal replay only.','', 'The [preregistration](preregistration.json) and [freeze](freeze.json) were written before extraction/fitting. One float64 multi-output ridge residual solve (lambda=1.0, unpenalized intercept) used replay camera-head penultimate 128 features. Normalization and the per-axis affine comparator used fit rows only. Full03 stayed eval/frozen; original `_camera` gains/masks, including pitch fix A, were retained. Corrected methods inherit original masks. No support-a3, training of full03, checkpoint promotion, label export, new decode, cloud spend or sealed access. Cost $0.','', 'Read access reused the unchanged reviewed v3 boundary, review gate, fixed prepared stores, pairing, checkpoint loader and module-origin checks. Source pins/denylist and all four store hashes were checked. The loader authenticates then rereads pinned JSON as documented in v3; this probe does not add a new corpus path. Parameters are scientific non-deployment coefficients, not a promoted checkpoint. No per-row feature or teacher target cache was exported.','', 'Synthetic controls verified the split purge, ridge constant-target intercept and zero/sign failure before the single real-data run. Output start records prevent retries. Runtime module pins, checkpoint, prepared/review hashes, feature digest and completion time are recorded in result.json. CPU BelowNormal, Torch 2 intraop / 1 interop threads.','', 'The report block was already inspected and scored in the previous diagnostic; it is temporally separated, not blind or independent generalization. Prior eligibility inspection covered 140 quarter-second paired samples and selected native neighbours, not all frames visually; computational PTS/context checks covered every row. Reused continuity/identity/1x/focus/UI findings remain as pinned in the earlier review. No logger video timing or session camera-unit calibration was established, so no physical accuracy is claimed. Shared truth error does not automatically cancel. No Gate 2 credit; V-C, V-Q and sealed groups remain closed.','', 'The predecessor alignment sensitivity belongs to [the paired diagnostic](../idm-paired-camera-result-20260929/README.md); it is unchanged evidence, not a timing search in this fit. This single exposed pair cannot establish whether replay rendering is worse or whether a correction generalizes. Stop after this fit/report.']
(P/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
