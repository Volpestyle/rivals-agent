"""Read-only IDM labelling metadata. Never open label steps beyond their header."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
import subprocess
import threading
import time

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
                              [(v['source_id'], v['creator'], number(v['duration_hours'], 2) + ' h',
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
            'No frames or label payloads are served.</footer></div></body></html>')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dump', action='store_true', required=True)
    parser.parse_args()
    print(json.dumps(collect(), allow_nan=False))
