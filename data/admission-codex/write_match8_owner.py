"""Record completed -8 owner inspection; independent native review is still required."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sid = '20260927T055006-068Z-150600-8'
d = root / 'data/human/sessions' / sid
out = root / 'data/admission-codex/review-8'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
ev = json.loads((d / 'segments-evidence.json').read_text())
audit = json.loads((out / 'input-audit.json').read_text())
assert audit['evidence_sha256'] == sha(d / 'segments-evidence.json')
assert audit['ui_key_down_count'] == audit['ping_cut_overlap_count'] == 0
assert not audit['focus_events'] and not audit['scroll_events'] and not audit['unbound_mouse_down_events']
notes = {
    'seg-002': 'Own setup-room swinging and movement, own HUD in all three samples; the setup countdown is not an exclusion.',
    'seg-006': 'Own setup movement, exit and combat in all three samples; last frame has own live HUD at 119 HP.',
    'seg-012': 'Own traversal and combat in all ten samples. Collector gallery arrival is an objective banner over own play, not a separate camera. Frame 7307 is a HUD-reader miss with own live HUD visible. Last frame remains alive at 127 HP.',
    'seg-020': 'Own respawn traversal and close camera through his translucent body; own HUD persists. Contemplator garden arrival banner overlays gameplay.',
    'seg-024': 'Own traversal and combat in all four samples; final close camera is his own body at 59 HP before the conservative death boundary.',
    'seg-032': 'Own respawn traversal, combat and ultimate. Final stunned frame is own camera and live HUD at 70 HP; crowd control is gameplay.',
    'seg-039': 'Own respawn traversal and combat, ending on own live HUD at 29 HP. Adjacent HUD-unknown images also show own play; the conservative boundary stays.',
    'seg-043': 'Own healing, traversal and combat in all three supplied samples, ending at 79 HP. Unbound VK52 at logger 257.1049323 s requires independent native event-neighborhood inspection.',
    'seg-047': 'Own traversal, combat and web attacks in all five samples, ending alive at 2 HP. Unbound VK52 at logger 312.5987816 s requires independent native event-neighborhood inspection.',
    'seg-053': 'Own respawn traversal and combat in all three samples, ending alive at 107 HP before the death cut.',
    'seg-058': 'Own traversal, wall movement and combat in all five samples. Frame 44383 is a HUD-reader miss on his own live play; final sample remains alive at 90 HP.',
    'seg-062': 'Own combat and ultimate in all three samples; last frame remains alive at 55 HP before the conservative death cut.',
    'seg-067': 'Own respawn traversal into combat, including his own camera while swinging. Frame 49097 is a reader miss with own live HUD visible; final frame remains alive before the UI/end-screen exclusion.',
}
assert set(notes) == set(audit['candidate_ids'])
stamp = datetime.now(timezone.utc).isoformat()
verdicts = {}
for s in ev['segments']:
    key = s['segment_id']
    frames = s['review_frames']
    for f in frames:
        assert sha(d / f['image']) == f['image_sha256']
    if key in notes:
        assert s['proposal'] == 'unresolved' and frames[0]['own_hud'] and frames[-1]['own_hud']
        decision, reason = 'accepted', notes[key]
    else:
        decision = 'rejected'
        reason = s['machine_reason'] + ': retained intake exclusion. '
        reason += ('All supplied samples visually inspected; conservative cuts remain even where a boundary sample shows own play.' if frames else 'Zero-frame boundary sliver; no visual claim.')
        if key in ('seg-007', 'seg-010', 'seg-011', 'seg-018', 'seg-025', 'seg-030', 'seg-037', 'seg-040', 'seg-044', 'seg-052', 'seg-056', 'seg-057'):
            reason += ' Supplied images show own play; this rejection does not claim they depict a different camera.'
        if key == 'seg-069':
            reason += ' Scoreboard and end transition visible.'
    verdicts[key] = dict(suitability=decision, reason=reason, reviewer='admission-codex (owner; independent review required)', reviewed_at=stamp,
                         evidence='segments-evidence.json and all supplied JPEGs, visually inspected through data/admission-codex/review-8/page-00.jpg through page-22.jpg',
                         frames=[{k: f[k] for k in ('frame_index', 'composition_ns', 'decoded_bgr_sha256')} for f in frames])
doc = dict(session=sid, segments_evidence_sha256=sha(d / 'segments-evidence.json'), reviewer='admission-codex', reviewed_at=stamp,
           role='owner visual inspection; provisional until independent frame verdicts and admission review',
           method='Inspected all 178 supplied JPEGs in 23 labeled contact sheets; verified every JPEG and evidence-input hash. Input replay found zero UI-key makes, ping-cut overlap, scroll or focus events in proposed accepts. No new decode during owner inspection.',
           limits=['Sparse images do not prove all intervening frames. Independent native review must include both unbound VK52 event neighborhoods in input-audit.json.', 'HUD-reader misses and conservative rejected boundaries are explicitly retained; own setup movement is allowed under the own-HUD guard.'],
           input_audit=dict(path=out.relative_to(root).as_posix() + '/input-audit.json', sha256=sha(out / 'input-audit.json')), verdicts=verdicts)
target = d / 'owner-verdicts.json'
assert not target.exists()
target.write_text(json.dumps(doc, indent=1) + '\n', encoding='utf-8', newline='\n')
segment_list = dict(session=sid, evidence_sha256=sha(d / 'segments-evidence.json'), owner_sha256=sha(target),
                    segments=[dict(segment_id=s['segment_id'], start_ns=s['start_ns'], end_ns=s['end_ns'], t_rel_s=s['t_rel_s'], verdict=verdicts[s['segment_id']]['suitability'], machine_reason=s['machine_reason']) for s in ev['segments']],
                    accepted_count=len(notes), accepted_ns=audit['candidate_ns'], native_event_checks=audit['unbound_key_down_events'])
list_path = out / 'segment-list.json'
assert not list_path.exists()
list_path.write_text(json.dumps(segment_list, indent=1) + '\n', encoding='utf-8', newline='\n')
checks = []
for step in ('vote', 'scan', 'regime', 'motor', 'propose', 'evidence'):
    path = root / 'data/admission-codex/runs' / sid / (step + '.run.json')
    run = json.loads(path.read_text(encoding='utf-8-sig'))
    assert run['session'] == sid and run['exit_code'] == 0 and run['failure'] is None
    if step in ('propose', 'evidence'):
        assert 'code-snapshot-f8fd92c-ping-20260927' in run['arguments']
    checks.append(dict(step=step, path=path.relative_to(root).as_posix(), sha256=sha(path), exit_code=0, failure=None,
                       peak_process_bytes=max(run['process_peak_working_set_bytes'].values(), default=0)))
for entry in ev['inputs'].values():
    assert sha(d / entry['path']) == entry['sha256']
recon = dict(session=sid, checked_at=stamp, stages=checks, evidence_sha256=sha(d / 'segments-evidence.json'), evidence_inputs_verified=True,
             review_image_count=178, review_image_hashes_verified=True, snapshot_manifest_sha256=ev['snapshot_manifest_sha256'])
(out / 'run-reconciliation.json').write_text(json.dumps(recon, indent=1) + '\n', encoding='utf-8', newline='\n')
print(json.dumps(dict(evidence=sha(d / 'segments-evidence.json'), owner=sha(target), segment_list=sha(list_path), input_audit=sha(out / 'input-audit.json'), accepted=len(notes), rejected=len(verdicts)-len(notes), accepted_s=audit['candidate_ns']/1e9)))
