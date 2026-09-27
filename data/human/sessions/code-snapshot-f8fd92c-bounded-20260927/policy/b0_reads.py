"""Persist unchanged HUD reader outputs for B0's two authorized training sources only."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import time

from .b0 import OUT, digest, train_clips, write_json


def serialize_reads(reads):
    """Preserve the format-5 reader's score and optional glyph observations without using them as labels."""
    rows = []
    for read in reads:
        if len(read) not in (8, 9):
            raise ValueError('format-5 read_run must return 8 fields, or 9 with glyph evidence')
        i, t, hud, playing, aside, killfeed, cut, score = read[:8]
        row = dict(i=i, t=t, hud=asdict(hud), playing=playing, aside=aside, killfeed=killfeed,
                   cut=cut, hero_score=score)
        if len(read) == 9:
            row['glyph_evidence'] = read[8]
        rows.append(row)
    return rows


def main():
    from perception.events import extract_frames, read_run, scene_cuts, writer_version, _cut_flags
    from perception.hud import LAYOUTS

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', required=True)
    ap.add_argument('--out', type=Path, default=OUT)
    args = ap.parse_args()
    _, clips = train_clips()
    clip = next((c for c in clips if c.id == args.source), None)
    if clip is None:
        raise ValueError('source is not one of the two authorized train clips')
    meta = clip.events_meta
    if meta['writer'] != writer_version():
        raise ValueError('reader changed since accepted event extraction')
    target = args.out / 'visibility' / (clip.id + '.json')
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ValueError(f'{target} already exists; inspect before replacing')
    run_dir = args.out / 'frames' / clip.id
    r = meta['recipe']
    started = time.perf_counter()
    print(f'{clip.id}: extracting 10Hz frames', flush=True)
    index = run_dir / 'frames.jsonl'
    if index.exists():
        frame_rows = [json.loads(line) for line in index.read_text().splitlines()]
        if (len(frame_rows) != meta['frames'] or frame_rows[0]['t'] != 0
                or abs(frame_rows[-1]['t'] - meta['duration_s']) > .002
                or any(row['i'] != i or abs(row['t'] - i / 10) > .002
                       or not (run_dir / row['file']).exists() for i, row in enumerate(frame_rows))):
            raise ValueError('retained extracted frame index does not match accepted reader grid')
        origin = meta['pts_origin_s']  # retained frames from this authorized extraction attempt
        print(f'{clip.id}: reusing checked {len(frame_rows)} extracted frames', flush=True)
    else:
        origin = extract_frames(r['video'], run_dir, r['hz'], r['start'], r['duration'])
        frame_rows = [json.loads(line) for line in index.read_text().splitlines()]
    if abs(origin - meta['pts_origin_s']) > .001:
        raise ValueError('reader origin changed')
    cuts = scene_cuts(r['video'], pts_origin=origin, start=r['start'], duration=r['duration'])
    snapped_cuts = [round(row['t'], 3) for row, flag in zip(frame_rows, _cut_flags(cuts, frame_rows)) if flag]
    if snapped_cuts != meta['cut_times']:
        raise ValueError('cut detection differs from accepted event stream')
    write_json(run_dir / 'cuts.json', cuts)
    reads = read_run(run_dir, layout=LAYOUTS[r['layout']], progress=500)
    if len(reads) != meta['frames'] or writer_version() != meta['writer']:
        raise ValueError('reader frame count or writer changed')
    rows = serialize_reads(reads)
    payload = dict(meta=dict(source=clip.id, event_sha256=digest(clip._resolve(clip.header['events'])),
                            manifest_sha256=digest(clip.path), media_sha256=digest(r['video']),
                            writer=meta['writer'], fps=meta['fps'], pts_origin_s=origin,
                            slot_mapping=meta['slot_mapping'], layout=meta['layout'], recipe=r,
                            native_cut_times=cuts, sampled_cut_times=snapped_cuts, frame_index_sha256=digest(index),
                            reader_versions={p: digest(p) for p in ('perception/events.py', 'perception/hud.py')},
                            elapsed_seconds=time.perf_counter() - started,
                            limitation='10Hz sampled observability; intersample occlusions are not established'), frames=rows)
    write_json(target.with_suffix('.tmp'), payload)
    target.with_suffix('.tmp').replace(target)
    print(f'{target}: {len(rows)} raw frames, {time.perf_counter() - started:.1f}s', flush=True)


if __name__ == '__main__':
    main()
