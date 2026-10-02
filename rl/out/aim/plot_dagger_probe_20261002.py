"""Render the measured single-seed camera-head comparison, without reading frames."""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).parent
data = json.loads((root / 'dagger_camera_probe_20261002.json').read_text())
im = Image.new('RGB', (1400, 860), '#111920')
d = ImageDraw.Draw(im)
font = lambda n: ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', n)
white, muted, blue, orange = '#eef4f7', '#adbec9', '#8ecbff', '#ffa77f'
d.text((48, 30), 'Camera-head DAgger probe: DISCARD', font=font(40), fill=white)
d.text((48, 90), 'Offline retained-frame replay | 1 seed | 400 epochs | provisional teacher gain 0.25 | $0', font=font(23), fill=muted)
d.text((48, 146), 'Mix399', font=font(22), fill=blue)
d.text((180, 146), 'Fine-tuned head', font=font(22), fill=orange)
d.text((48, 207), 'Held-out sitting', font=font(23), fill=white)
d.text((425, 207), 'Yaw sign agreement', font=font(23), fill=white)
d.text((755, 207), 'Yaw angular-error reduction / step', font=font(23), fill=white)
d.text((755, 242), 'degrees; right of zero is better', font=font(19), fill=muted)
for y, sid in [(285, '04'), (420, '07')]:
    fold = data['folds']['hold-rl-sitting-20260930-' + sid]
    scores = fold['held_out']['yaw']
    d.text((48, y), '20260930-' + sid, font=font(26), fill=white)
    d.text((48, y+39), f"n = {scores['mix399']['n']} labelled turn frames", font=font(20), fill=muted)
    zero, scale = 1200, 700
    d.line((zero, y-4, zero, y+93), fill=muted, width=2)
    for offset, model, color in [(0, 'mix399', blue), (45, 'finetuned', orange)]:
        score = scores[model]
        d.text((430, y+offset), f"{100*score['sign_agree']:.2f}%", font=font(25), fill=color)
        val = score['reduction_deg']
        endpoint = int(zero + val * scale)
        d.rectangle((min(zero, endpoint), y+offset+5, max(zero, endpoint), y+offset+26), fill=color)
        d.text((760, y+offset), f'{val:+.4f}', font=font(21), fill=color)
d.line((48, 557, 1350, 557), fill='#354653', width=2)
base = data['dev_yaw_mae_mix399'][0]
d.text((48, 580), f'DEV yaw guard: at most {base+.03:.4f} deg/step (mix399 {base:.4f} + 0.03)', font=font(27), fill=white)
d.text((48, 626), 'Actual: 0.9213 / 0.9142 / 1.0390 — all fail (24,556 DEV rows each)', font=font(25), fill=orange)
d.text((48, 674), 'Pitch improved, but yaw correction and DEV regression fail the stated keep criteria.', font=font(23), fill=white)
d.text((48, 716), 'learned-01-a: 81 zero-turn controls; n=0 directional targets, not an aiming pass.', font=font(20), fill=muted)
d.text((48, 752), 'Rows within episodes are correlated. Angular reduction is an offline geometric proxy, not live improvement.', font=font(19), fill=muted)
d.text((48, 794), 'Source: rl/out/aim/dagger_camera_probe_20261002.json; leave-one-sitting-out, CUDA replay.', font=font(19), fill=muted)
im.save(root / 'dagger_camera_probe_20261002.png')
