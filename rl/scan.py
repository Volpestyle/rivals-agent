"""Run the reward readers over a recorded video, offline. No game, no input.

  python -m rl.scan VIDEO OUT.jsonl [--fps 10] [--start S] [--duration D] [--crops DIR]

Frames stream from one ffmpeg process as raw native BGR, one at a time, so memory stays at
a few frames. Each row: t (s from --start), the per-frame reads, and the raw scores behind them.
With --crops, every frame where a KO ring, a kill-feed change or an hp change starts is saved as
small crops for hand checking.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from perception.events import playing_spiderman  # noqa: E402
from perception.hud import read_bar_fill, read_damage_segment, read_hp  # noqa: E402
from perception.killfeed_geometry import row_candidates  # noqa: E402
from perception.scoreboard import is_killfeed  # noqa: E402
from rl.rewards import hit_arms, ko_ring, HIT_RUN, HIT_ARMS, KO_ON  # noqa: E402

FEED = (1990, 20, 2530, 200)   # x0, y0, x1, y1 at 1440p: the range kill-feed column
ROIS = (                        # what a native frame is cut down to before it leaves ffmpeg
    (1190, 630, 1370, 810),     # crosshair: hit strokes reach r 68, the KO ring r 62
    (1960, 20, 2530, 200),      # kill feed: FEED plus scoreboard.KILLFEED (x from 0.77 w)
    (920, 1266, 1640, 1440),    # hp digits and bar: hud.HP_TEXT and HP_BAR
    (38, 1209, 256, 1383),      # hero portrait: perception.events.PORTRAIT (for --hero)
)


def probe(video):
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                          'stream=width,height', '-of', 'json', str(video)],
                         capture_output=True, text=True, check=True).stdout
    s = json.loads(out)['streams'][0]
    return s['width'], s['height']


def frames(video, fps=10.0, start=None, duration=None, threads=4, hwaccel=None):
    w, h = probe(video)
    cmd = ['ffmpeg', '-v', 'error', '-threads', str(threads)]
    if hwaccel:
        cmd += ['-hwaccel', hwaccel]
    if start is not None:
        cmd += ['-ss', str(start)]
    if duration is not None:
        cmd += ['-t', str(duration)]
    roi = (w, h) == (2560, 1440)
    if roi:
        # Only the regions the readers look at leave ffmpeg, stacked into one 720x534 image; piping whole native
        # frames ran at a quarter of real time on the shared PC. They are pasted back into a native canvas, so
        # every reader sees its own pixels at their own coordinates and nothing else (the rest stays black).
        chains = ';'.join(f'[s{i}]crop={x1 - x0}:{y1 - y0}:{x0}:{y0},pad=720:{y1 - y0}[r{i}]'
                          for i, (x0, y0, x1, y1) in enumerate(ROIS))
        graph = (f'[0:v]fps={fps},split={len(ROIS)}' + ''.join(f'[s{i}]' for i in range(len(ROIS))) + ';'
                 + chains + ';' + ''.join(f'[r{i}]' for i in range(len(ROIS))) + f'vstack={len(ROIS)}')
        cmd += ['-i', str(video), '-filter_complex', graph]
        ow, oh = 720, sum(y1 - y0 for _, y0, _, y1 in ROIS)
    else:
        cmd += ['-i', str(video), '-vf', f'fps={fps}']
        ow, oh = w, h
    cmd += ['-f', 'rawvideo', '-pix_fmt', 'bgr24', '-']
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=ow * oh * 3)
    canvas = np.zeros((h, w, 3), np.uint8)
    n = 0
    try:
        while True:
            buf = proc.stdout.read(ow * oh * 3)
            if len(buf) < ow * oh * 3:
                break
            img = np.frombuffer(buf, np.uint8).reshape(oh, ow, 3)
            if roi:
                y = 0
                for x0, y0, x1, y1 in ROIS:
                    canvas[y0:y1, x0:x1] = img[y:y + y1 - y0, :x1 - x0]
                    y += y1 - y0
                img = canvas
            yield n / fps, img
            n += 1
    finally:
        proc.stdout.close()
        proc.wait()


def read_frame(frame, hero=False):
    s = frame.shape[0] / 1440.0
    arms = hit_arms(frame)
    x0, y0, x1, y1 = (int(round(v * s)) for v in FEED)
    rows = row_candidates(frame[y0:y1, x0:x1]) if frame.shape[:2] == (1440, 2560) else None
    hp, max_hp = read_hp(frame)
    return {
        'hit': sum(r >= HIT_RUN for r in arms) >= HIT_ARMS, 'hit_arms': [round(r) for r in arms],
        'ko': ko_ring(frame) >= KO_ON, 'ko_ring': round(ko_ring(frame), 3),
        'feed': is_killfeed(frame), 'feed_rows': None if rows is None else len(rows),
        'hp': hp, 'max_hp': max_hp, 'bar': read_bar_fill(frame),
        'dmg_stripe': round(read_damage_segment(frame) or 0.0, 3),
        'own': playing_spiderman(frame) if hero else None,
    }


def save_crops(frame, path):
    h, w = frame.shape[:2]
    cross = frame[h // 2 - 90:h // 2 + 90, w // 2 - 90:w // 2 + 90]
    feed = frame[20:200, 1990:2530]
    hud = frame[int(h * 0.88):h, int(w * 0.36):int(w * 0.64)]
    top = cv2.resize(feed, (360, 120))
    mid = np.zeros((180, 360, 3), np.uint8)
    mid[:, 90:270] = cross
    bot = cv2.resize(hud, (360, int(360 * hud.shape[0] / hud.shape[1])))
    cv2.imwrite(str(path), np.vstack([top, mid, bot]))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('video')
    ap.add_argument('out')
    ap.add_argument('--fps', type=float, default=10.0)
    ap.add_argument('--start', type=float)
    ap.add_argument('--duration', type=float)
    ap.add_argument('--crops')
    ap.add_argument('--hero', action='store_true', help='read the hero portrait (~50 ms/frame); for matches')
    ap.add_argument('--threads', type=int, default=0, help='ffmpeg decode threads; 0 = auto (3.5x faster than 8 on the PC)')
    ap.add_argument('--hwaccel', help="e.g. cuda; only while the game is closed (the GPU is the game's)")
    a = ap.parse_args(argv)
    crops = Path(a.crops) if a.crops else None
    if crops:
        crops.mkdir(parents=True, exist_ok=True)
    prev = None
    with open(a.out, 'w', encoding='utf-8') as f:
        for t, frame in frames(a.video, a.fps, a.start, a.duration, a.threads, a.hwaccel):
            row = {'t': round(t, 3), **read_frame(frame, a.hero)}
            f.write(json.dumps(row) + '\n')
            if crops and prev is not None and (
                    (row['ko'] and not prev['ko'])
                    or (row['feed_rows'] or 0) > (prev['feed_rows'] or 0)
                    or (row['hp'] is not None and prev['hp'] is not None and row['hp'] != prev['hp'])):
                save_crops(frame, crops / f'{t:08.2f}.jpg')
            prev = row


if __name__ == '__main__':
    main()
