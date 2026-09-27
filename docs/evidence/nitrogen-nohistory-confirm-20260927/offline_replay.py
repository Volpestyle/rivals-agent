"""Pinned 30 s recorded-view replay. No live inputs or autonomous gameplay."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import torch

ROOT = Path('/Users/james/dev/range-bc-data/explore/nitrogen-nohistory-confirm-20260927')
CODE = ROOT / 'mac-code-88b231d'
sys.path.insert(0, str(CODE))
from policy.range_bc import cache, metrics, train, vocab
from policy.range_bc.confirm_encoder_recovery import completed_features
from policy.range_bc.explore_camera import predict_suite
from policy.range_bc.explore_chunks import ChunkPolicy
from policy.range_bc.explore_chunks_train import load_manifest
from policy.range_bc.explore_encoder import EncoderPolicy, FeatureArrays
from policy.range_bc.model import Config


def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def put(p, obj):
    with p.open('x') as f:
        json.dump(obj, f, indent=2, allow_nan=False)
        f.write('\n')


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) >= 10
    torch.set_num_threads(2)
    judged = json.loads((ROOT / 'mac-evaluation-a2b/judgement.json').read_text())
    # The pinned interval permits seed 1 only after the confirmation gate.
    assert judged['decision'] == 'CONFIRMED'
    interval_path = ROOT / 'replay-interval.json'
    interval = json.loads(interval_path.read_text())
    assert interval['session'] == '20260923T171533-187Z-33696-5'
    assert interval['display_start_row'] == 185 and interval['display_stop_row_exclusive'] == 1085
    out = ROOT / 'offline-replay'
    out.mkdir(exist_ok=False)
    arrays, dev = load_manifest(ROOT.parent / 'manifest-full.json',
        CODE / 'data/human/session-splits.corpus.json', CODE / 'data/human/sessions/tally.json')
    del arrays
    arr = next(a for a in dev if a.session.session_id == interval['session'])
    assert arr.session.sha256 == interval['steps_sha256']
    manifest = json.loads((ROOT.parent / 'manifest-full.json').read_text())
    item = next(x for x in manifest['dev'] if Path(x['steps']).stem == interval['session'])
    cache.open_cache(item['cache'], arr.session, verify_hashes=True)
    assert (interval['warmup_start_row'], interval['original_run_stop']) in arr.runs
    feature_root = completed_features(ROOT / 'recovery-features-stage.json',
        'd051df52812522d8973fec3b1e9a2dac5f1a37371cfdfd9798d553b53f66b23e',
        '14347004b5d12ed44a89d69961fcb2df7be8f1a34444460f145fee3c5797cf21')
    arr = copy.copy(arr)
    arr.runs = [(interval['warmup_start_row'], interval['display_stop_row_exclusive'])]
    feature_arr = FeatureArrays(arr, feature_root)
    h1 = ROOT.parent / 'modal30-attempt2/collected/h1'
    nitro = ROOT / 'evaluation-recovery/candidate-s1'
    assert sha(h1 / 'epoch-26.pt') == interval['incumbent_checkpoint_sha256']
    assert sha(nitro / 'epoch-26.pt') == interval['candidate_checkpoint_sha256']
    assert sha(h1 / 'evaluation.json') == 'bfda525a1ee17fc6fc22d1dce6296508744d57a0a0f72109c13a174da76435b0'
    assert sha(nitro / 'evaluation.json') == '1399b086450478335e9c9b63bb4d99d8cc028f0705ebaab6ba90211a5f9b783c'
    predictions, scores, live_masks = {}, {}, []
    for label, folder, factory, views in [('H1 incumbent', h1, ChunkPolicy, arr),
                                          ('NitroGen no history', nitro, EncoderPolicy, feature_arr)]:
        payload = torch.load(folder / 'epoch-26.pt', map_location='cpu', weights_only=True)
        model = factory(Config.from_dict(payload['recipe']['config']), 1).to('mps')
        model.load_state_dict(payload['model'])
        calibration = json.loads((folder / 'evaluation.json').read_text())['threshold_calibration']
        assert calibration['source'] == 'TRAIN teacher-forced predictions only'
        live = [calibration['actions'][n]['live'] for n in vocab.NAMES]
        live_masks.append(live)
        suite = predict_suite(model, [views], live, {
            ('train_chosen', 'median'): calibration['thresholds'],
            ('fixed_0.5', 'median'): [.5] * vocab.N}, device='mps', progress=print)
        scores[label] = {}
        for condition, modes in suite.items():
            values = modes['self'][0][32:]
            assert len(values) == interval['frames']
            scores[label]['/'.join(condition)] = {
                'metrics': metrics.evaluate([values], **metrics.SELF),
                'checks': metrics.selffed_checks([values], live)}
            if condition[0] == 'train_chosen':
                predictions[label] = [p for _, p in values]
                records = [r for r, _ in values]
        del model, suite
        torch.mps.empty_cache()
    assert live_masks[0] == live_masks[1]
    human = [r['target'] for r in records]
    predictions = {'James recorded': human, **predictions}
    put(out / 'predictions.json', {'interval_sha256': sha(interval_path),
        'caption': interval['caption'], 'source': interval['visual_source'],
        'thresholds': 'original TRAIN-calibrated; median camera', 'scores': scores,
        'predictions': predictions, 'row_ids': [r['row'] for r in records]})
    width, height = 1536, 800
    try:
        font = ImageFont.truetype('/System/Library/Fonts/Menlo.ttc', 18)
        title = ImageFont.truetype('/System/Library/Fonts/Menlo.ttc', 25)
    except OSError:
        font = ImageFont.load_default(size=18)
        title = ImageFont.load_default(size=25)
    ffmpeg = ['/opt/homebrew/bin/ffmpeg', '-v', 'error', '-nostdin', '-n', '-f', 'rawvideo',
        '-pix_fmt', 'rgb24', '-s', f'{width}x{height}', '-r', '30', '-i', '-', '-an',
        '-c:v', 'libx264', '-threads', '2', '-preset', 'fast', '-crf', '20', '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart', str(out / 'offline-predictions.mp4')]
    with (out / 'ffmpeg.log').open('x') as log:
        proc = subprocess.Popen(ffmpeg, stdin=subprocess.PIPE, stderr=log)
        try:
            for i, row in enumerate(range(185, 1085)):
                canvas = Image.new('RGB', (width, height), '#101722')
                d = ImageDraw.Draw(canvas)
                d.text((20, 15), 'OFFLINE PREDICTIONS / recorded frames, not model gameplay', font=title, fill='white')
                d.text((20, 50), f'{i / 30:05.2f} s  |  TRAIN cutoff + median camera  |  32-step causal warm-up',
                       font=font, fill='#a9bdd2')
                frame = Image.fromarray(np.asarray(arr.global_frames[int(arr.row_frame[row])])).resize((480, 270))
                for j, (label, seq) in enumerate(predictions.items()):
                    x = 16 + j * 512
                    d.text((x, 93), label, font=title, fill=('#8bceff' if j == 0 else '#9bedc1'))
                    canvas.paste(frame, (x, 130))
                    p = seq[i]
                    d.text((x, 415), f"yaw {p['yaw']:+7.3f}  pitch {p['pitch']:+7.3f} deg/step", font=font, fill='white')
                    d.text((x, 445), 'Yaw trace: last 3 s, +/- 12 deg/step', font=font, fill='#a9bdd2')
                    d.line((x, 510, x + 480, 510), fill='#486079')
                    points = [(x + 480 * k / 89, 510 - max(-12, min(12, q['yaw'])) * 3)
                              for k, q in enumerate(seq[max(0, i - 89):i + 1])]
                    if len(points) > 1:
                        d.line(points, fill='#f3c76d', width=2)
                    d.text((x, 562), 'Actions: blue=held, amber=recent press', font=font, fill='#a9bdd2')
                    # Display extends a press pulse to 5 frames only for legibility.
                    for c, name in enumerate(vocab.NAMES):
                        bx, by = x + (c % 3) * 160, 595 + (c // 3) * 27
                        recent = any(q['press'][c] > .5 for q in seq[max(0, i - 4):i + 1])
                        held = p['held'][c] > .5
                        color = '#9a6627' if recent else '#235477' if held else '#26303f'
                        d.rectangle((bx, by, bx + 155, by + 23), fill=color)
                        d.text((bx + 3, by + 2), name.replace('move_', '').replace('get_over_here', 'pull')[:13],
                               font=font, fill='white')
                d.text((20, 753), 'Same human frames in all panels; 256x144 policy view enlarged. Press flash lasts 5 frames.',
                       font=font, fill='#a9bdd2')
                proc.stdin.write(canvas.tobytes())
                if i in (0, 449, 899):
                    canvas.save(out / f'preview-{i:03d}.png')
        finally:
            proc.stdin.close()
        assert proc.wait() == 0
    probe = json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe', '-v', 'error',
        '-count_frames', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,nb_read_frames,duration',
        '-of', 'json', str(out / 'offline-predictions.mp4')]))
    stream = probe['streams'][0]
    assert int(stream['nb_read_frames']) == 900 and abs(float(stream['duration']) - 30) < .001
    put(out / 'receipt.json', {'scope': 'offline predictions, not model gameplay', 'exit': 0,
        'interval_sha256': sha(interval_path), 'judgement_sha256': sha(ROOT / 'mac-evaluation-a2b/judgement.json'),
        'script_sha256': sha(Path(__file__)), 'probe': probe, 'cloud_spend': 0,
        'files': {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in out.iterdir() if p.is_file()}})
    print('Offline replay complete; 900 frames / 30 seconds', flush=True)


if __name__ == '__main__':
    main()
