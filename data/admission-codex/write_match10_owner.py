"""Record completed owner visual inspection of all 175 -10 review JPEGs."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sid = '20260927T060021-195Z-150600-10'
d = root / 'data/human/sessions' / sid
out = root / 'data/admission-codex/review-10'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
ev = json.loads((d / 'segments-evidence.json').read_text())
audit = json.loads((out / 'input-audit.json').read_text())
assert audit['evidence_sha256'] == sha(d / 'segments-evidence.json')
assert audit['ui_key_down_count'] == audit['ping_cut_overlap_count'] == 0
assert not audit['unbound_key_down_events'] and not audit['unbound_mouse_down_events'] and not audit['focus_events']
notes = {
    'seg-002': 'Own setup-room traversal, wall crawling and subsequent combat in all eight samples. Objective banners overlay own play; final frame is live at 87 HP before the ping cut.',
    'seg-006': 'Own healing and combat in all three samples after ping settle, ending alive at 33 HP before the death cut.',
    'seg-013': 'Own respawn traversal and combat in seven samples, including a close wall camera; live HUD persists. Frame 15040 is an apparent reader miss on own play. No replay panel in these samples.',
    'seg-017': 'Own traversal ending in an apparent fall while still alive at 217 HP. This precedes the death and self-replay; supplied samples contain no Past Lives/Defeated By panel. Independent native edge check required.',
    'seg-024': 'Own respawn and combat in all six samples, ending alive before the round transition. Frames 22894, 24953 and 25982 are apparent reader misses on own gameplay.',
    'seg-032': 'Own setup-room movement before the next objective, all five samples own HUD and camera. Setup countdown is not a cut.',
    'seg-040': 'Own setup exit, traversal, ultimate and combat in all ten samples, ending alive before the ping cut. Frame 42459 is an apparent reader miss. Scroll-up at logger 348.5132994 s needs independent native event-neighborhood inspection.',
    'seg-044': 'Own healing and combat in all five samples after ping settle. Frames 45011 and 47339 are apparent reader misses on own play; last sample remains alive at 11 HP.',
    'seg-051': 'Own respawn, combat and ultimate in all ten samples. Reader misses at 50979, 53144 and 54227 are own gameplay under effects/bonus HP. Last frame is alive at 17 HP before the death cut.',
}
rejects = {
    'seg-021': 'VISUAL REJECTION overriding unresolved proposal: all three supplied frames show Past Lives and Defeated By replay panels, despite own Spider-Man HUD being reader-positive. This is a replay of his own fall/death, not live control; reject the entire span.',
    'seg-057': 'VISUAL REJECTION overriding unresolved proposal: earlier supplied frames show own play, but final frame 64699 already dissolves into the Capture the Royal Palace round-transition screen. Reject the entire bounded span conservatively; do not infer HUD-positive means live control.',
}
assert set(notes) == set(audit['candidate_ids'])
stamp = datetime.now(timezone.utc).isoformat()
verdicts = {}
for s in ev['segments']:
    key = s['segment_id']; frames = s['review_frames']
    for f in frames:
        assert sha(d / f['image']) == f['image_sha256']
    if key in notes:
        assert s['proposal'] == 'unresolved' and frames[0]['own_hud'] and frames[-1]['own_hud']
        decision, reason = 'accepted', notes[key]
    elif key in rejects:
        decision, reason = 'rejected', rejects[key]
    else:
        decision = 'rejected'
        reason = s['machine_reason'] + ': retained intake exclusion. '
        reason += ('All supplied samples visually inspected; conservative cuts remain even when a boundary sample shows own play.' if frames else 'Zero-frame sliver; no visual claim.')
        if key in ('seg-019', 'seg-020', 'seg-022'):
            reason += ' Self-replay occurs here; the own-HUD flag does not establish live control.'
    verdicts[key] = dict(suitability=decision, reason=reason, reviewer='admission-codex (owner; independent review required)', reviewed_at=stamp,
                         evidence='segments-evidence.json and all supplied JPEGs visually inspected through data/admission-codex/review-10/page-00.jpg through page-21.jpg',
                         frames=[{k: f[k] for k in ('frame_index', 'composition_ns', 'decoded_bgr_sha256')} for f in frames])
doc = dict(session=sid, segments_evidence_sha256=sha(d / 'segments-evidence.json'), reviewer='admission-codex', reviewed_at=stamp,
           role='owner visual inspection; provisional until independent frame verdicts and admission review',
           method='Inspected all 175 supplied JPEGs in 22 contact sheets. Verified every JPEG and evidence-input hash. Rejected seg-021 self-replay and seg-057 transition despite unresolved machine proposals. Input replay found no UI makes, ping overlap, unknown key/button or focus events in accepts. One scroll event requires native review. No new decode during owner inspection.',
           limits=['Sparse JPEGs cannot prove every intervening frame. Native review required around scroll event, own-HUD reader misses, self-replay boundaries and final round transition.'],
           input_audit=dict(path=out.relative_to(root).as_posix() + '/input-audit.json', sha256=sha(out / 'input-audit.json')), verdicts=verdicts)
target = d / 'owner-verdicts.json'; assert not target.exists()
target.write_text(json.dumps(doc, indent=1) + '\n', encoding='utf-8', newline='\n')
listing = dict(session=sid, evidence_sha256=sha(d / 'segments-evidence.json'), owner_sha256=sha(target),
               segments=[dict(segment_id=s['segment_id'], start_ns=s['start_ns'], end_ns=s['end_ns'], t_rel_s=s['t_rel_s'], verdict=verdicts[s['segment_id']]['suitability'], machine_reason=s['machine_reason']) for s in ev['segments']],
               accepted_count=len(notes), accepted_ns=audit['candidate_ns'], native_event_checks=audit['scroll_events'], visual_rejections=rejects)
list_path = out / 'segment-list.json'; assert not list_path.exists()
list_path.write_text(json.dumps(listing, indent=1) + '\n', encoding='utf-8', newline='\n')
print(json.dumps(dict(evidence=sha(d / 'segments-evidence.json'), owner=sha(target), segment_list=sha(list_path), input_audit=sha(out / 'input-audit.json'), accepted=len(notes), rejected=len(verdicts)-len(notes), accepted_s=audit['candidate_ns']/1e9)))
