"""Owner verification of the two explicitly authorized ping-only assembly revisions; no decoder."""
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from agent import human_intake as hi


def need(value, message):
    if not value:
        raise RuntimeError(message)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def rows_by_segment(path):
    grouped = defaultdict(list)
    runs = defaultdict(dict)
    with path.open(encoding='utf-8') as f:
        header = json.loads(next(f))
        for line in f:
            row = json.loads(line)
            sid = row['segment']
            del row['i']
            mapping = runs[sid]
            row['run'] = mapping.setdefault(row['run'], len(mapping))
            grouped[sid].append(row)
    return header, grouped


def main(sid, attempt='initial'):
    need(sid in ('20260927T051206-888Z-150600-4', '20260927T052001-827Z-150600-5'), 'outside authorized revision scope')
    need(attempt in ('initial', 'retry1', 'retry2'), 'unknown attempt')
    d = ROOT / 'data/human/sessions' / sid
    run_dir = ROOT / 'data/admission-codex/runs' / sid / 'ping-a1'
    if attempt != 'initial':
        run_dir /= attempt
    out = run_dir / 'assembly-delta-check.json'
    need(not out.exists(), 'verification already recorded')
    read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
    run = read(out.parent / 'assemble.run.json')
    need(run['exit_code'] == 0 and run['failure'] is None, 'assembly did not succeed')
    delta = read(d / 'ping-a1-delta.json')
    evidence = read(d / 'segments-evidence.json')
    preservation = read(d / 'assembly-ping-a1-supersedes.json')
    for row in preservation['files']:
        need(sha(d / row['preserved']) == row['sha256'], 'historical assembly changed')
    old_header, old = rows_by_segment(d / f'{sid}.steps.v1.jsonl')
    new_header, new = rows_by_segment(d / f'{sid}.steps.jsonl')
    need({k: v for k, v in old_header.items() if k != 'source'} ==
         {k: v for k, v in new_header.items() if k != 'source'}, 'step header changed outside source pins')
    unchanged = delta['unchanged_segments']
    for key in unchanged:
        need(old.get(key, []) == new.get(key, []), f'unchanged step rows differ: {key}')
    payloads = []
    for name in ('imported-demo.v1.jsonl', 'imported-demo.jsonl'):
        with (d / name).open(encoding='utf-8') as f:
            header, body = json.loads(next(f)), next(f).rstrip('\n')
            need(not f.read(), 'unexpected imported-demo records')
        need(hashlib.sha256(body.encode()).hexdigest() == header['payload_sha256'], 'payload hash mismatch')
        payload = json.loads(body)
        payload.pop('review')
        payloads.append(payload)
    need(payloads[0] == payloads[1], 'raw metadata/events/packets/decoded PTS changed')
    cuts = hi.ping_wheel_cuts(payloads[1]['events'], evidence['focused_intervals'])
    review = read(d / 'review.json')
    accepted = [s for s in review['segments'] if s['imitation_suitability'] == 'accepted']
    need(not any(s['start_ns'] < b and a < s['end_ns'] for s in accepted for a, b, _ in cuts),
         'accepted interval overlaps held ping button or release settle')
    need(sum(s['end_ns'] - s['start_ns'] for s in accepted) == delta['accepted_ns'], 'accepted duration differs')
    doc = dict(session=sid, result='pass', unchanged_segment_count=len(unchanged),
               unchanged_step_rows=sum(len(new.get(k, [])) for k in unchanged),
               comparison='All step fields equal, except global row index and normalized run identifiers; run partition preserved.',
               raw_payload_and_decoded_pts_equal=True, accepted_ping_overlap_count=0,
               accepted_segments=len(accepted), accepted_ns=delta['accepted_ns'],
               steps_sha256=sha(d / f'{sid}.steps.jsonl'), imported_demo_sha256=sha(d / 'imported-demo.jsonl'),
               freeze_sha256=sha(d / 'artifact-hashes.json'), verifier_sha256=sha(Path(__file__)))
    out.write_text(json.dumps(doc, indent=1) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(doc))


if __name__ == '__main__':
    main(*sys.argv[1:])
