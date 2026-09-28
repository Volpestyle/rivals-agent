"""Record the owner's completed inspection of the 74 supplied -11 JPEGs."""
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'data/human/sessions/code-snapshot-f8fd92c-ping-20260927'))
from agent import human_intake as hi

sid = '20260927T061107-953Z-150600-11'
d = root / 'data/human/sessions' / sid
out = root / 'data/admission-codex/review-11'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
ev = json.loads((d / 'segments-evidence.json').read_text())
prov = json.loads((d / 'provenance.json').read_text())
profile = json.loads((d / 'input-profile.json').read_text())
raw = Path('C:/Users/volpe/Videos/RivalsInput') / sid / 'inputs.jsonl'
assert sha(raw) == prov['raw_files']['inputs.jsonl']
events = [json.loads(line) for line in raw.read_text().splitlines()]
for pin in ev['inputs'].values():
    assert sha(d / pin['path']) == pin['sha256']
for step in ('vote', 'scan', 'regime', 'motor', 'propose', 'evidence'):
    run_bytes = (root / 'data/admission-codex/runs' / sid / (step + '.run.json')).read_bytes()
    run = json.loads(run_bytes)
    assert run['session'] == sid and run['exit_code'] == 0 and not run['failure']

notes = {
    'seg-002': 'Own setup traversal across trees and roofs, own camera and HUD in all three samples.',
    'seg-006': 'Own roof exit, traversal, combat and healing in all nine samples. Final frame remains alive at 129 HP. Passive team chat is not a menu.',
    'seg-010': 'Own healing and combat in all five samples. Frame 14982 is a reader miss under pink shark/teammate effects with own 100 HP HUD; later bonus HP remains own play. Ends alive at 170 HP.',
    'seg-014': 'Own traversal, healing and combat in all twelve samples. Frame 22407 is a reader miss with own 164 HP HUD. Final frame 31848 remains own live camera at 55 HP before the death cut; independent native edge check required.',
    'seg-021': 'Own respawn exit, traversal, combat and healing in all eight samples. Bonus HP and objective countdown overlay live control. Last frame 40928 shows own combat at 300 HP before the final UI/scoreboard/MVP cut; independent native edge check required.',
}
candidates = [s for s in ev['segments'] if s['segment_id'] in notes]
assert {s['segment_id'] for s in ev['segments'] if s['proposal'] == 'unresolved'} == set(notes)
ping = hi.ping_wheel_cuts(events, profile['focused_intervals'])
keys, mouse = Counter(), Counter()
ui, unknown_keys, unknown_mouse, comms, scroll, focus, overlaps = [], [], [], [], [], [], []
known_keys = {87,65,83,68,32,16,17,67,69,70,81,50,20}
t0 = prov['metadata']['start_ns']
for s in candidates:
    a,b = s['start_ns'], s['end_ns']
    for p,q,reason in ping:
        if max(a,p) < min(b,q):
            overlaps.append(dict(segment=s['segment_id'], start_ns=p, end_ns=q))
    for e in events:
        if not a <= e['t_ns'] < b:
            continue
        item = dict(segment=s['segment_id'], t_rel_s=(e['t_ns']-t0)/1e9)
        if e['type'] == 'key' and e['down']:
            vk = e['vk']; keys[vk] += 1; item['vk'] = vk
            if vk in hi.UI_KEYS: ui.append(item)
            elif vk == 52: comms.append(item)
            elif vk not in known_keys: unknown_keys.append(item)
        elif e['type'] == 'mouse':
            for button in e['buttons_down']:
                mouse[button] += 1
                if button not in (1,2,4,5): unknown_mouse.append(dict(item, button=button))
            if e['wheel_vertical'] or e['wheel_horizontal']:
                scroll.append(dict(item, vertical=e['wheel_vertical'], horizontal=e['wheel_horizontal']))
        elif e['type'] == 'focus': focus.append(dict(item, active=e['active']))
audit = dict(session=sid, input_sha256=sha(raw), evidence_sha256=sha(d/'segments-evidence.json'),
             candidate_ids=list(notes), candidate_ns=sum(s['end_ns']-s['start_ns'] for s in candidates),
             ui_key_down_count=len(ui), ui_key_down_events=ui, ping_cut_overlap_count=len(overlaps), ping_cut_overlaps=overlaps,
             key_down_counts=dict(keys), mouse_down_counts=dict(mouse), unbound_key_down_events=unknown_keys,
             unbound_mouse_down_events=unknown_mouse, thank_you_comms_events=comms, scroll_events=scroll, focus_events=focus,
             ping_cuts_ns=ping, note='Keyboard 4 is thank-you comms, no cut and outside gameplay vocabulary. Native independent review still required.')
assert not ui and not overlaps and not unknown_keys and not unknown_mouse and not focus
stamp = datetime.now(timezone.utc).isoformat()
verdicts = {}
for s in ev['segments']:
    frames = s['review_frames']; key = s['segment_id']
    for f in frames: assert sha(d/f['image']) == f['image_sha256']
    if key in notes:
        assert frames[0]['own_hud'] and frames[-1]['own_hud']
        decision, reason = 'accepted', notes[key]
    else:
        decision = 'rejected'
        reason = s['machine_reason'] + ': retained conservative intake exclusion. '
        reason += 'All supplied samples visually inspected.' if frames else 'Zero-frame sliver; no visual claim.'
        if key in ('seg-016','seg-017','seg-018'): reason += ' Scoreboard/death/Past Lives replay excluded.'
        if key == 'seg-023': reason += ' Final scoreboard and MVP sequence excluded.'
    verdicts[key] = dict(suitability=decision, reason=reason, reviewer='admission-codex (owner; independent review required)', reviewed_at=stamp,
                         evidence='All 74 supplied JPEGs visually inspected through review-11/page-00.jpg through page-09.jpg',
                         frames=[{k:f[k] for k in ('frame_index','composition_ns','decoded_bgr_sha256')} for f in frames])
assert sum(len(s['review_frames']) for s in ev['segments']) == 74
def write(path, doc):
    assert not path.exists(), path
    path.write_text(json.dumps(doc, indent=1)+'\n', encoding='utf-8', newline='\n')
write(out/'input-audit.json', audit)
doc = dict(session=sid, segments_evidence_sha256=sha(d/'segments-evidence.json'), reviewer='admission-codex', reviewed_at=stamp,
           role='owner visual inspection; provisional until independent frame verdicts and admission review',
           method='Inspected all 74 supplied JPEGs in ten contact sheets and verified JPEG and evidence-input hashes. Replayed all key/button events in the five candidate accepts, including middle-button hold plus settle overlaps. No new decode for owner inspection.',
           limits=['Sparse supplied JPEGs cannot establish all intervening frames. Native independent review required at event neighborhoods and death/final-round edges.'],
           input_audit=dict(path=(out/'input-audit.json').relative_to(root).as_posix(), sha256=sha(out/'input-audit.json')), verdicts=verdicts)
write(d/'owner-verdicts.json', doc)
write(out/'segment-list.json', dict(session=sid, evidence_sha256=sha(d/'segments-evidence.json'), owner_sha256=sha(d/'owner-verdicts.json'),
      segments=[dict(segment_id=s['segment_id'], start_ns=s['start_ns'], end_ns=s['end_ns'], t_rel_s=s['t_rel_s'], verdict=verdicts[s['segment_id']]['suitability'], machine_reason=s['machine_reason']) for s in ev['segments']],
      accepted_count=len(notes), accepted_ns=audit['candidate_ns'], native_event_checks=comms+scroll))
print(json.dumps(dict(evidence=sha(d/'segments-evidence.json'), owner=sha(d/'owner-verdicts.json'), segment_list=sha(out/'segment-list.json'), input_audit=sha(out/'input-audit.json'), audit=audit)))
