"""Reviewed development-only preparation and camera prediction agreement.

Two commands: prepare (no inference), score (requires explicit context review).
No logger truth scoring, admission, labels, fitting or checkpoint writes.
"""
import bisect
import csv
import hashlib
import json
import math
import re
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

PACKET = Path(__file__).resolve().parent
ROOT = PACKET.parents[2]
OUT = Path('D:/rivals-agent-evidence/idm-paired-camera-development-20260929')
AUDIT = PACKET / 'access-audit.json'
LIVE = (120.0, 155.0)
REPLAY = (89.39, 124.39)
OFFSET = -30.600
CHECKPOINT = ROOT / 'data/idm/cloud-20260927/full03-result-collected/artifacts/fit/refit.pt'
CHECKPOINT_SHA = 'f681da9f3a4b8db6f7d19566172b02db776e4bcfac3381be744786179aa55dde'
CLOSURE = ROOT / 'data/idm/cloud-20260927/runtime-full03-05a61b4/code/cloud/idm_payload'
OFFSETS = tuple(range(-16, 17, 2))

def require(value, reason):
    if not value:
        raise RuntimeError(reason)

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def write(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write('\n')

def nearest(pts, t):
    j = bisect.bisect_left(pts, t)
    choices = [k for k in (j - 1, j) if 0 <= k < len(pts)]
    return min(choices, key=lambda k: (abs(pts[k] - t), k))

def pairs(live, replay, intervals):
    """Same explicit examples for all shifts; every context stays inside reviewed intervals."""
    result = []
    for i in range(16, len(live) - 16, 2):
        li = [i + o for o in OFFSETS]
        ri = [nearest(replay, live[k] + OFFSET) for k in li]
        if not all(abs(replay[j] - (live[k] + OFFSET)) <= 0.0046 for k, j in zip(li, ri)):
            continue
        if not all(b - a == 2 for a, b in zip(ri, ri[1:])):
            continue
        if min(ri) < 1 or max(ri) + 1 >= len(replay):
            continue
        valid = any(a <= live[i - 16] and live[i + 16] < b for a, b in intervals)
        if not valid:
            continue
        # Explicit exact intersection and completeness including +/- native-frame variants.
        if not (LIVE[0] <= live[li[0]] and live[li[-1]] < LIVE[1]
                and REPLAY[0] <= replay[ri[0] - 1] and replay[ri[-1] + 1] < REPLAY[1]):
            continue
        result.append({'live': li, 'replay': ri, 't': live[i],
                       'duration_ns': round((live[i] - live[i - 2]) * 1e9),
                       'alignment_ms': 1000 * (replay[ri[8]] - live[i] - OFFSET)})
    return result

def metric(a, b):
    require(len(a) == len(b), 'metric pair count mismatch')
    differences = [x - y for x, y in zip(a, b)]
    n = len(differences)
    return {'n': n, 'mae_deg': sum(abs(x) for x in differences) / n if n else None,
            'rmse_deg': math.sqrt(sum(x*x for x in differences) / n) if n else None}

def boundary():
    # Authenticate code/evidence closure before any media/ledger/checkpoint access.
    for path, pin in read(PACKET / 'SHA256SUMS.json').items():
        require(sha(ROOT / path) == pin, 'phase-two frozen dependency changed: ' + path)
    sys.path.insert(0, str(ROOT))
    from agent import human_intake as I
    deny = I.load_denylist(ROOT / 'data/human/sealed-denylist.v2.json',
                          sha256_pin=read(AUDIT)['denylist_sha256'])
    audit = read(AUDIT)
    sources = [(audit['metadata']['session_id'], Path(list(audit['pins'])[0])),
               ('20260926T161008-331Z-116800-2', Path(list(audit['pins'])[1]))]
    for sid, path in sources:
        for row in deny['sessions']:
            require(sid not in (row.get('session_id'), row.get('session_group'))
                    and audit['pins'][str(path)] != row['media_sha256']
                    and str(path).replace('\\', '/').casefold() != str(row.get('media_path', '')).replace('\\', '/').casefold(),
                    'sealed identity: STOP')
    for path, pin in audit['pins'].items():
        require(sha(path) == pin, 'source/TOFU ledger changed: STOP')
    return audit, sources

def decode(name, path, span):
    # At most one decoder, two codec threads, one filter thread, no hardware acceleration.
    processes = subprocess.check_output(['tasklist', '/FO', 'CSV'], text=True).casefold()
    require('marvel-win64-shipping.exe' not in processes and 'obs64.exe' not in processes,
            'game or OBS open: decode STOP')
    rgb = OUT / (name + '.rgb')
    log = OUT / (name + '-decode.log')
    require(not rgb.exists() and not log.exists(), 'refuse decoder rerun')
    graph = ('showinfo,scale=in_range=tv:in_color_matrix=bt709:out_range=pc:'
             'flags=accurate_rnd+bitexact+full_chroma_int,format=rgb24,'
             'scale=448:252:flags=area+accurate_rnd+bitexact')
    command = ['ffmpeg', '-nostdin', '-hide_banner', '-threads', '2', '-filter_threads', '1',
               '-ss', str(span[0]), '-i', str(path), '-t', str(span[1]-span[0]),
               '-an', '-sn', '-vf', graph, '-fps_mode', 'passthrough', '-pix_fmt', 'rgb24',
               '-f', 'rawvideo', '-n', str(rgb)]
    with log.open('x', encoding='utf-8') as f:
        subprocess.run(command, stderr=f, stdout=subprocess.DEVNULL, check=True,
                       creationflags=0x4000 | 0x08000000)  # BELOW_NORMAL_PRIORITY_CLASS + CREATE_NO_WINDOW
    pts = [span[0] + float(m.group(1)) for m in re.finditer(
        r'\bn:\s*\d+\s+pts:\s*-?\d+\s+pts_time:([-\d.e+]+)', log.read_text(encoding='utf-8'))]
    count, remainder = divmod(rgb.stat().st_size, 252*448*3)
    require(remainder == 0 and count > 0 and count <= len(pts) <= count+2, 'RGB/showinfo mismatch')
    # FFmpeg can log filter lookahead past output -t; only emitted frames are mapped.
    pts = pts[:count]
    require(pts and all(span[0] <= t < span[1] for t in pts), 'decode escaped frozen span')
    require(all(0.007 <= b-a <= 0.010 for a, b in zip(pts, pts[1:])), 'native PTS discontinuity')
    require(rgb.stat().st_size == len(pts)*252*448*3, 'RGB/PTS count mismatch')
    import numpy as np
    pixels = np.memmap(rgb, dtype=np.uint8, mode='r', shape=(len(pts), 252, 448, 3))
    grey = OUT / (name + '.grey')
    with grey.open('xb') as f:
        for frame in pixels:
            v = frame.astype(np.uint16)
            f.write(((77*v[:,:,0]+150*v[:,:,1]+29*v[:,:,2]+128)>>8).astype(np.uint8).tobytes())
    return {'pts': pts, 'rgb_sha256': sha(rgb), 'grey_sha256': sha(grey), 'command': command,
            'platform': sys.platform, 'graph': graph}

def prepare():
    audit, sources = boundary()
    ledger = Path(list(audit['pins'])[2]).parent
    from agent import human_demos as H
    with (ledger / 'inputs.jsonl').open(encoding='utf-8') as f:
        events = tuple(H._event(json.loads(line)) for line in f)
    with (ledger / 'frames.csv').open(encoding='utf-8', newline='') as f:
        packets = [{k: int(v) for k, v in row.items()} for row in csv.DictReader(f)]
    H._validate_raw(audit['metadata'], events, packets)
    # No fitted muxer offset or degrees labels. CTS and recorded PTS retained for reviewed QC only.
    ui = [e.payload for e in events if e.type == 'key' and e.payload['vk'] in
          (9, 13, 27, 66, 72, 84, 112, 18, 164, 165, 91, 92)]
    provenance = {'designation': 'provisional, unadmitted development evidence',
                  'accuracy_established': False, 'capture_latency_calibrated': False,
                  'ui_events': ui, 'focus_events': audit['state_events'],
                  'packet_timing': [{'pts_seconds': p['pts']*p['timebase_num']/p['timebase_den'],
                                     'composition_ns': p['composition_ns']} for p in packets
                                    if 118 <= p['pts']*p['timebase_num']/p['timebase_den'] < 157],
                  'timing_policy': 'No logger accuracy. Native video PTS pairing only; QC reviewer must resolve UI/focus/POV/1x.'}
    write(OUT / 'timing-qc.json', provenance)
    stores = {}
    for (name, span), (_, path) in zip((('live', LIVE), ('replay', REPLAY)), sources):
        stores[name] = decode(name, path, span)
    write(OUT / 'prepared.json', stores)
    # Full-width native-derived camera views for semi-manual continuous review: all frames, not sparse samples.
    # Reviewers can step raw RGB frames using their pinned PTS; no eligibility inferred from model output.
    print('Prepared frozen-span RGB/grey and timing QC; score requires a pinned explicit review.json.')

def check_review(review, prepared_sha):
    """Pure eligibility gate; no file access or model imports."""
    require(review.get('reviewer') and review.get('prepared_sha256') == prepared_sha, 'missing reviewed provenance')
    for key in ('same_identity', 'continuous_pov', 'replay_1x', 'focused', 'ui_excluded'):
        require(review.get(key) is True, 'unresolved ' + key + ': STOP')
    require(review.get('evidence'), 'missing context/focus/UI evidence: STOP')
    intervals = review['valid_live_intervals']
    require(intervals and all(LIVE[0] <= a < b <= LIVE[1] for a, b in intervals), 'review interval widening')
    require(all(a[1] <= b[0] for a,b in zip(intervals, intervals[1:])), 'overlapping review intervals')
    return intervals

def module_provenance(train, targets, model):
    for module in (train, targets, model):
        require(Path(module.__file__).resolve().is_relative_to(CLOSURE.resolve()),
                'policy module outside original closure: STOP')
    from agent import human_demos, human_intake
    import agent
    return {module.__name__: {'path': str(Path(module.__file__).resolve()),
                              'sha256': sha(module.__file__)}
            for module in (train, targets, model, agent, human_demos, human_intake)}

def score(review_path, review_pin):
    boundary()
    require(review_path.resolve() == (OUT / 'review.json').resolve(), 'review path outside fixed output: STOP')
    require(sha(review_path) == review_pin, 'context review pin mismatch')
    review = read(review_path)
    intervals = check_review(review, sha(OUT / 'prepared.json'))
    stores = read(OUT / 'prepared.json')
    require(set(stores) == {'live','replay'}, 'unexpected prepared source')
    for name, info in stores.items():
        require(sha(OUT / (name+'.grey')) == info['grey_sha256'], 'grey store changed')
        require(sha(OUT / (name+'.rgb')) == info['rgb_sha256'], 'RGB store changed')
    rows = pairs(stores['live']['pts'], stores['replay']['pts'], intervals)
    require(rows, 'no paired complete context')
    require(sha(CHECKPOINT) == CHECKPOINT_SHA, 'checkpoint mismatch')
    # Original full03 policy closure; pinned repo agent modules remain loaded. No support-a3.
    sys.path.insert(0, str(CLOSURE))
    import numpy as np
    import torch
    from policy.idm import train
    from policy import idm_targets
    from policy.idm import model as model_module
    runtime_provenance = module_provenance(train, idm_targets, model_module)
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    model, payload = train.load_checkpoint(CHECKPOINT, device='cpu')
    require(model.config.window == 8 and model.config.height == 252 and model.config.width == 448, 'unexpected model')
    cal = {'yaw_deg_per_count': 0.0330738, 'pitch_deg_per_count': 0.0330738}
    # Reference calibration used solely to reproduce original predictor abstention; not a session truth claim.
    arrays = {name: np.memmap(OUT/(name+'.grey'), dtype=np.uint8, mode='r',
              shape=(len(info['pts']),252,448)) for name,info in stores.items()}
    predictions = {'live': [], 'replay_minus1': [], 'replay_0': [], 'replay_plus1': []}
    with torch.inference_mode():
        for row in rows:
            for name, store, indices in (
                ('live','live',row['live']),
                ('replay_minus1','replay',[i-1 for i in row['replay']]),
                ('replay_0','replay',row['replay']),
                ('replay_plus1','replay',[i+1 for i in row['replay']])):
                motion = np.diff(arrays[store][indices].astype(np.float32)/255.0, axis=0)
                _, camera = model(torch.from_numpy(motion[None]), torch.zeros((1,6,80,200)))
                raw = camera[0].tolist()
                predictions[name].append(train._camera(raw[0],raw[1],raw[2:],
                    {'t0_ns':0,'t1_ns':row['duration_ns']}, cal))
    scores = {}
    for axis in ('yaw_deg','pitch_deg'):
        common = [i for i in range(len(rows)) if all(predictions[k][i][axis] is not None for k in predictions)]
        scores[axis] = {'eligible':len(rows), 'common_answered_all_shifts':len(common),
            'coverage':{k:sum(p[axis] is not None for p in v)/len(rows) for k,v in predictions.items()},
            'paired_agreement':{k:metric([predictions['live'][i][axis] for i in common],
                                        [v[i][axis] for i in common]) for k,v in predictions.items() if k!='live'},
            'distance_to_zero_not_accuracy':{k:metric([v[i][axis] for i in common],[0]*len(common)) for k,v in predictions.items()}}
    write(OUT/'agreement.json', {'designation':'provisional, unadmitted development evidence',
        'accuracy':None, 'reason':'independent video/input timing and session camera truth calibration not established',
        'shared_truth_error':'Does not automatically cancel; no logger accuracy conclusion is drawn.',
        'checkpoint':CHECKPOINT_SHA, 'review_sha256':review_pin, 'reference_mask_gain':cal,
        'runtime_modules': runtime_provenance,
        'eligible_count':len(rows), 'scores':scores, 'paired_rows':rows, 'predictions':predictions,
        'interpretation':'Prediction agreement cannot establish whether replay worsens accuracy or model transfer.'})
    # Legible static comparison using per-second means, same common sample set.
    with (OUT/'comparison.csv').open('x',encoding='utf-8',newline='') as f:
        writer=csv.writer(f); writer.writerow(['live_seconds','axis','live_mean','replay_minus1_mean','replay_0_mean','replay_plus1_mean','common_n'])
        for second in range(120,155):
            for axis in ('yaw_deg','pitch_deg'):
                ids=[i for i,r in enumerate(rows) if second<=r['t']<second+1 and all(predictions[k][i][axis] is not None for k in predictions)]
                writer.writerow([second,axis,*[sum(predictions[k][i][axis] for i in ids)/len(ids) if ids else '' for k in predictions],len(ids)])
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="960" height="520" viewBox="0 0 960 520">',
           '<rect width="960" height="520" fill="white"/>',
           '<text x="30" y="25" font-family="sans-serif" font-size="17">Provisional unadmitted development: prediction agreement only</text>',
           '<text x="30" y="48" font-family="sans-serif" font-size="13">Blue live; green replay 0; orange replay -1; purple replay +1 native frame. Same common examples.</text>']
    for panel,axis in enumerate(('yaw_deg','pitch_deg')):
        dots=[]
        for second in range(120,155):
            ids=[i for i,r in enumerate(rows) if second<=r['t']<second+1 and all(predictions[k][i][axis] is not None for k in predictions)]
            if ids:
                dots.extend((second,k,sum(predictions[k][i][axis] for i in ids)/len(ids)) for k in predictions)
        scale=max([abs(v) for _,_,v in dots]+[0.01])
        middle=160+panel*220
        svg.append(f'<text x="30" y="{middle-75}" font-family="sans-serif" font-size="14">{axis}: one-second means, +/-{scale:.3f} degrees per interval; dots omit unknowns</text>')
        svg.append(f'<path d="M40 {middle} H930" stroke="#999"/>')
        colors={'live':'#1671c5','replay_0':'#23833d','replay_minus1':'#d07717','replay_plus1':'#8a40b3'}
        for second,k,v in dots:
            svg.append(f'<circle cx="{50+(second-120)*25}" cy="{middle-65*v/scale:.2f}" r="3" fill="{colors[k]}"/>')
    svg.append('<text x="30" y="495" font-family="sans-serif" font-size="13">Live video time 120–154 s. Zero line is a reference, not truth. No accuracy or transfer conclusion.</text></svg>')
    with (OUT/'comparison.svg').open('x',encoding='utf-8') as f:
        f.write('\n'.join(svg))
    print('One unchanged-full03 paired prediction-agreement diagnostic complete; no accuracy/Gate 2 claim.')

if __name__ == '__main__':
    require(sys.platform == 'win32', 'this bounded decoder wrapper is Windows-only')
    import ctypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    kernel.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_ulong)
    require(kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x4000), 'cannot set BelowNormal')
    if sys.argv[1:] == ['prepare']:
        prepare()
    elif len(sys.argv) == 4 and sys.argv[1] == 'score':
        score(Path(sys.argv[2]), sys.argv[3])
    else:
        raise RuntimeError('Usage: paired.py prepare | paired.py score REVIEW.json SHA256')
