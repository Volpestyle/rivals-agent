"""Record the owner's completed inspection of the 149 supplied -12 JPEGs."""
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'data/human/sessions/code-snapshot-f8fd92c-ping-20260927'))
from agent import human_intake as hi

sid = '20260927T061900-143Z-150600-12'
d = root / 'data/human/sessions' / sid
out = root / 'data/admission-codex/review-12'
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

notes = {'seg-002': 'Own setup-room movement, wall crawl, exit and combat in all seven samples. Initial OBS window is outside this accept. Final frame6936 remains live at20HP before death; independent edge check required.', 'seg-009': 'Own respawn exit, traversal and combat in all five samples. Reader misses10668/11826 are own play with118/105HP under effects. Final frame12984 remains live at20HP before death.', 'seg-016': 'Own respawn traversal, combat and ultimate in all seven samples. Reader miss19980 is own play at239HP under effects. Last frame21072 remains live at19HP before death.', 'seg-021': 'Own respawn traversal and combat in all three samples; ends alive at205HP before scoreboard and subsequent round transition. Passive chat is not a menu.', 'seg-029': 'Own next-round setup-room movement in all five samples with own HUD and camera. Countdown and teammates are live play; this ends before UI cut.', 'seg-033': 'Own setup exit, traversal and combat in all six samples. Objective banner overlays own play. Last frame35352 remains alive at120HP before death.', 'seg-036': 'Own respawn traversal, combat and healing in all six samples, including bonus HP. Ends live at59HP in frame42467 before middle-button ping cut.', 'seg-040': 'Own traversal, healing, combat and ultimate in all fourteen samples. Bonus HP and close wall camera remain own play. Last frame58018 shows own live swing/combat at250HP before final UI and round transition; native edge check required.'}

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
assert not ui and not overlaps and not unknown_mouse and not focus
assert unknown_keys == [dict(segment='seg-016', t_rel_s=170.3793789, vk=86)]
notes['seg-016'] += ' Unidentified V (VK86) at170.3793789s requires independent native event-neighborhood inspection before admission; sparse supplied images do not establish its effect.'
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
        if key in ('seg-003','seg-004','seg-005','seg-006','seg-010','seg-011','seg-012','seg-013','seg-017','seg-018','seg-019','seg-034'): reason += ' Scoreboard/death/Past Lives replay excluded.'
        if key in ('seg-024','seg-025','seg-026','seg-027','seg-028','seg-042','seg-043','seg-044','seg-045','seg-046','seg-047'): reason += ' Round transition or final scoreboard/defeat/MVP sequence excluded.'
    verdicts[key] = dict(suitability=decision, reason=reason, reviewer='admission-codex (owner; independent review required)', reviewed_at=stamp,
                         evidence='All 149 supplied JPEGs visually inspected through review-12/page-00.jpg through page-18.jpg',
                         frames=[{k:f[k] for k in ('frame_index','composition_ns','decoded_bgr_sha256')} for f in frames])
assert sum(len(s['review_frames']) for s in ev['segments']) == 149
def write(path, doc):
    assert not path.exists(), path
    path.write_text(json.dumps(doc, indent=1)+'\n', encoding='utf-8', newline='\n')
write(out/'input-audit.json', audit)
doc = dict(session=sid, segments_evidence_sha256=sha(d/'segments-evidence.json'), reviewer='admission-codex', reviewed_at=stamp,
           role='owner visual inspection; provisional until independent frame verdicts and admission review',
           method='Inspected all 149 supplied JPEGs in nineteen contact sheets and verified JPEG and evidence-input hashes. Replayed all key/button events in the eight candidate accepts, including middle-button hold plus settle overlaps. No new decode for owner inspection.',
           limits=['Sparse supplied JPEGs cannot establish all intervening frames. Native independent review required at event neighborhoods and death/final-round edges.', 'V (VK86) at170.3793789s in seg-016 is unidentified and requires native review before admission.'],
           input_audit=dict(path=(out/'input-audit.json').relative_to(root).as_posix(), sha256=sha(out/'input-audit.json')), verdicts=verdicts)
write(d/'owner-verdicts.json', doc)
write(out/'segment-list.json', dict(session=sid, evidence_sha256=sha(d/'segments-evidence.json'), owner_sha256=sha(d/'owner-verdicts.json'),
      segments=[dict(segment_id=s['segment_id'], start_ns=s['start_ns'], end_ns=s['end_ns'], t_rel_s=s['t_rel_s'], verdict=verdicts[s['segment_id']]['suitability'], machine_reason=s['machine_reason']) for s in ev['segments']],
      accepted_count=len(notes), accepted_ns=audit['candidate_ns'], native_event_checks=comms+scroll+unknown_keys))
print(json.dumps(dict(evidence=sha(d/'segments-evidence.json'), owner=sha(d/'owner-verdicts.json'), segment_list=sha(out/'segment-list.json'), input_audit=sha(out/'input-audit.json'), audit=audit)))
