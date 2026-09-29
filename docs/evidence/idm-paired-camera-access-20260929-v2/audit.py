"""Phase-one access audit only. No decoder, inference, truth export or admission."""
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from agent import human_demos as H
from agent import human_intake as I

SID = '20260926T010620-721Z-63684-5'
REPLAY_SID = '20260926T161008-331Z-116800-2'
DENY = '09e8b9d350c89eb41c1581e1bce47548bfb855bca5805cf2e65955b9b23597b5'
SOURCES = (
    (SID, Path('C:/Users/volpe/Videos/2026-09-25 20-06-20.mkv'), 'b286939f3a503a52bffa0c0a29873e8c71aac7d89dfb1b726f4818176e2efc87'),
    (REPLAY_SID, Path('C:/Users/volpe/Videos/2026-09-26 11-10-08.mkv'), '4c74f388be47e44c53002005edb548cd41aa7308ecf50ac39a34625862817e7e'),
)

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)

def normalized_path(path):
    return str(path).replace('\\', '/').casefold()

def refuse_sealed(sources, banned):
    for sid, path, expected in sources:
        for row in banned:
            require(sid not in (row.get('session_id'), row.get('session_group'))
                    and expected != row.get('media_sha256')
                    and normalized_path(path) != normalized_path(row.get('media_path', '')),
                    'sealed source: STOP')

def main():
    # No user-selected input paths, registry discovery, or recursive traversal.
    deny = ROOT / 'data/human/sealed-denylist.v2.json'
    banned = I.load_denylist(deny, sha256_pin=DENY)['sessions']
    refuse_sealed(SOURCES, banned)
    pins = {}
    for sid, path, expected in SOURCES:
        actual = sha(path)
        require(actual == expected, 'video identity changed: STOP')
        pins[str(path)] = actual
    ledger = Path('C:/Users/volpe/Videos/RivalsInput') / SID
    for name in ('metadata.json', 'inputs.jsonl', 'frames.csv'):
        pins[str(ledger / name)] = sha(ledger / name)
    meta = json.loads((ledger / 'metadata.json').read_text(encoding='utf-8'))
    require(meta.get('session_id') == SID, 'logger identity mismatch: STOP')
    with (ledger / 'inputs.jsonl').open(encoding='utf-8') as f:
        events = tuple(H._event(json.loads(line)) for line in f)
    with (ledger / 'frames.csv').open(encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        require(tuple(reader.fieldnames) == H.FRAME_COLUMNS, 'unsupported frame schema')
        packets = [{k: int(v) for k, v in row.items()} for row in reader]
    start, end = H._validate_raw(meta, events, packets)
    require(all(a.t_ns <= b.t_ns for a, b in zip(events, events[1:])), 'input clock regression')
    require(all(p['packet_index'] == i and p['track'] == 0 for i, p in enumerate(packets)), 'packet discontinuity')
    state_events = [e.payload for e in events if e.type in ('focus', 'pause', 'raw_input_status', 'marker')]
    # Preserve state/timing evidence, never camera labels or mouse samples.
    result = {'designation': 'provisional, unadmitted development evidence',
              'pins': pins, 'ledger_pin_policy': 'trust-on-first-use at reviewed audit access; enforce in later packet',
              'denylist_sha256': DENY, 'metadata': meta,
              'raw_validation': 'passed', 'start_ns': start, 'end_ns': end,
              'state_events': state_events, 'event_count': len(events),
              'packet_count': len(packets),
              'timing_accuracy_established': False,
              'reason': 'Packet timestamps alone do not establish an independent muxer offset or capture latency.',
              'inference_run': False}
    out = Path('D:/rivals-agent-evidence/idm-paired-camera-development-20260929')
    out.mkdir(parents=True, exist_ok=True)
    with (out / 'access-audit.json').open('x', encoding='utf-8', newline='\n') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print('Access audit written; no decode or inference performed.')

if __name__ == '__main__':
    main()
