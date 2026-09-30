"""IDM progress metadata and private span/label/clip review on the tailnet board."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
import re
import secrets
import subprocess
import threading
import time
from urllib.parse import urlsplit

if __package__:
    from . import idm_clip_renderer as review
else:
    import idm_clip_renderer as review

SETS = ('v2-a', 'v2-cd')
STATES = {'queued', 'labelling', 'done', 'paused-for-game', 'held'}


def rows(path, max_bytes=20 * 1024 * 1024):
    """Only explicit metadata files, with bounded reads and no symlink traversal."""
    path = Path(path)
    if any('sealed' in p.lower() for p in path.parts):
        return
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        return
    try:
        with path.open('rb') as stream:
            remaining = max_bytes
            while remaining > 0:
                line = stream.readline(min(remaining, 262144))
                if not line:
                    break
                remaining -= len(line)
                try:
                    yield json.loads(line)
                except (ValueError, UnicodeError):
                    continue
    except OSError:
        return


def document(path):
    # Receipt JSON can be pretty-printed, unlike label headers.
    path = Path(path)
    if (any('sealed' in p.lower() for p in path.parts)
            or path.is_symlink() or any(p.is_symlink() for p in path.parents)):
        return {}
    try:
        with path.open('rb') as stream:
            value = json.loads(stream.read(1024 * 1024))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def header(path):
    path = Path(path)
    if (any('sealed' in p.lower() for p in path.parts)
            or path.is_symlink() or any(p.is_symlink() for p in path.parents)):
        return {}
    try:
        with path.open('rb') as stream:
            value = json.loads(stream.readline(65536))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def collect(corpus=Path('D:/rivals-expert-footage'),
            labels=Path('D:/rivals-agent-local/idm-labels'),
            jobs=Path('C:/Users/volpe/jobs')):
    published = document(jobs / 'idm-labelling.json')
    catalogue = {r['source_id']: r for r in rows(corpus / 'catalogue.jsonl')
                 if isinstance(r, dict) and 'source_id' in r}
    spans = defaultdict(list)
    for row in rows(corpus / 'idm-spans.jsonl'):
        spans[row['source_id']].append(row['end_s'] - row['start_s'])
    output = {'updated': datetime.now(timezone.utc).isoformat(),
              'supervisor': published.get('supervisor', {'state': 'unknown'}),
              'expert_check': published.get('expert_check'), 'label_sets': {},
              'total_spans': sum(map(len, spans.values())),
              'total_hours': sum(sum(s) for s in spans.values()) / 3600}
    for name in SETS:
        supplied = published.get('label_sets', {}).get(name, {})
        video_receipts = {str(v['source_id']): v for v in supplied.get('videos', [])}
        receipt_name = 'idm-v2a-expert-labels' if name == 'v2-a' else 'idm-v2cd-expert-labels'
        receipt = document(jobs / (receipt_name + '.status.json'))
        videos = []
        for sid, durations in spans.items():
            meta = header(labels / name / f'expert-{sid}.steps.jsonl')
            completed = meta.get('idm', {}).get('labelled_spans')
            reported = video_receipts.get(sid, {})
            done = reported.get('spans_done', completed)
            if not isinstance(done, int) or not 0 <= done <= len(durations):
                done = None
            # Whole-video hours are exact when every admitted span is labelled.
            # Partial span count alone does not tell us which durations were labelled.
            hours = reported.get('labelled_hours')
            if hours is None and done == len(durations):
                hours = sum(durations) / 3600
            if done == 0 and hours is None:
                hours = 0
            state = reported.get('state', 'done' if done == len(durations) else 'unknown')
            if state in ('labelled', 'exported'):
                state = 'done'
            elif state in ('pending', 'partial'):
                supervisor = output['supervisor'].get('state')
                stopped = 'superseded' in str(supplied.get('eta', '')).lower()
                if stopped or supervisor == 'held':
                    state = 'held'
                elif supervisor == 'paused-for-game':
                    state = 'paused-for-game'
                else:
                    state = 'labelling' if state == 'partial' else 'queued'
            if state not in STATES:
                state = 'unknown'
            videos.append({'source_id': sid, 'creator': catalogue.get(sid, {}).get('channel', 'unknown'),
                           'duration_hours': sum(durations) / 3600, 'label_set': name,
                           'state': state, 'spans_done': done, 'spans_total': len(durations),
                           'labelled_hours': hours, 'updated': reported.get('updated', 'unknown')})
        count = supplied.get('spans_done', receipt.get('progress', {}).get('n')
                             if isinstance(receipt.get('progress'), dict) else None)
        if count is None and all(v['spans_done'] is not None for v in videos):
            count = sum(v['spans_done'] for v in videos)
        hours = supplied.get('labelled_hours')
        if hours is None and all(v['labelled_hours'] is not None for v in videos):
            hours = sum(v['labelled_hours'] for v in videos)
        creators = []
        for creator in sorted({v['creator'] for v in videos}):
            group = [v for v in videos if v['creator'] == creator]
            creators.append({'creator': creator, 'spans_total': sum(v['spans_total'] for v in group),
                             'spans_done': sum(v['spans_done'] for v in group)
                             if all(v['spans_done'] is not None for v in group) else None,
                             'hours_total': sum(v['duration_hours'] for v in group),
                             'labelled_hours': sum(v['labelled_hours'] for v in group)
                             if all(v['labelled_hours'] is not None for v in group) else None})
        output['label_sets'][name] = {'spans_done': count, 'labelled_hours': hours,
                                     'throughput': supplied.get('throughput'),
                                     'eta': supplied.get('eta', receipt.get('eta')),
                                     'updated': supplied.get('updated', published.get('updated', receipt.get('updated', 'unknown'))),
                                     'videos': videos, 'creators': creators}
    return output


class LabellingCache:
    """Background PC metadata fetch; requests never block on SSH."""
    def __init__(self):
        self.lock = threading.Lock()
        self.data = None
        self.busy = False
        self.deadline = 0
        self.warning = 'IDM metadata is being fetched.'

    def poll(self):
        try:
            result = subprocess.run(
                ['ssh', '-n', '-T', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=4',
                 '-o', 'StrictHostKeyChecking=yes', 'volpe@supedupsilly',
                 'C:/Users/volpe/AppData/Local/Programs/Python/Python311/python.exe',
                 'C:/Users/volpe/repos/rivals-agent/scripts/idm_board.py', '--dump'],
                capture_output=True, text=True, timeout=15, check=True)
            if len(result.stdout) > 1024 * 1024:
                raise ValueError('oversized metadata')
            value = json.loads(result.stdout)
            if not isinstance(value.get('label_sets'), dict):
                raise ValueError('invalid metadata')
            with self.lock:
                self.data, self.warning = value, None
        except (OSError, ValueError, subprocess.SubprocessError):
            with self.lock:
                self.warning = 'PC metadata unavailable; cached counts may be stale. Current state is unconfirmed.'
        finally:
            with self.lock:
                self.busy = False
                self.deadline = time.monotonic() + 30

    def snapshot(self):
        with self.lock:
            if not self.busy and time.monotonic() >= self.deadline:
                self.busy = True
                threading.Thread(target=self.poll, daemon=True, name='idm-metadata').start()
            return dict(self.data or {}), self.warning


def render(data, warning, css):
    def text(value):
        if isinstance(value, VideoLink):
            return f'<a href="/idm-review/video/{escape(value.sid)}">{escape(value.sid)}</a>'
        return escape(str(value)) if value is not None else 'Unknown'

    def number(value, digits=0):
        return f'{value:,.{digits}f}' if isinstance(value, (int, float)) else 'Unknown'

    def table(headers, cells):
        return ('<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse">'
                '<thead><tr>' + ''.join(f'<th style="padding:12px;text-align:left">{text(h)}</th>' for h in headers)
                + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join(
                    f'<td style="padding:12px;border-top:1px solid #394146">{text(c)}</td>' for c in row)
                    + '</tr>' for row in cells) + '</tbody></table></div>')

    state = data.get('supervisor', {}).get('state', 'unknown')
    state = {'paused-for-game': 'Paused because the game is up', 'held': 'Held by the lead',
             'running': 'Running'}.get(state, 'Unknown') if not warning else 'Unconfirmed'
    panels, summaries = [], []
    for name in SETS:
        label = data.get('label_sets', {}).get(name, {})
        summaries.append(f'<section class="panel"><div class="panel-body"><h2>{name}</h2>'
                      f'<p style="font-size:22px">{number(label.get("spans_done"))} / '
                      f'{number(data.get("total_spans", 9350))} spans · '
                      f'{number(label.get("labelled_hours"), 1)} / '
                      f'{number(data.get("total_hours", 53.3), 1)} hours</p>'
                      f'<p>Throughput: {text(label.get("throughput"))} · ETA: {text(label.get("eta"))}</p>'
                      f'<p class="muted">Last receipt: {text(label.get("updated"))}</p></div></section>')
        panels.append(f'<section class="panel"><div class="panel-body"><h2>{name} · Videos</h2></div>'
                      + table(['Video', 'Creator', 'Admitted duration', 'State', 'Label set', 'Spans done', 'Last update'],
                              [(VideoLink(v['source_id']), v['creator'], number(v['duration_hours'], 2) + ' h',
                                v['state'], name, number(v['spans_done']) + ' / ' + number(v['spans_total']),
                                v['updated']) for v in label.get('videos', [])])
                      + '<div class="panel-body"><h3>Totals per creator</h3></div>'
                      + table(['Creator', 'Spans labelled', 'Hours labelled'],
                              [(v['creator'], number(v['spans_done']) + ' / ' + number(v['spans_total']),
                                number(v['labelled_hours'], 2) + ' / ' + number(v['hours_total'], 2))
                               for v in label.get('creators', [])]) + '</section>')
    check = data.get('expert_check') or {}
    accuracy = table(['Creator', 'Reported value', 'Metric', 'Samples', 'Flag'],
                     [(v.get('creator'), v.get('accuracy'), v.get('metric'), v.get('n'),
                       check.get('flags', {}).get(v.get('creator'), '—'))
                      for v in check.get('creators', [])]) if check.get('creators') else '<p>No per-creator accuracy receipt published yet.</p>'
    if check.get('creators'):
        accuracy = (f'<p>{text(check.get("source"))}</p><p class="muted">Updated: {text(check.get("updated"))}</p>'
                    + accuracy)
        press = check.get('press_spot_check', {})
        if press:
            accuracy += f'<p>Press spot-check precision: {text(press.get("precision"))} · n={text(press.get("n"))}</p>'
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta http-equiv="refresh" content="30"><title>IDM labelling · Rivals</title><style>{css}'
            '.idm-summary{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px;margin:24px 0}'
            '.idm-summary .panel{min-width:0}.shell>.panel{min-width:0}'
            '@media(max-width:760px){.idm-summary{grid-template-columns:minmax(0,1fr)}}'
            '</style>'
            '</head><body><div class="shell"><header class="masthead"><div class="brand">RIVALS<span>/ TRAINING LAB</span></div>'
            '<a href="/">Training lab</a></header><section class="overview"><div><h1>IDM labelling</h1>'
            f'<p>Supervisor: <strong>{text(state)}</strong> · {text(data.get("supervisor", {}).get("reason"))}</p>'
            '<p>Read-only metadata · updates every 30 seconds. Duration means admitted gameplay, not raw video.</p></div></section>'
            + (f'<div class="warning-banner">{text(warning)}</div>' if warning else '')
            + '<div class="idm-summary">' + ''.join(summaries) + '</div>'
            + ''.join(panels) + '<section class="panel"><div class="panel-body"><h2>Expert label accuracy</h2>'
            + accuracy + '</div></section><footer class="page-footer">Snapshot: '
            + text(data.get('updated')) + ' · Missing fields stay unknown. Done is the published processing state; refused spans can remain unlabelled. '
            'Private span reviews are available from each video link.</footer></div></body></html>')


class VideoLink:
    def __init__(self, sid):
        self.sid = sid


REVIEW_ROOT = Path('/Users/james/dev/idm-review')
_queue_slots = threading.BoundedSemaphore(2)


def review_url(sid, ordinal, label_set):
    review.key(sid, ordinal, label_set)
    return f'/idm-review/span/{sid}/{ordinal}/{label_set}'


def timeline(video):
    duration = max(1, video['duration_s'])
    pieces = []
    for span in video['spans']:
        name = 'v2-cd' if 'v2-cd' in span['labels'] else 'v2-a'
        url = review_url(video['source_id'], span['ordinal'], name)
        color = '#91d9bd' if span['labels'] else '#606a70'
        pieces.append(f'<a href="{url}"><rect x="{span["start_s"] / duration * 1000:.3f}" '
                      f'y="4" width="{max(.6, (span["end_s"] - span["start_s"]) / duration * 1000):.3f}" '
                      f'height="24" fill="{color}"><title>{span["start_s"]:.1f}–{span["end_s"]:.1f}s</title></rect></a>')
    return ('<svg class="timeline" role="img" aria-label="Admitted spans within the full video" viewBox="0 0 1000 32">'
            '<rect width="1000" height="32" fill="#253039"/>' + ''.join(pieces) + '</svg>')


def label_strip(detail):
    """SVG uses actual points; unknown labels remain gray, never converted to zero."""
    rows = detail.get('rows', [])
    if not rows:
        return '<p>Labels have not been loaded for this span yet.</p>'
    start, end = detail['start_s'], detail['end_s']
    width, left = 1000, 145
    scale = width / max(.001, end - start)
    actions = detail['actions']
    height = 265 + len(actions) * 23
    parts = [f'<svg id="label-strip" role="img" aria-label="Actual IDM camera and action labels" viewBox="0 0 1160 {height}">',
             '<rect width="1160" height="100%" fill="#101619"/>']
    for j, field in enumerate(('yaw', 'pitch')):
        mid = 60 + j * 90
        bound = max(1, max((abs(r[field]) for r in rows if r[field] is not None), default=1))
        parts.append(f'<text x="8" y="{mid - 10}" fill="#dbe9e5">{field} deg/s</text>'
                     f'<text x="8" y="{mid + 10}" fill="#93a7ab">±{bound:.1f}</text>'
                     f'<line x1="{left}" y1="{mid}" x2="1145" y2="{mid}" stroke="#405055"/>')
        points = []
        for row in rows + [{field: None}]:
            if row[field] is None:
                if points:
                    parts.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="{"#91d9bd" if j == 0 else "#edba76"}" stroke-width="1.4"/>')
                    points = []
            else:
                points.append(f'{left + (row["t"] - start) * scale:.2f},{mid - row[field] / bound * 35:.2f}')
    parts.append('<text x="8" y="216" fill="#b9c8cc">H / P</text>')
    for i, action in enumerate(actions):
        y = 230 + i * 23
        parts.append(f'<text x="8" y="{y + 11}" fill="#dbe9e5">{escape(action)}</text>')
        for lane, field in enumerate(('held', 'press')):
            parts.append(f'<rect x="{left}" y="{y + lane * 8}" width="1000" height="7" fill="#26343a"/>')
            runs = []
            for row in rows:
                value = row[field][i] if i < len(row[field]) else None
                a, b = row['t'], min(end, row['t'] + row['dt'])
                if runs and runs[-1][2] == value and abs(runs[-1][1] - a) < .002:
                    runs[-1][1] = b
                else:
                    runs.append([a, b, value])
            for a, b, value in runs:
                if value == 0:
                    continue
                color = '#59666b' if value is None else '#edba76' if lane else '#91d9bd'
                parts.append(f'<rect x="{left + (a - start) * scale:.2f}" y="{y + lane * 8}" '
                             f'width="{max(.4, (b - a) * scale):.2f}" height="7" fill="{color}"/>')
    for tick in range(6):
        t = (end - start) * tick / 5
        parts.append(f'<text x="{left + width * tick / 5:.1f}" y="{height - 5}" fill="#b9c8cc" text-anchor="middle">{t:.1f}s</text>')
    parts.append(f'<line id="playhead" x1="{left}" x2="{left}" y1="4" y2="{height - 20}" stroke="#fff" opacity=".7"/>')
    return ''.join(parts) + '</svg>'


def review_page(title, content, css, nonce, refresh=False):
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            + ('<meta http-equiv="refresh" content="5">' if refresh else '')
            + f'<title>{escape(title)} · IDM review</title><style>{css}'
            '.review{max-width:1280px;margin:auto;padding:24px}.review p{margin:12px 0}'
            '.timeline{width:100%;height:52px}.review table{width:100%;border-collapse:collapse}'
            '.review td,.review th{padding:10px;text-align:left;border-bottom:1px solid #344247}'
            '.review video{display:block;width:100%;max-width:960px;background:#000;border-radius:8px}'
            '.review button{background:#91d9bd;color:#13231e;border:0;border-radius:5px;padding:10px;cursor:pointer}'
            '.review form{display:inline-block;margin:3px}.review svg text{font:12px monospace}'
            '.strip{overflow-x:auto}.strip svg{width:100%;min-width:760px}.review nav{margin-bottom:24px}'
            '</style></head><body><main class="review"><nav><a href="/idm-labelling">IDM labelling</a> · '
            '<a href="/idm-review/">All videos</a></nav>'
            f'<h1>{escape(title)}</h1>{content}<p class="muted">Private tailnet review. Third-party footage must not be posted to Linear or the blog.</p></main></body></html>')


def queue_remote(sid, ordinal, name, root):
    token = review.key(sid, ordinal, name)
    try:
        subprocess.run(['ssh', '-n', '-T', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=4',
                        '-o', 'StrictHostKeyChecking=yes', 'volpe@supedupsilly',
                        'C:/Users/volpe/AppData/Local/Programs/Python/Python311/python.exe',
                        'C:/Users/volpe/repos/rivals-agent/scripts/idm_clip_renderer.py',
                        'enqueue', '--source', sid, '--span', str(ordinal), '--label-set', name],
                       capture_output=True, timeout=20, check=True)
    except (OSError, subprocess.SubprocessError):
        review.write_json(root / 'status' / f'{token}.json', {'state': 'error', 'reason': 'PC queue unavailable; retry when connected.'})
    finally:
        _queue_slots.release()


def handle_review_request(handler, css, root=REVIEW_ROOT):
    """Minimal job-board GET/POST hook. All private review routes end here."""
    path = urlsplit(handler.path).path
    if not path.startswith('/idm-review/'):
        return False
    nonce = secrets.token_urlsafe(18)
    def respond(body, mime='text/html; charset=utf-8', status=200, extra=()):
        if isinstance(body, str):
            body = body.encode('utf-8')
        handler.send_response(status)
        handler.send_header('Content-Type', mime)
        handler.send_header('Content-Length', str(len(body)))
        handler.send_header('Cache-Control', 'no-store')
        handler.send_header('X-Content-Type-Options', 'nosniff')
        handler.send_header('Content-Security-Policy', f"default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-{nonce}'; media-src 'self'; form-action 'self'; frame-ancestors 'none'")
        for name, value in extra:
            handler.send_header(name, value)
        handler.end_headers()
        handler.wfile.write(body)
    try:
        media = re.fullmatch(r'/idm-review/media/([a-f0-9]{24})\.mp4', path)
        if media and handler.command == 'GET':
            clip = review.safe(root / 'clips' / (media[1] + '.mp4'))
            if not clip.is_file() or clip.stat().st_size > 25 * 1024 * 1024:
                raise FileNotFoundError('clip not ready')
            size = clip.stat().st_size
            a, b = 0, size - 1
            requested = handler.headers.get('Range')
            if requested:
                match = re.fullmatch(r'bytes=(\d+)-(\d*)', requested)
                if not match or int(match[1]) >= size:
                    respond(b'', 'video/mp4', 416, [('Content-Range', f'bytes */{size}')])
                    return True
                a = int(match[1])
                b = min(size - 1, int(match[2])) if match[2] else size - 1
                if b < a:
                    raise ValueError('invalid byte range')
            with clip.open('rb') as stream:
                stream.seek(a)
                payload = stream.read(b - a + 1)
            headers = [('Accept-Ranges', 'bytes')]
            if requested:
                headers.append(('Content-Range', f'bytes {a}-{b}/{size}'))
            respond(payload, 'video/mp4', 206 if requested else 200, headers)
            return True
        match = re.fullmatch(r'/idm-review/(span|render)/([A-Za-z0-9_-]{1,64})/(\d{1,4})/(v2-a|v2-cd)', path)
        if match:
            kind, sid, ordinal, name = match[1], match[2], int(match[3]), match[4]
            token = review.key(sid, ordinal, name)
            video = review.read_json(root / 'videos' / (sid + '.json'))
            span = video['spans'][ordinal]
            status = review.read_json(root / 'status' / (token + '.json'))
            if kind == 'render' and handler.command == 'POST':
                host, origin = handler.headers.get('Host', ''), handler.headers.get('Origin', '')
                if origin not in ('https://' + host, 'http://' + host) or int(handler.headers.get('Content-Length', '0')) > 1024:
                    respond('Request origin refused.', status=403)
                    return True
                if name not in span['labels']:
                    respond('No exported labels for this span yet.', status=409)
                    return True
                if status.get('state') != 'ready':
                    if not _queue_slots.acquire(blocking=False):
                        respond('Queue connection busy; retry shortly.', status=503)
                        return True
                    review.write_json(root / 'status' / (token + '.json'), {'state': 'queued', 'updated': review.stamp()})
                    threading.Thread(target=queue_remote, args=(sid, ordinal, name, root), daemon=True).start()
                respond(b'', status=303, extra=[('Location', review_url(sid, ordinal, name))])
                return True
            if kind != 'span' or handler.command != 'GET':
                respond('Method not allowed', status=405)
                return True
            detail = review.read_json(root / 'details' / (token + '.json'))
            state = status.get('state', 'not rendered')
            title = f'{video["creator"]} · {sid} · span {ordinal + 1}'
            content = f'<p><a href="/idm-review/video/{sid}">Back to video timeline</a> · {span["start_s"]:.3f}–{span["end_s"]:.3f}s · {name}</p>'
            for other in span['labels']:
                content += f'<a style="margin-right:14px" href="{review_url(sid, ordinal, other)}">{other} labels</a>'
            content += f'<p><strong>{escape(state)}</strong> {escape(status.get("reason", ""))}</p>'
            if state == 'ready':
                content += f'<video id="review-video" controls autoplay muted loop playsinline src="/idm-review/media/{token}.mp4"></video>'
                content += f'<p>First {status["clip_duration_s"]:.1f}s of the span · 540p · actual IDM overlay. Camera arrow: +yaw right, +pitch down.</p>'
            else:
                content += f'<form method="post" action="/idm-review/render/{sid}/{ordinal}/{name}"><button>Load labels &amp; render 10s review</button></form>'
                content += '<p>Rendering waits until both the game and OBS have exited, including OBS in the tray.</p>'
            content += '<h2>Label strip</h2><p>Yaw/pitch in deg/s. Each action: held in green (upper), presses in amber (lower), unknown in gray.</p>'
            content += '<div class="strip">' + label_strip(detail) + '</div>'
            if detail:
                content += f'<p class="muted">Camera basis: {escape(detail.get("camera_basis", "unknown"))}</p>'
            if state == 'ready':
                duration = span['end_s'] - span['start_s']
                content += f'<script nonce="{nonce}">const v=document.getElementById("review-video"),p=document.getElementById("playhead");function tick(){{if(p){{let x=145+1000*v.currentTime/{duration};p.setAttribute("x1",x);p.setAttribute("x2",x);}}requestAnimationFrame(tick)}}tick();</script>'
            respond(review_page(title, content, css, nonce, state in ('queued', 'rendering', 'paused-for-game')))
            return True
        video_match = re.fullmatch(r'/idm-review/video/([A-Za-z0-9_-]{1,64})', path)
        if video_match and handler.command == 'GET':
            sid = video_match[1]
            video = review.read_json(root / 'videos' / (sid + '.json'))
            content = f'<p>{escape(video["title"])} · full video {video["duration_s"] / 3600:.2f}h</p>' + timeline(video)
            content += '<p>Green: exported labels exist · gray: not yet. Timeline covers the full source video.</p><div style="overflow-x:auto"><table><tr><th>Span</th><th>Start–end</th><th>Duration</th><th>Labels / review</th></tr>'
            for span in video['spans']:
                controls = 'not yet'
                if span['labels']:
                    controls = ''.join(f'<form method="post" action="/idm-review/render/{sid}/{span["ordinal"]}/{name}"><button>Review {name}</button></form>' for name in span['labels'])
                content += f'<tr><td>{span["ordinal"] + 1}</td><td>{span["start_s"]:.3f}–{span["end_s"]:.3f}s</td><td>{span["end_s"] - span["start_s"]:.1f}s</td><td>{controls}</td></tr>'
            content += '</table></div>'
            respond(review_page(video['creator'] + ' · ' + sid, content, css, nonce))
            return True
        if path == '/idm-review/' and handler.command == 'GET':
            catalogue = review.read_json(root / 'catalogue.json')
            content = '<p>Choose a source to inspect its admitted spans and the actual IDM output.</p><ul>'
            for video in catalogue.get('videos', []):
                content += f'<li><a href="/idm-review/video/{video["source_id"]}">{escape(video["creator"])} · {video["source_id"]}</a> · {video["spans"]} spans</li>'
            respond(review_page('Span reviews', content + '</ul>', css, nonce))
            return True
        respond('Not found', status=404)
    except (OSError, ValueError, KeyError, IndexError) as error:
        respond('Review unavailable: ' + escape(str(error)), status=404)
    return True


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dump', action='store_true', required=True)
    parser.parse_args()
    print(json.dumps(collect(), allow_nan=False))
