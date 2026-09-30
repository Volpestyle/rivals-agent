"""Private IDM reviews: bounded label reads and a CPU-only, game/OBS-yielding queue.

Original media and labels stay on D:. Only requested label projections and short
overlaid clips are copied to the private Mac board. No upload to public services.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time

CORPUS = Path('D:/rivals-expert-footage')
LABELS = Path('D:/rivals-agent-local/idm-labels')
ROOT = CORPUS / 'private-review'
MAC_ROOT = '/Users/james/dev/idm-review'
SETS = ('v2-a', 'v2-cd')
MAX_LABEL_BYTES = 32 * 1024 * 1024
RENDER_VERSION = 2


def safe(path):
    """Reject sealed paths, symlinks and Windows junction/reparse traversal."""
    path = Path(path).absolute()
    if 'sealed' in str(path).lower():
        raise ValueError('sealed paths are closed')
    for part in (path, *path.parents):
        try:
            stat = part.lstat()
        except FileNotFoundError:
            continue
        if part.is_symlink() or getattr(stat, 'st_file_attributes', 0) & 0x400:
            raise ValueError('symlink/reparse traversal refused')
    return path


def read_json(path, limit=8 * 1024 * 1024):
    try:
        with safe(path).open('rb') as stream:
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise ValueError('oversized metadata')
        return json.loads(raw)
    except FileNotFoundError:
        return {}


def write_json(path, value):
    path = safe(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = safe(path.with_suffix(path.suffix + '.tmp'))
    temp.write_text(json.dumps(value, separators=(',', ':'), allow_nan=False), encoding='utf-8')
    temp.replace(path)


def stamp():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def corpus_rows(path):
    with safe(path).open('rb') as stream:
        if os.fstat(stream.fileno()).st_size > 20 * 1024 * 1024:
            raise ValueError('oversized corpus metadata')
        for line in stream:
            if len(line) > 262144:
                raise ValueError('oversized metadata line')
            yield json.loads(line)


def key(sid, ordinal, label_set):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', sid) or label_set not in SETS:
        raise ValueError('invalid review identifier')
    if not isinstance(ordinal, int) or not 0 <= ordinal < 10000:
        raise ValueError('invalid span ordinal')
    return hashlib.sha256(f'{sid}/{ordinal}/{label_set}'.encode()).hexdigest()[:24]


def label_index(path, cache):
    """One bounded streaming pass per changed label file; byte ranges per segment.

    Maximum one GiB and 120 seconds per file. No rows retained in memory. A
    partially written final row is ignored and retried when the file changes.
    """
    path = safe(path)
    if not path.exists():
        return {}
    stat = path.stat()
    fingerprint = [stat.st_size, stat.st_mtime_ns]
    prior = read_json(cache)
    if prior.get('fingerprint') == fingerprint:
        return prior
    if stat.st_size > 1024 ** 3:
        raise ValueError('label file exceeds bounded index size')
    spans = {}
    deadline = time.monotonic() + 120
    pattern = re.compile(rb'"(?:run|segment)"\s*:\s*"([^"\\]+)"')
    with path.open('rb') as stream:
        header = json.loads(stream.readline(65536))
        while stream.tell() < stat.st_size:
            if time.monotonic() > deadline:
                raise TimeoutError('label index deadline')
            begin = stream.tell()
            line = stream.readline(65536)
            if not line.endswith(b'\n'):
                break
            match = pattern.search(line)
            if match:
                span = match[1].decode('utf-8')
                item = spans.setdefault(span, {'begin': begin, 'end': 0, 'rows': 0})
                item['end'] = stream.tell()
                item['rows'] += 1
    value = {'fingerprint': fingerprint, 'header': header, 'spans': spans}
    write_json(cache, value)
    return value


def prepare(root=ROOT, corpus=CORPUS, labels=LABELS):
    root = safe(root)
    catalogue = {x['source_id']: x for x in corpus_rows(corpus / 'catalogue.jsonl')}
    grouped = defaultdict(list)
    for span in corpus_rows(corpus / 'idm-spans.jsonl'):
        grouped[span['source_id']].append(span)
    videos = []
    for sid, spans in grouped.items():
        indexes = {name: label_index(labels / name / f'expert-{sid}.steps.jsonl',
                                    root / 'indexes' / f'{name}-{sid}.json') for name in SETS}
        cat = catalogue[sid]
        public = []
        for ordinal, span in enumerate(spans):
            public.append({'ordinal': ordinal, 'span_id': span['span_id'],
                           'start_s': span['start_s'], 'end_s': span['end_s'],
                           'labels': [name for name in SETS if span['span_id'] in indexes[name].get('spans', {})]})
        video = {'source_id': sid, 'creator': cat['channel'], 'title': cat['title'],
                 'duration_s': cat['duration_s'], 'spans': public, 'updated': stamp()}
        write_json(root / 'videos' / f'{sid}.json', video)
        videos.append({k: v for k, v in video.items() if k != 'spans'} | {'spans': len(public)})
        print('indexed', sid, len(public), flush=True)
    write_json(root / 'catalogue.json', {'videos': videos, 'updated': stamp()})


def selected_span(sid, ordinal, corpus=CORPUS):
    found = [s for s in corpus_rows(corpus / 'idm-spans.jsonl') if s['source_id'] == sid]
    if ordinal >= len(found):
        raise ValueError('span not in admitted corpus')
    return found[ordinal]


def project_labels(span, label_set, root=ROOT, labels=LABELS):
    sid = span['source_id']
    path = safe(labels / label_set / f'expert-{sid}.steps.jsonl')
    index = label_index(path, root / 'indexes' / f'{label_set}-{sid}.json')
    part = index.get('spans', {}).get(span['span_id'])
    if not part:
        return {'actions': [], 'rows': [], 'message': 'No exported labels for this span yet.'}
    if part['end'] - part['begin'] > MAX_LABEL_BYTES:
        raise ValueError('span label range exceeds 32 MiB bound')
    header = index['header']
    step = header['step_ns'] / 1e9
    if not 0 < step <= 1:
        raise ValueError('invalid label step duration')
    result = []
    with path.open('rb') as stream:
        stream.seek(part['begin'])
        while stream.tell() < part['end']:
            row = json.loads(stream.readline(65536))
            if row.get('segment', row.get('run')) != span['span_id']:
                continue
            t = row['anchor_ns'] / 1e9
            if not span['start_s'] <= t < span['end_s']:
                continue
            def known(values, mask):
                return [v if i < len(mask) and mask[i] else None for i, v in enumerate(values)]
            yaw, pitch = row.get('yaw_deg'), row.get('pitch_deg')
            result.append({'t': t, 'dt': step,
                           'yaw': yaw / step if isinstance(yaw, (int, float)) and math.isfinite(yaw) else None,
                           'pitch': pitch / step if isinstance(pitch, (int, float)) and math.isfinite(pitch) else None,
                           'press': known(row.get('press', []), row.get('press_known', [])),
                           'held': known(row.get('held_start', []), row.get('held_known', []))})
            if len(result) > 10000:
                raise ValueError('span exceeds 10000 label row bound')
    return {'actions': header['actions'], 'rows': result, 'step_s': step,
            'units': 'deg/s', 'source': 'actual exported IDM steps',
            'camera_basis': header.get('camera_scale', {}).get('basis', 'James camera degrees; expert scale unverified')}


def blockers(ignore_pid=None):
    """Fail closed. OBS in the tray still appears in tasklist."""
    result = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True,
                            text=True, timeout=5, check=True)
    processes = list(csv.reader(io.StringIO(result.stdout)))
    names = [row[0].lower() for row in processes if row and (len(row) < 2 or row[1] != str(ignore_pid))]
    active = [name for name in names if name.startswith('marvel-win64') or name == 'obs64.exe']
    if names.count('ffmpeg.exe') >= 2:
        active.append('other CPU decoders are active')
    return active


def guarded_run(command, cwd, timeout=180, check=blockers):
    if check():
        return False
    flags = getattr(subprocess, 'BELOW_NORMAL_PRIORITY_CLASS', 0) | getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    with safe(cwd / 'ffmpeg.log').open('wb') as log:
        process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=log, creationflags=flags)
        deadline = time.monotonic() + timeout
        try:
            while process.poll() is None:
                try:
                    paused = blockers(process.pid) if check is blockers else check()
                except (OSError, subprocess.SubprocessError):
                    paused = ['process check failed']
                if paused:
                    process.terminate()
                    process.wait(timeout=5)
                    return False
                if time.monotonic() > deadline:
                    raise TimeoutError('clip render deadline')
                time.sleep(.5)
            if process.returncode:
                raise RuntimeError('ffmpeg failed; private ffmpeg.log has details')
            return True
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)


def ass_time(seconds):
    n = max(0, round(seconds * 100))
    return f'{n // 360000}:{n // 6000 % 60:02}:{n // 100 % 60:02}.{n % 100:02}'


def overlay_ass(detail, start, duration):
    lines = ['[Script Info]', 'ScriptType: v4.00+', 'PlayResX: 960', 'PlayResY: 540',
             '[V4+ Styles]', 'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
             'Style: Label,Arial,14,&H00FFFFFF,&H00FFFFFF,&H80000000,&H80000000,0,0,0,0,100,100,0,0,3,2,0,7,8,8,8,1',
             '[Events]', 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
    def event(a, b, text):
        lines.append(f'Dialogue: 0,{ass_time(a)},{ass_time(b)},Label,,0,0,0,,{text}')
    event(0, duration, r'{\pos(14,14)}IDM output | yaw / pitch deg/s | P press, H held, ? unknown | +yaw right, +pitch down')
    for row in detail['rows']:
        a, b = max(0, row['t'] - start), min(duration, row['t'] + row['dt'] - start)
        if b <= a:
            continue
        for i, action in enumerate(detail['actions']):
            # Action names are an allowlisted token, never ASS markup.
            if not re.fullmatch(r'[a-z_]{1,40}', action):
                continue
            press = row['press'][i] if i < len(row['press']) else None
            held = row['held'][i] if i < len(row['held']) else None
            color = '00B9FF' if press else 'A8F0A0' if held else 'AAAAAA'
            state = 'P' if press else 'H' if held else '?' if press is None or held is None else '-'
            event(a, b, f'{{\\pos({14 + i % 5 * 150},{40 + i // 5 * 22})\\c&H{color}&}}{action} [{state}]')
        yaw, pitch = row['yaw'], row['pitch']
        if yaw is not None and pitch is not None:
            dx, dy = max(-65, min(65, yaw * .25)), max(-45, min(45, pitch * .25))
            length = math.hypot(dx, dy)
            if length > 1:
                ux, uy = dx / length, dy / length
                points = [(0, 0), (dx, dy), (dx - ux * 9 - uy * 4, dy - uy * 9 + ux * 4),
                          (dx, dy), (dx - ux * 9 + uy * 4, dy - uy * 9 - ux * 4)]
                drawing = 'm ' + ' l '.join(f'{x:.1f} {y:.1f}' for x, y in points)
                event(a, b, r'{\pos(865,83)\p1\bord2\shad0\c&H00FFFF&}' + drawing)
            event(a, b, f'{{\\pos(780,132)}}yaw {yaw:+.1f}  pitch {pitch:+.1f}')
    return '\n'.join(lines) + '\n'


def enqueue(sid, ordinal, label_set, root=ROOT, corpus=CORPUS):
    token = key(sid, ordinal, label_set)
    selected_span(sid, ordinal, corpus)  # Membership, not a client-supplied path.
    request = {'source_id': sid, 'ordinal': ordinal, 'label_set': label_set, 'key': token}
    write_json(root / 'queue' / f'{token}.json', request)
    status = root / 'status' / f'{token}.json'
    if read_json(status).get('state') != 'ready' or read_json(status).get('render_version') != RENDER_VERSION:
        write_json(status, {'state': 'queued', 'updated': stamp()})
    return request


def render_request(request, root=ROOT, corpus=CORPUS, labels=LABELS):
    sid, ordinal, name = request['source_id'], request['ordinal'], request['label_set']
    token = key(sid, ordinal, name)
    status_path = root / 'status' / f'{token}.json'
    prior = read_json(status_path)
    if (prior.get('state') == 'ready' and prior.get('render_version') == RENDER_VERSION
            and safe(root / 'clips' / f'{token}.mp4').is_file()):
        return True
    span = selected_span(sid, ordinal, corpus)
    detail = project_labels(span, name, root, labels)
    detail.update(start_s=span['start_s'], end_s=span['end_s'], label_set=name, span_id=span['span_id'])
    write_json(root / 'details' / f'{token}.json', detail)
    if not detail['rows']:
        write_json(status_path, {'state': 'not-yet-labelled', 'updated': stamp()})
        return True
    active = blockers()
    if active:
        write_json(status_path, {'state': 'paused-for-game', 'reason': ', '.join(active), 'updated': stamp()})
        return False
    media = safe(Path(span['local_path']))
    if not media.is_relative_to(safe(corpus / 'media')):
        raise ValueError('media outside admitted media root')
    start, duration = span['start_s'], min(10.0, span['end_s'] - span['start_s'])
    work = safe(root / 'work' / token)
    work.mkdir(parents=True, exist_ok=True)
    safe(work / 'overlay.ass').write_text(overlay_ass(detail, start, duration), encoding='utf-8')
    output = safe(work / 'clip.mp4')
    write_json(status_path, {'state': 'rendering', 'updated': stamp()})
    command = ['ffmpeg', '-nostdin', '-v', 'error', '-y', '-hwaccel', 'none', '-threads', '2',
               '-ss', str(start), '-i', str(media), '-t', str(duration), '-an',
               '-vf', 'scale=960:540,setsar=1,fps=30,ass=overlay.ass',
               '-filter_threads', '2', '-c:v', 'libx264', '-threads', '2', '-preset', 'veryfast',
               '-crf', '24', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(output)]
    if not guarded_run(command, work):
        write_json(status_path, {'state': 'paused-for-game', 'reason': 'Game/OBS started or guard unavailable', 'updated': stamp()})
        return False
    target = safe(root / 'clips' / f'{token}.mp4')
    target.parent.mkdir(parents=True, exist_ok=True)
    output.replace(target)
    write_json(status_path, {'state': 'ready', 'render_version': RENDER_VERSION,
                             'clip_start_s': start, 'clip_duration_s': duration,
                             'width': 960, 'height': 540, 'updated': stamp()})
    return True


def sync_files(paths, root=ROOT):
    for path in paths:
        path = safe(path)
        relative = path.relative_to(safe(root)).as_posix()
        if not re.fullmatch(r'[A-Za-z0-9_./-]+', relative) or '..' in relative:
            raise ValueError('invalid sync path')
        remote = MAC_ROOT + '/' + relative
        # Atomic publication: web requests never see a partially transferred clip.
        subprocess.run(['scp', '-q', '-o', 'BatchMode=yes', str(path), 'mac:' + remote + '.tmp'],
                       timeout=120, check=True)
        ssh = 'C:/Program Files/Git/usr/bin/ssh.exe' if os.name == 'nt' else 'ssh'
        subprocess.run([ssh, '-n', '-T', '-o', 'BatchMode=yes', 'mac',
                        f'nice -n 10 taskpolicy -b mv {remote}.tmp {remote}'], timeout=15, check=True)


def seed(root=ROOT):
    by_creator = defaultdict(list)
    for v in read_json(root / 'catalogue.json')['videos']:
        video = read_json(root / 'videos' / (v['source_id'] + '.json'))
        usable = [s for s in video['spans'] if s['end_s'] - s['start_s'] >= 10 and s['labels']]
        if usable:
            by_creator[v['creator']].append((v['source_id'], usable[len(usable) // 2]))
    requests = []
    for creator, sources in by_creator.items():
        picks = sources[:2]
        if len(picks) == 1:
            sid, first = picks[0]
            other = [s for s in read_json(root / 'videos' / (sid + '.json'))['spans']
                     if s['labels'] and s['end_s'] - s['start_s'] >= 10 and s['ordinal'] != first['ordinal']]
            if other:
                picks.append((sid, other[len(other) // 3]))
        for sid, span in picks:
            name = 'v2-cd' if 'v2-cd' in span['labels'] else 'v2-a'
            request = enqueue(sid, span['ordinal'], name, root)
            requests.append(dict(request, creator=creator))
    write_json(root / 'samples.json', {'samples': requests})
    return requests


def worker(root=ROOT, sync=False, once=False):
    # One renderer at a time, including independently launched queue workers.
    root = safe(root)
    root.mkdir(parents=True, exist_ok=True)
    lock = safe(root / 'worker.lock').open('a+b')
    if os.name == 'nt':
        import msvcrt
        lock.seek(0)
        if not lock.read(1):
            lock.write(b'0')
            lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    last_refresh = time.monotonic()
    heartbeat = 0
    while True:
        for path in sorted(safe(root / 'queue').glob('*.json'), key=lambda p: p.stat().st_mtime):
            request = read_json(path)
            token = key(request['source_id'], request['ordinal'], request['label_set'])
            done = True
            try:
                done = render_request(request, root)
                if sync:
                    files = [root / folder / (token + suffix) for folder, suffix in
                             [('details', '.json'), ('clips', '.mp4'), ('status', '.json')]]
                    sync_files([p for p in files if p.exists()], root)
                if done:
                    path.unlink()  # Only this renderer's consumed queue request.
            except Exception as error:
                write_json(root / 'status' / f'{token}.json',
                           {'state': 'error', 'reason': str(error)[:300], 'updated': stamp()})
                if sync:
                    sync_files([root / 'status' / f'{token}.json'], root)
                path.unlink()
            if not done:
                break
        if once:
            return
        if time.monotonic() >= heartbeat:
            if __package__:
                from .job_status import write
            else:
                from job_status import write
            pending = len(list((root / 'queue').glob('*.json')))
            ready = len(list((root / 'clips').glob('*.mp4')))
            write('idm-review-clips', owner='footage', stage='queued', host='pc',
                  evidence=str(root / 'status'), progress=f'{ready} private clips ready; {pending} queued', eta=None)
            heartbeat = time.monotonic() + 30
        if time.monotonic() - last_refresh > 600:
            prepare(root)
            if sync:
                sync_files([root / 'catalogue.json', *sorted((root / 'videos').glob('*.json'))], root)
            last_refresh = time.monotonic()
        time.sleep(5)


def main():
    if os.name == 'nt':
        import ctypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        if not kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x4000):
            raise ctypes.WinError(ctypes.get_last_error())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'seed', 'enqueue', 'worker'])
    parser.add_argument('--source')
    parser.add_argument('--span', type=int)
    parser.add_argument('--label-set', choices=SETS, default='v2-cd')
    parser.add_argument('--sync', action='store_true')
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare()
        if args.sync:
            sync_files([ROOT / 'catalogue.json', *sorted((ROOT / 'videos').glob('*.json'))])
    elif args.command == 'seed':
        print(json.dumps(seed()))
    elif args.command == 'enqueue':
        print(json.dumps(enqueue(args.source, args.span, args.label_set)))
    else:
        worker(sync=args.sync, once=args.once)


if __name__ == '__main__':
    main()
