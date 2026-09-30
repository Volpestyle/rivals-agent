"""Read-only presentation of explicitly curated results; never discovers corpus files."""
from html import escape
from pathlib import Path
import re


CSS = """
.lab-nav{display:flex;gap:18px;flex-wrap:wrap;margin:0 0 28px;font-size:13px}
.lab-section{margin:0 0 32px;scroll-margin-top:20px}.lab-section h2{font-size:24px;letter-spacing:-.6px}
.lab-note{color:var(--muted);font-size:13px;line-height:1.6;margin:10px 0 18px}
.lab-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}
.lab-card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:20px;min-width:0}
.lab-card h3{font-size:17px;margin:10px 0}.lab-card p{font-size:13px;line-height:1.65;color:var(--muted)}
.lab-card img{display:block;width:100%;height:auto;border-radius:7px;margin:14px 0;background:#101319}
.lab-card a{overflow-wrap:anywhere}.lab-number{font-size:38px;letter-spacing:-1.5px;font-weight:650;color:var(--mint)}
.lab-card svg{width:100%;display:block}.lab-charts{grid-template-columns:repeat(4,minmax(0,1fr))}
.lab-readiness{margin:0 0 32px}.lab-readiness p{display:flex;justify-content:space-between;gap:8px}.lab-readiness h3{min-height:48px}
.lab-split{display:grid;grid-template-columns:1fr 1fr;gap:18px}.lab-scroll{overflow-x:auto;border:1px solid var(--line);border-radius:10px}
.lab-table{width:100%;border-collapse:collapse;font-size:13px;white-space:nowrap}.lab-table th,.lab-table td{text-align:left;padding:13px 16px;border-bottom:1px solid var(--line)}
.lab-table th{color:var(--muted);font-size:11px;letter-spacing:.04em;text-transform:uppercase}.lab-table tr:last-child td{border:0}
.lab-bar{display:grid;grid-template-columns:minmax(90px,1fr) 2fr 65px;align-items:center;gap:10px;font-size:12px;margin:12px 0}.lab-bar>span:first-child{overflow-wrap:anywhere}
.lab-track{height:7px;border-radius:6px;background:#2b3039;overflow:hidden}.lab-track i{display:block;height:100%;background:var(--orange)}
.lab-gate{border-left:3px solid var(--orange);padding:20px 24px;background:var(--panel);border-radius:0 12px 12px 0;margin-bottom:20px}
.lab-gate h2{margin:8px 0}.lab-gate p{line-height:1.6;color:var(--muted);max-width:840px;font-size:14px}
.lab-pill{display:inline-block;border-radius:20px;padding:4px 9px;font-size:11px;background:#243c36;color:#98ddc7;white-space:nowrap}.lab-pill.fail{background:#402e2c;color:#ffb09e}.lab-pill.unknown{background:#30343c;color:#bdc4cf}
.lab-timeline{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.lab-timeline .lab-card{padding:18px}.lab-cost{float:right;color:var(--muted);font-size:12px;max-width:55%;text-align:right}
.lab-timeline summary{cursor:pointer;font-size:12px;color:var(--mint);margin-top:12px}.lab-timeline .lab-card p{margin:9px 0}.lab-source{font-size:11px;color:var(--muted)}
.lab-budget{height:12px;margin:16px 0}.lab-budget i{background:var(--mint)}.lab-legend{display:flex;gap:16px;flex-wrap:wrap;font-size:12px;color:var(--muted)}
@media(max-width:900px){.lab-grid{grid-template-columns:1fr 1fr}.lab-split{grid-template-columns:1fr}}
@media(max-width:600px){.lab-grid,.lab-timeline{grid-template-columns:1fr}.lab-card{padding:16px}.lab-number{font-size:32px}.lab-section h2{font-size:21px}.lab-gate{padding:18px}.lab-nav{gap:14px}.lab-table th,.lab-table td{padding:11px}.lab-cost{float:none;display:block;text-align:left;max-width:100%;margin-top:8px}}
@media(max-width:600px){.masthead{align-items:flex-start;flex-direction:column;gap:12px;padding:20px 0}.brand{white-space:nowrap}.live-label{flex-wrap:wrap}.lab-readiness{grid-template-columns:1fr 1fr}.lab-readiness h3{font-size:14px}.lab-readiness p{font-size:12px}}
@media(prefers-reduced-motion:reduce){.lab-card img[src$=".gif"]{visibility:hidden}.lab-card a:has(img[src$=".gif"])::after{content:'Open animation';visibility:visible}}
"""


def media(repo, data, name):
    """Serve only manifest-named small image copies, never paths from a URL."""
    if name not in data.get('media', {}) or not re.fullmatch(r'[a-z0-9-]+\.(?:png|jpg|gif)', name):
        return None
    path = Path(repo) / 'data/job-board-media' / name
    if any('sealed' in p.name.lower() or p.is_symlink() for p in (path, *path.parents)):
        return None
    try:
        if path.stat().st_size > 16 * 1024 * 1024:
            return None
        body = path.read_bytes()
    except OSError:
        return None
    mime = {'.png': 'image/png', '.jpg': 'image/jpeg', '.gif': 'image/gif'}[path.suffix]
    return body, mime


def pill(value):
    style = 'fail' if value in ('FAIL', 'Discarded') else 'unknown' if value in ('Not measured', 'Pending', 'Unjudged', 'No gain demonstrated') else ''
    return f'<span class="lab-pill {style}">{escape(value)}</span>'


def readiness(hold, turn):
    if hold is None or turn is None:
        return 'Not measured'
    return 'PASS' if hold >= .3 and turn >= .2 else 'FAIL'


def table(head, rows):
    return '<div class="lab-scroll"><table class="lab-table"><thead><tr>' + ''.join(f'<th>{escape(x)}</th>' for x in head) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join(f'<td>{x}</td>' for x in row) + '</tr>' for row in rows) + '</tbody></table></div>'


def number(x, digits=3):
    return '—' if x is None else f'{x:.{digits}f}'


def picture(data, name, alt):
    if not name or name not in data.get('media', {}):
        return ''
    url = '/lab-media/' + escape(name, quote=True)
    return f'<a href="{url}"><img src="{url}" alt="{escape(alt, quote=True)}" loading="lazy" decoding="async"></a>'


def source(text):
    return f'<p class="lab-source">Source: {escape(text)}</p>'


def bars(rows):
    maximum = max((float(v) for _, v in rows), default=1) or 1
    return ''.join(f'<div class="lab-bar"><span>{escape(k)}</span><div class="lab-track"><i style="width:{100*v/maximum:.1f}%"></i></div><b>${v:.2f}</b></div>' for k, v in rows)


def progress_charts(policy):
    """Matched three-seed means only; no mixing seed-0 picks into the trend."""
    cards = []
    cohort = policy[:4]
    for key, title, suffix in [('yaw','Yaw error ↓','°'),('onset','Onset accuracy ↑','%'),
                               ('f1','Press F1 ↑',''),('still','Still false turns ↓','%')]:
        values = [r.get(key) for r in cohort]
        if len(values) != 4 or any(v is None for v in values):
            continue
        lo, hi = min(values), max(values)
        points = [(20+i*80, 65-(v-lo)/(hi-lo or 1)*40) for i,v in enumerate(values)]
        line = ' '.join(f'{x},{y:.1f}' for x,y in points)
        marks = ''.join(f'<circle cx="{x}" cy="{y:.1f}" r="4" fill="var(--mint)"/>' for x,y in points)
        labels = ''.join(f'<text x="{x}" y="95" text-anchor="middle" fill="var(--muted)" font-size="10">{label}</text>' for (x,_),label in zip(points,['Own','93k','399k','469k']))
        digits = 1 if suffix == '%' else 3
        cards.append(f'<article class="lab-card"><div class="eyebrow">{title}</div><h3>{number(values[0],digits)}{suffix} → {number(values[-1],digits)}{suffix}</h3><svg viewBox="0 0 280 105" role="img" aria-label="{title}: own, 93k, 399k, 469k; values {escape(str(values))}"><polyline points="{line}" fill="none" stroke="var(--mint)" stroke-width="2"/>{marks}{labels}</svg></article>')
    return '<div class="lab-grid lab-charts" style="margin-bottom:18px">' + ''.join(cards) + '</div>'


def render(data):
    if not data:
        return '<section class="panel empty-note">Achievement snapshot unavailable.</section>'
    asof = escape(data['as_of'])
    policy = data['policy']
    measured = [r for r in policy if r.get('hold') is not None and r.get('turn') is not None]
    passed = sum(readiness(r['hold'], r['turn']) == 'PASS' for r in measured)
    parts = [f'<nav class="lab-nav" aria-label="Lab sections">' + ''.join(f'<a href="#{key}">{title}</a>' for key, title in [('policy-progress','Policy'),('spend','Spend'),('sittings','Live sittings'),('results-timeline','Results'),('idm-quality','IDM'),('world-model','World model'),('recordings','Recordings'),('operations','Jobs')]) + '</nav>',
             f'<div class="lab-gate"><div class="eyebrow">THE NEXT GATE · LIVE-READINESS</div><h2>{passed} / {len(measured)} tested candidates pass.</h2><p>Expert footage improved offline imitation. Starting from still is the unresolved live problem. A candidate must reach hold ≥ 0.30 and turn ≥ 0.20 on the retained live frames; this is a screening check, not proof of autonomous play.</p><p class="lab-source">Results snapshot: {asof}. Job snapshot refreshes on page load.</p></div>']
    rows = []
    parts += ['<div class="lab-grid lab-charts lab-readiness">']
    for r in measured:
        checks = ''.join(f'<p><span>{label} ≥ {threshold:.2f}</span><b style="color:var(--{"mint" if r[key]>=threshold else "coral"})">{r[key]:.3f}</b></p>' for key,label,threshold in [('hold','Hold',.3),('turn','Turn',.2)])
        parts += [f'<article class="lab-card">{pill(readiness(r["hold"],r["turn"]))}<h3>{escape(r["name"])}</h3>{checks}</article>']
    parts += ['</div>']
    for r in policy:
        h, t = r.get('hold'), r.get('turn')
        rows.append([escape(r['name']), escape(r['seeds']), number(r.get('yaw')), number(r.get('onset'), 1), number(r.get('f1')), number(r.get('still'), 1), number(h), number(t), pill(readiness(h,t))])
    parts += ['<section class="lab-section" id="policy-progress"><h2>Better imitation. The live gap remains.</h2><p class="lab-note">Validation yaw error ↓ · onset sign accuracy ↑ · press F1 ↑ · still false turns ↓. Three-seed averages and individual deployment candidates are labelled separately. A dash means unreported, never zero.</p>', progress_charts(policy), table(['Candidate','Seeds','Yaw °/step ↓','Onset % ↑','Press F1 ↑','Still turn % ↓','Live hold','Live turn','Live check'],rows), '<p class="lab-note">Grid k and l also required val yaw ≤ 0.766 and press F1 ≥ 0.33. Their reported offline scores pass; their live hold/turn check fails. mix399 remains the offline camera pick.</p>', source('docs/lanes/policy.md · 2026-09-30 verdicts; retained learned-01-a frames'), '</section>']
    billing = data['billing']
    total, cap = billing['total'], billing['cap']
    attributed = data['attributed_spend']
    parts += [f'<section class="lab-section" id="spend"><h2>What the learning cost</h2><div class="lab-grid"><article class="lab-card"><div class="eyebrow">MODAL · MONTH TO DATE</div><div class="lab-number">${total:.2f}</div><p>of ${cap:.0f} cap · ${max(0,cap-total):.2f} remaining</p><div class="lab-track lab-budget"><i style="width:{min(100,total/cap*100):.1f}%"></i></div><p>Billing observed {escape(billing["as_of"])}. Snapshot, not a live meter.</p></article>',
              f'<article class="lab-card"><div class="eyebrow">KEPT · ATTRIBUTED SUBSET</div><div class="lab-number">${attributed["kept"]:.2f}</div><p>{escape(attributed["kept_note"])}</p></article>',
              f'<article class="lab-card"><div class="eyebrow">DID NOT PAY OFF · SUBSET</div><div class="lab-number" style="color:var(--orange)">${attributed["discarded"]:.2f}</div><p>{escape(attributed["discarded_note"])}</p></article></div><p class="lab-note">Outcome attribution uses owner-recorded run costs (some estimates), not an invoice reconciliation. Other spend is mixed or unattributed. Shared app bills appear once in billing; timeline costs must not be added together.</p>',
              '<div class="lab-split"><article class="lab-card"><h3>By day · UTC</h3>' + bars(billing['days']) + '</article><article class="lab-card"><h3>By app · largest first</h3>' + bars(billing['apps'][:8]) + '<details class="technical"><summary>All remaining apps</summary>' + bars(billing['apps'][8:]) + '</details></article></div>', source('Modal billing report · profile rivals / workspace volpestyle; docs/steering/spend-ledger-20260927.md'), '</section>']
    parts += ['<section class="lab-section" id="sittings"><h2>What happened in the range</h2><p class="lab-note">Retained live evidence. Compatibility, execution and learning are different checks.</p><div class="lab-grid">']
    for r in data['sittings']:
        parts += [f'<article class="lab-card"><div class="eyebrow">{escape(r["date"])}</div><h3>{escape(r["name"])}</h3>{pill(r["verdict"])}{picture(data,r["image"],r["name"])}<p>{escape(r["result"])}</p><p><b>Stop:</b> {escape(r["stop"])}</p><p>{escape(r["counts"])}</p>']
        if r.get('extra_image'):
            parts += ['<details class="technical"><summary>Takeover check sheet</summary>', picture(data,r['extra_image'],'Retained takeover check sheet'), '</details>']
        parts += [source(r['source']), '</article>']
    parts += ['</div></section><section class="lab-section" id="results-timeline"><h2>The results, including the negatives</h2><p class="lab-note">Kept means the owner retained the result for its stated scope. It does not mean live-ready. Ordered by the source ledger, followed by later decisions; dates are report dates, not inferred launch times.</p><div class="lab-timeline">']
    for r in data['runs']:
        visual = f'<details><summary>View retained visual</summary>{picture(data,r.get("image"),r["name"])}</details>' if r.get('image') else ''
        parts += [f'<article class="lab-card"><div class="eyebrow">{escape(r["date"])} · {r["id"]:02d}</div><h3>{escape(r["name"])}</h3>{pill(r["verdict"])}<span class="lab-cost">{escape(r["cost"])}</span><p>{escape(r["result"])}</p><p class="lab-source">Decision: {escape(r["decision"])}</p>{visual}</article>']
    parts += ['</div>', source('Lead’s 23-row runs ledger (2026-09-30 14:05 CDT), superseded by later policy/rl lane verdicts where noted'), '</section>']
    idm_rows = [[escape(r['name']), number(r['yaw']), number(r['pitch']), escape(r['press'])] for r in data['idm']]
    parts += ['<section class="lab-section" id="idm-quality"><h2>Reading actions from video</h2><p class="lab-note">Same held-out match -11 across versions. Moving yaw/pitch MAE in degrees per 60 Hz interval; press F1 is jump / combo / cluster. These units differ from policy steps.</p>', table(['IDM version','Yaw ↓','Pitch ↓','Press F1 ↑'],idm_rows), '<p class="lab-note">v2-cd is the better labeller; the matched policy grid j still found no downstream yaw gain. <a href="/idm-labelling">Explore the labelling pipeline →</a></p>', source('docs/lanes/inverse-dynamics.md · v2 variants'), '</section>']
    parts += ['<section class="lab-section" id="world-model"><h2>Imagining the next few seconds</h2><p class="lab-note">A useful short-horizon prototype; the 2–3 second goal is unmet. Mean-prediction PSNR (dB) on [0,1], one seed. full-01 is scored at half resolution. GIFs show real and imagined frames, not autonomous gameplay.</p><div class="lab-grid">']
    for r in data['world_models']:
        parts += [f'<article class="lab-card"><h3>{escape(r["name"])}</h3>{pill(r["verdict"])}{picture(data,r["image"],r["name"]+" real versus imagined")}<p><b>{r["db"][0]:.1f} / {r["db"][1]:.1f} / {r["db"][2]:.1f} dB</b><br>+0.1 s / +1 s / +3 s</p><p>{escape(r["note"])}</p></article>']
    parts += ['</div><p class="lab-note">Copy-last baseline: 15.3 / 12.7 / 12.3 dB. Imagined reward remains unreliable, so these rollouts are not yet a simulator for RL.</p>',source('docs/lanes/rl.md §5b · per-window mean PSNR; rl/world_model/out/*/eval.json'), '</section>']
    parts += ['<section class="lab-section" id="recordings"><h2>The demonstrations behind it</h2><div class="lab-grid">']
    for r in data['recordings']:
        parts += [f'<article class="lab-card"><div class="eyebrow">{escape(r["name"])}</div><div class="lab-number">{escape(r["value"])}</div><p>{escape(r["note"])}</p></article>']
    parts += ['</div><p class="lab-note">James: <b>7.0 KOs/min</b> over 186 minutes. Scripted reference: <b>4.2 KOs/min</b> in a five-minute run. Historical contexts differ; this is not a paired benchmark or a learned-policy score.</p>',source('docs/recording-log.md; docs/lanes/rl.md §3; source ledger'), '</section>']
    return ''.join(parts)
