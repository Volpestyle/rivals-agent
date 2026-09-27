"""Render an admitted recorded clip against pinned H1-format policy predictions.

Run: python -m policy.range_bc.offline_replay --spec replay-spec.json --out NEW_DIR
The JSON spec selects the clip/interval receipt, roster, model/calibration pairs,
feature receipt, device, fps and optional judgement provenance. No live inputs.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import torch

from . import cache, metrics, train, vocab
from .confirm_encoder_recovery import completed_features
from .explore_camera import predict_suite
from .explore_chunks import ChunkPolicy
from .explore_chunks_train import FORMAT, load_manifest
from .explore_encoder import EncoderPolicy, FeatureArrays
from .model import Config


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def put(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def selected_interval(interval, runs):
    start, stop = interval['display_start_row'], interval['display_stop_row_exclusive']
    warmup_start = interval['warmup_start_row']
    train.require(0 <= warmup_start <= start < stop, 'invalid replay interval')
    train.require(stop - start == interval['frames'], 'frame count differs from interval')
    train.require(any(a <= warmup_start and stop <= b for a, b in runs),
                  'replay interval crosses an ineligible gap or run boundary')
    return warmup_start, start, stop


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    spec = json.loads(args.spec.read_text())
    train.require(os.getpriority(os.PRIO_PROCESS, 0) >= 10, 'run this offline job niced')
    torch.set_num_threads(2)
    interval_path = Path(spec['interval']['path'])
    train.require(sha(interval_path) == spec['interval']['sha256'], 'interval receipt changed')
    interval = json.loads(interval_path.read_text())
    train.require(interval['session'] == spec['clip'], 'clip differs from pinned interval')
    train.require(sha(spec['manifest']) == spec['manifest_sha256'], 'input manifest changed')
    train.require(abs(spec['fps'] - 1e9 / interval['step_ns']) < 1e-6, 'fps differs from source steps')
    train.require(1 <= len(spec['models']) <= 3, 'render one to three policy panels')
    train.require(len({m['label'] for m in spec['models']}) == len(spec['models']), 'duplicate model labels')
    if spec.get('judgement'):
        judge = spec['judgement']
        train.require(sha(judge['path']) == judge['sha256'], 'judgement provenance changed')
        train.require(json.loads(Path(judge['path']).read_text())['decision'] == judge['expected_decision'],
                      'unexpected judgement provenance')
    out = args.out
    out.mkdir(exist_ok=False)
    arrays, dev = load_manifest(spec['manifest'], spec['registry'], spec['tally'])
    del arrays
    arr = next(a for a in dev if a.session.session_id == spec['clip'])
    train.require(arr.session.sha256 == interval['steps_sha256'], 'clip source changed')
    manifest = json.loads(Path(spec['manifest']).read_text())
    item = next(x for x in manifest['dev'] if Path(x['steps']).stem == spec['clip'])
    cache.open_cache(item['cache'], arr.session, verify_hashes=True)
    warmup_start, start, stop = selected_interval(interval, arr.runs)
    warmup = start - warmup_start
    arr = copy.copy(arr)
    arr.runs = [(warmup_start, stop)]
    predictions, scores, live_masks = {}, {}, []
    feature_views = {}
    for entry in spec['models']:
        label = entry['label']
        path, calibration_path = Path(entry['checkpoint']), Path(entry['calibration'])
        train.require(sha(path) == entry['checkpoint_sha256'], 'checkpoint changed')
        train.require(sha(calibration_path) == entry['calibration_sha256'], 'TRAIN calibration changed')
        payload = torch.load(path, map_location='cpu', weights_only=True)
        train.require(payload['format'] == FORMAT and payload['recipe']['horizon'] == 1,
                      'renderer supports H1 exploratory-format checkpoints')
        train.require(payload['epoch'] == entry['epoch'], 'checkpoint epoch differs')
        train.require(entry['kind'] in ('chunk', 'encoder'), 'unknown checkpoint adapter')
        views, factory = arr, ChunkPolicy
        if entry['kind'] == 'encoder':
            feature = entry['features']
            key = feature['sha256']
            if key not in feature_views:
                root = completed_features(feature['path'], key, feature['inputs_sha256'])
                feature_views[key] = FeatureArrays(arr, root)
            views, factory = feature_views[key], EncoderPolicy
        model = factory(Config.from_dict(payload['recipe']['config']), 1).to(spec['device'])
        model.load_state_dict(payload['model'])
        calibration = json.loads(calibration_path.read_text())['threshold_calibration']
        train.require(calibration['source'] == 'TRAIN teacher-forced predictions only', 'wrong cutoff source')
        live = [calibration['actions'][name]['live'] for name in vocab.NAMES]
        live_masks.append(live)
        suite = predict_suite(model, [views], live, {
            ('train_chosen', 'median'): calibration['thresholds'],
            ('fixed_0.5', 'median'): [.5] * vocab.N}, device=spec['device'], progress=print)
        scores[label] = {}
        for condition, modes in suite.items():
            values = modes['self'][0][warmup:]
            train.require(len(values) == interval['frames'], 'prediction count differs')
            scores[label]['/'.join(condition)] = {
                'metrics': metrics.evaluate([values], **metrics.SELF),
                'checks': metrics.selffed_checks([values], live)}
            if condition[0] == 'train_chosen':
                predictions[label] = [p for _, p in values]
                records = [r for r, _ in values]
        del model, suite
        if spec['device'] == 'mps':
            torch.mps.empty_cache()
    train.require(all(mask == live_masks[0] for mask in live_masks), 'checkpoint support masks differ')
    predictions = {'James recorded': [r['target'] for r in records], **predictions}
    put(out / 'predictions.json', {'spec_sha256': sha(args.spec), 'interval_sha256': sha(interval_path),
        'caption': interval['caption'], 'source': interval['visual_source'],
        'thresholds': 'original TRAIN-calibrated; median camera', 'scores': scores,
        'predictions': predictions, 'row_ids': [r['row'] for r in records]})
    width, height = 512 * len(predictions), 800
    try:
        font = ImageFont.truetype('/System/Library/Fonts/Menlo.ttc', 18)
        title = ImageFont.truetype('/System/Library/Fonts/Menlo.ttc', 25)
    except OSError:
        font = ImageFont.load_default(size=18)
        title = ImageFont.load_default(size=25)
    ffmpeg = [spec.get('ffmpeg', 'ffmpeg'), '-v', 'error', '-nostdin', '-n', '-f', 'rawvideo',
        '-pix_fmt', 'rgb24', '-s', f'{width}x{height}', '-r', str(spec['fps']), '-i', '-', '-an',
        '-c:v', 'libx264', '-threads', '2', '-preset', 'fast', '-crf', '20', '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart', str(out / 'offline-predictions.mp4')]
    with (out / 'ffmpeg.log').open('x') as log:
        proc = subprocess.Popen(ffmpeg, stdin=subprocess.PIPE, stderr=log)
        try:
            for i, row in enumerate(range(interval['display_start_row'], interval['display_stop_row_exclusive'])):
                canvas = Image.new('RGB', (width, height), '#101722')
                d = ImageDraw.Draw(canvas)
                d.text((20, 15), 'OFFLINE PREDICTIONS / recorded frames, not model gameplay', font=title, fill='white')
                d.text((20, 50), f"{i / spec['fps']:05.2f} s  |  TRAIN cutoff + median camera  |  {warmup}-step causal warm-up",
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
                if i in (0, interval['frames'] // 2, interval['frames'] - 1):
                    canvas.save(out / f'preview-{i:03d}.png')
        finally:
            proc.stdin.close()
        assert proc.wait() == 0
    probe = json.loads(subprocess.check_output([spec.get('ffprobe', 'ffprobe'), '-v', 'error',
        '-count_frames', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,nb_read_frames,duration',
        '-of', 'json', str(out / 'offline-predictions.mp4')]))
    stream = probe['streams'][0]
    assert int(stream['nb_read_frames']) == interval['frames']
    assert abs(float(stream['duration']) - interval['frames'] / spec['fps']) < .001
    put(out / 'receipt.json', {'scope': 'offline predictions, not model gameplay', 'exit': 0,
        'spec_sha256': sha(args.spec), 'interval_sha256': sha(interval_path),
        'script_sha256': sha(Path(__file__)), 'probe': probe, 'cloud_spend': 0,
        'files': {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in out.iterdir() if p.is_file()}})
    print(f"Offline replay complete: {interval['frames']} frames", flush=True)


if __name__ == '__main__':
    main()
