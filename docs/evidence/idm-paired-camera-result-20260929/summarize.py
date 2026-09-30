"""Summarize the single frozen scorer output; no model/source/ledger access."""
import ctypes
import hashlib
import json
import math
import statistics
import sys
from pathlib import Path
sys.dont_write_bytecode=True
OUT=Path('D:/rivals-agent-evidence/idm-paired-camera-development-20260929')

def metric(a,b):
    d=[x-y for x,y in zip(a,b)]
    return {'n':len(d),'mae_deg':sum(abs(x) for x in d)/len(d) if d else None,
            'rmse_deg':math.sqrt(sum(x*x for x in d)/len(d)) if d else None}

def main():
    k=ctypes.WinDLL('kernel32');k.GetCurrentProcess.restype=ctypes.c_void_p
    k.SetPriorityClass.argtypes=(ctypes.c_void_p,ctypes.c_ulong)
    assert k.SetPriorityClass(k.GetCurrentProcess(),0x4000)
    data=json.loads((OUT/'agreement.json').read_text(encoding='utf-8'))
    predictions=data['predictions'];rows=data['paired_rows'];summary={};curves={}
    for axis in ('yaw_deg','pitch_deg'):
        ids=[i for i in range(len(rows)) if all(predictions[n][i][axis] is not None for n in predictions)]
        live=[predictions['live'][i][axis] for i in ids]
        nominal=[predictions['replay_0'][i][axis] for i in ids]
        assert metric(live,nominal)==data['scores'][axis]['paired_agreement']['replay_0']
        differences=sorted(abs(x-y) for x,y in zip(live,nominal))
        mean_abs_live=sum(abs(x) for x in live)/len(ids) if ids else None
        summary[axis]={'same_common_n':len(ids),'nominal_agreement':metric(live,nominal),
            'signed_replay_minus_live_mean_deg':sum(y-x for x,y in zip(live,nominal))/len(ids) if ids else None,
            'median_absolute_difference_deg':statistics.median(differences) if ids else None,
            'p90_absolute_difference_deg':differences[math.ceil(.9*len(ids))-1] if ids else None,
            'nominal_mae_over_live_mean_absolute_prediction':metric(live,nominal)['mae_deg']/mean_abs_live if mean_abs_live else None,
            'replay_shift_only':{n:metric(nominal,[predictions[n][i][axis] for i in ids])
                for n in ('replay_minus1','replay_plus1')}}
        curves[axis]={n:[] for n in ('replay_minus1','replay_0','replay_plus1')}
        for second in range(120,155):
            subset=[i for i in ids if second<=rows[i]['t']<second+1]
            for name in curves[axis]:
                error=metric([predictions['live'][i][axis] for i in subset],[predictions[name][i][axis] for i in subset])
                curves[axis][name].append({'second':second,'n':len(subset),'mae_deg':error['mae_deg']})
    result={'designation':'provisional, unadmitted development evidence',
            'agreement_sha256':hashlib.sha256((OUT/'agreement.json').read_bytes()).hexdigest(),
            'materiality_threshold':'not prespecified; describe numerical effect and sensitivity, not a formal pass/fail',
            'statistics':summary,'per_second_absolute_disagreement':curves}
    with (OUT/'summary.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    # Static artifact chart in the same native head units; all eligible common rows, no selected examples.
    svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="600" viewBox="0 0 1000 600">',
         '<rect width="1000" height="600" fill="white"/>',
         '<text x="30" y="28" font-family="sans-serif" font-size="20">Full03: live / replay camera prediction disagreement</text>',
         '<text x="30" y="52" font-family="sans-serif" font-size="14">Provisional unadmitted development. Agreement only; no logger accuracy or Gate 2 credit.</text>',
         '<text x="30" y="74" font-family="sans-serif" font-size="14">Replay -1 native frame: orange    nominal: green    +1 native frame: purple</text>']
    colors={'replay_minus1':'#d07917','replay_0':'#168243','replay_plus1':'#8741bd'}
    for panel,axis in enumerate(('yaw_deg','pitch_deg')):
        top=115+panel*225;bottom=top+150
        vals=[p['mae_deg'] for series in curves[axis].values() for p in series if p['mae_deg'] is not None]
        ymax=max(vals+[.001])*1.1
        svg.append(f'<text x="70" y="{top-10}" font-family="sans-serif" font-size="16">{axis}: per-second mean absolute difference (degrees / interval), n={summary[axis]["same_common_n"]}</text>')
        for fraction in (0,.5,1):
            y=bottom-150*fraction
            svg.append(f'<path d="M80 {y} H950" stroke="#ddd"/><text x="25" y="{y+4}" font-family="sans-serif" font-size="12">{ymax*fraction:.3f}</text>')
        for name,points in curves[axis].items():
            poly=' '.join(f'{80+(p["second"]-120)*870/34:.1f},{bottom-150*p["mae_deg"]/ymax:.1f}' for p in points if p['mae_deg'] is not None)
            svg.append(f'<polyline points="{poly}" fill="none" stroke="{colors[name]}" stroke-width="2"/>')
        for second in (120,125,130,135,140,145,150,154):
            x=80+(second-120)*870/34
            svg.append(f'<text x="{x-10}" y="{bottom+20}" font-family="sans-serif" font-size="12">{second}</text>')
    svg.append('<text x="70" y="580" font-family="sans-serif" font-size="14">Live video time (seconds). Same common answered examples across every rendering and alignment shift.</text></svg>')
    with (OUT/'absolute-disagreement.svg').open('x',encoding='utf-8') as f:f.write('\n'.join(svg))
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
