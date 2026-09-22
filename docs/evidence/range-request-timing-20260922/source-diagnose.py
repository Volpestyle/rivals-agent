"""Read-only source timing diagnosis of admitted n142/n199, stdlib only.

Run from the repository root: uv run --no-sync python -B
data/diagnostics/human-cast-request-timing-20260922/diagnose.py
Writes only report.json/report.md beside this script. No image/video decoding,
training, policy imports, label mutation or input execution.
"""
from pathlib import Path
from fractions import Fraction
import csv
import hashlib
import json

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
SESSION = Path('C:/Users/volpe/Videos/RivalsInput/20260922T032454-642Z-24328-1')
SCHEMA = Path('C:/Users/volpe/obs-input-logger/SCHEMA.md')
ADMITTED = ROOT/'data/human/skill-events/032454-train-diagnostic-v2/examples.json'
ANNOTATIONS = {
    142: ROOT/'data/human/skill-event-candidates/032454-support-v2/visual-annotations.json',
    199: ROOT/'data/human/skill-event-candidates/20260922T032454-642Z-24328-1/visual-annotations.json',
}

def read(p): return json.loads(p.read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p, obj): p.write_text(json.dumps(obj, indent=2, allow_nan=False)+'\n', encoding='utf-8')

assert sha(ADMITTED) == 'b12f7013b24482b505e44468eb723245a03d1e5a56bb46ab9d282cdf3e1001d5'
metadata = read(SESSION/'metadata.json')
assert metadata['complete'] and metadata['clean_stop'] and metadata['status'] == 'complete'
assert metadata['session_id'] == SESSION.name and metadata['video_path'] == 'C:/Users/volpe/Videos/2026-09-21 22-24-54.mkv'
assert not metadata['writer_failed'] and not metadata['queue_dropped_events'] and not metadata['raw_input_errors']
events = sorted((json.loads(line) for line in (SESSION/'inputs.jsonl').read_text().splitlines()),
                key=lambda e: (e['t_ns'], e['seq']))
packets = list(csv.DictReader((SESSION/'frames.csv').open(newline='')))
zero = [r for r in packets if int(r['track']) == 0 and int(r['pts']) == 0]
assert len(zero) == 1
FIRST = int(zero[0]['composition_ns'])
assert FIRST == 115370505348149
by_cts = {}
for packet in packets:
    if int(packet['track']) == 0:
        by_cts.setdefault(int(packet['composition_ns']), []).append(packet)
rows = {r['grid_index']:r for r in read(ADMITTED)['rows'] if r['grid_index'] in (142,199)}
ns = lambda t: FIRST + round(t*1e9)
relative = lambda t: (t-FIRST)/1e9

def transitions(e):
    if e['type'] != 'mouse': return True
    return bool(e['buttons_down'] or e['buttons_up'] or e['wheel_vertical'] or e['wheel_horizontal'])

def decorated(e, anchor_ns):
    return dict(raw=e, composition_relative_t=relative(e['t_ns']),
                offset_from_anchor_ns=e['t_ns']-anchor_ns,
                offset_from_anchor_ms=(e['t_ns']-anchor_ns)/1e6)

def receipt_state_at(t_ns):
    # Device-local transitions; focus snapshots are separately reported, never
    # fabricated as per-device down events. Unknown reset boundaries clear holds.
    latest = {}
    focus = None
    boundaries = []
    repeats = []
    for e in events:
        if e['t_ns'] > t_ns: break
        typ = e['type']
        if typ == 'focus':
            focus = e
            latest.clear()
            boundaries.append(e)
        elif typ in ('gap','pause'):
            latest.clear()
            boundaries.append(e)
        elif typ == 'key':
            key = ('key',e['device'],e['scan'],e['flags'] & 6)
            if e['down'] and key in latest and latest[key]['down']:
                repeats.append(e['seq'])
            latest[key] = {'down':e['down'],'raw':e}
        elif typ == 'mouse':
            for button in e['buttons_down']:
                key = ('mouse',e['device'],button)
                if key in latest and latest[key]['down']: repeats.append(e['seq'])
                latest[key] = {'down':True,'raw':e}
            for button in e['buttons_up']:
                latest[('mouse',e['device'],button)] = {'down':False,'raw':e}
    return dict(at_ns=t_ns, composition_relative_t=relative(t_ns),
                latest_focus=focus,
                observed_held_controls=[dict(control=list(k),down_event=v['raw']) for k,v in latest.items() if v['down']],
                mouse_button_latest=[dict(control=list(k),**v) for k,v in latest.items() if k[0]=='mouse'],
                repeated_down_event_ids=sorted(set(repeats)),
                last_continuity_boundary=boundaries[-1] if boundaries else None,
                scope='Received device-local transitions since latest focus/reset. Focus held_vk is aggregate snapshot, not device attribution. Physical delivery/bindings remain unknown.')

def frame(t, annotations):
    absolute = ns(t)
    matches = by_cts[absolute]
    assert len(matches) == 1
    packet = matches[0]
    file_ms = round(Fraction(int(packet['pts'])*1000*int(packet['timebase_num']),int(packet['timebase_den'])))+21
    evidence = next((f for f in annotations if f['composition_ns']==absolute), None)
    if evidence: assert file_ms == evidence['file_pts_num']
    return dict(composition_relative_t=t, composition_ns=absolute,
                callback_event_seq=int(packet['event_seq']), callback_packet_index=int(packet['packet_index']),
                callback_pts=int(packet['pts']), callback_timebase=[int(packet['timebase_num']),int(packet['timebase_den'])],
                original_file_pts_ms=file_ms, frozen_image_evidence=evidence)

windows = []
for n,row in sorted(rows.items()):
    assert row['label_known'] and row['label']=='start'
    anchor_ns = FIRST+n*100_000_000
    low,high = anchor_ns-600_000_000,anchor_ns+600_000_000
    window_events = [e for e in events if low<=e['t_ns']<=high]
    selected = [e for e in window_events if transitions(e)]
    ann = next(r for r in read(ANNOTATIONS[n]) if r['grid_index']==n)
    evidence = ann.get('frame_evidence',ann.get('evidence_frames',[]))+ann.get('causal_history_evidence',[])
    history = [frame(h['state']['t'],evidence) for h in row['history']]
    right_downs = [e for e in selected if e['type']=='mouse' and 2 in e['buttons_down']]
    right_ups = [e for e in selected if e['type']=='mouse' and 2 in e['buttons_up']]
    assert len(right_downs)==len(right_ups)==1, 'Report needs explicit multi-transition handling; never choose a hidden nearest press'
    down,up = right_downs[0],right_ups[0]
    assert down['device']==up['device'] and down['t_ns']<up['t_ns']
    last = frame(row['last_not_started_t'],evidence)
    first = frame(row['first_started_t'],evidence)
    confirm = frame(row['confirmation_t'],evidence)
    motion = [e for e in window_events if e['type']=='mouse']
    windows.append(dict(grid_index=n,target='named Luna Snow hero simulation' if n==142 else 'nearby Galacta',
        accepted_event_id=row['event_id'],accepted_review_sha256=row['review_sha256'],
        scope_relative_s=[relative(low),relative(high)],scope_absolute_ns=[low,high],
        anchor_t=row['anchor_t'],anchor_ns=anchor_ns,actual_causal_history=history,
        right_mouse_down=decorated(down,anchor_ns),right_mouse_up=decorated(up,anchor_ns),
        right_hold_duration_ms=(up['t_ns']-down['t_ns'])/1e6,
        anchor_after_right_receipt_ms=(anchor_ns-down['t_ns'])/1e6,
        final_history_after_right_receipt_ms=(history[-1]['composition_ns']-down['t_ns'])/1e6,
        history_frames_before_receipt=sum(f['composition_ns']<down['t_ns'] for f in history),
        history_frames_after_receipt=sum(f['composition_ns']>down['t_ns'] for f in history),
        accepted_visual_last_not_started=last,accepted_visual_first_started=first,accepted_confirmation=confirm,
        visual_onset_after_receipt_ms=[(last['composition_ns']-down['t_ns'])/1e6,(first['composition_ns']-down['t_ns'])/1e6],
        confirmation_after_receipt_ms=(confirm['composition_ns']-down['t_ns'])/1e6,
        all_control_transitions=[decorated(e,anchor_ns) for e in selected],
        state_at_window_start=receipt_state_at(low),state_at_anchor=receipt_state_at(anchor_ns),
        state_at_emission=receipt_state_at(first['composition_ns']),state_at_window_end=receipt_state_at(high),
        mouse_motion_summary=dict(packets=len(motion),relative_packets=sum(e['relative'] for e in motion),
                                  nonzero_motion_packets=sum(bool(e['dx'] or e['dy']) for e in motion),
                                  interpretation='Raw motion retained in button-transition packets; other motion summarized, not converted to aim or inferred ability.'),
        conflicting_control_note='Left button down seq2692 at13.944991151 stays held through anchor/emission until up2798 at14.384998151.' if n==142 else 'No other mouse transition within the window; no other control inferred to be a web binding.',
        interpretation='The received right-mouse down precedes anchor and final causal frame; correspondence to this cast is plausible temporal evidence, not proven source binding or physical-input delivery time.'))

sources = [SESSION/'metadata.json',SESSION/'inputs.jsonl',SESSION/'frames.csv',SCHEMA,ADMITTED,*ANNOTATIONS.values()]
report = dict(kind='read_only_two_positive_anchor_received_input_timing_diagnosis',session=SESSION.name,
    original_media_sha256=rows[142]['media_sha256'],script_sha256=sha(Path(__file__)),
    sources=[dict(path=str(path),sha256=sha(path)) for path in sources],
    clock=dict(origin_composition_ns=FIRST,shared_clock=metadata['clock'],
               input_semantics=metadata['input_time_semantics'],video_semantics=metadata['video_time_semantics'],
               accepted_original_mux_offset_ms=21,formula='relative_t=(event.t_ns-FIRST)/1e9; grid_anchor_ns=FIRST+n*100000000. Frame CTS comes directly from CSV; callback receipt/order not used as frame time.',
               capture_latency_calibrated=metadata['capture_latency_calibrated']),
    state_reconstruction_scope='Inputs file read to preserve received held states across +/-0.6s boundaries. Only two requested event windows reported; earlier transitions only retained as carry-in state provenance. No other media/session scan.',
    windows=windows,
    conclusions=['Both positive anchors follow one received right-mouse down and precede its up; first four history frames precede receipt, fifth follows it.',
                 'If those right-mouse presses initiated the visually accepted casts, these anchors forecast already-requested actions rather than necessarily choosing a fresh request. Temporal association alone does not prove that condition.',
                 'Measured receipt-to-visible-first-started intervals are about102.016ms and115.678ms. These are compatible in scale with the lead-reported pad calibrationD delay, but this script neither opens nor independently validates D and does not equate KBM/pad paths.',
                 'No source binding inferred from button presence, no physical delivery/game-render/player-view latency inferred, no horizon/labels/features/admission/model changes. Root decides any semantic implication.'])
write(BASE/'report.json',report)

lines=['# Received mouse input versus two admitted visual-emission anchors','',
       'Both anchors occur after a received raw right-mouse down. This establishes recorded ordering on the shared OBS clock; it does not prove physical press timing, binding or causal delivery to the game. Admitted labels remain unchanged.','',
       'All times below are composition-relative seconds; deltas are milliseconds. Raw event IDs are original `seq`. Each window is anchor +/-0.6s.','',
       '| Bin / target | Five actual history times | Right down / up (seq; time) | Anchor; after down | Accepted visual bracket; delay after down | Confirmation |',
       '|---|---|---|---|---|---|']
for w in windows:
    times=', '.join(f"{f['composition_relative_t']:.9f}" for f in w['actual_causal_history'])
    d,u=w['right_mouse_down'],w['right_mouse_up'];lo,hi=w['visual_onset_after_receipt_ms']
    lines.append(f"| n{w['grid_index']} / {w['target']} | {times} | down#{d['raw']['seq']} {d['composition_relative_t']:.9f}; up#{u['raw']['seq']} {u['composition_relative_t']:.9f} | {w['anchor_t']:.1f}; +{w['anchor_after_right_receipt_ms']:.6f}ms | ({w['accepted_visual_last_not_started']['composition_relative_t']:.9f}, {w['accepted_visual_first_started']['composition_relative_t']:.9f}]; (+{lo:.6f}, +{hi:.6f}]ms | {w['accepted_confirmation']['composition_relative_t']:.9f} |")
lines += ['',
    'For each bin, four history frames precede right-down receipt and only the fifth follows it. The final actual frame follows receipt by2.015781ms (n142) and24.011353ms (n199). Right mouse remains held at each anchor and first-started frame. Holds last140.004700ms and140.108300ms, respectively.','',
    'n142 has a conflicting/overlapping left-button hold: down#2692 at13.944991151, up#2798 at14.384998151, spanning the anchor and visual onset. Its other received transitions are S/Space/D releases and presses before the anchor, then W, Space, E and A transitions afterward. n199 carries W/A/Space from earlier received downs into the window; their releases are#3845/#3872/#3954 before the anchor, followed by E down/up#4033/#4066 and Shift down#4114 afterward. These names denote raw VKs only, not inferred abilities or bindings. `report.json` preserves every control transition, original fields/device/seq/t_ns, repeated-down handling and held-state provenance.','',
    'The accepted n142 native interpretation is withdrawn wrist14.313 -> new forward pose/white emission14.321 -> expanded impact14.329. n199 uses last-not-started19.979 -> first-started20.013 -> impact confirmation20.079. Those file PTS facts are reused from frozen evidence, not re-decoded/re-annotated. The JSON joins each history/bracket/confirmation time to its actual CSV composition_ns, callback event_seq and original-specific+21ms file mapping.','',
    'If the observed right presses initiated these two casts, the model anchors are already after their request receipt. Thus the accepted task can forecast upcoming visible execution of an action already requested; these two positives do not establish a pre-request firing decision. Temporal correspondence and the existing native evidence make that association plausible, but button presence alone does not prove it, particularly with n142 overlapping left hold.','',
    'Receipt-to-first-visible-emission is102.015777ms and115.678016ms. These are comparable in scale to the lead-reported pad calibrationD100-150ms, not a validation of D or KBM-to-pad equivalence. Recorder SCHEMA states input timestamps are WM_INPUT receipt by the logger thread; frame CTS is OBS composition, not game render or player-view time. Physical device/input delivery and capture/display latency remain unmeasured. The2.016ms n142 ordering is numerical shared-clock ordering, not a sub-frame behavioral claim.','',
    'Reproduce from repository root: `uv run --no-sync python -B data/diagnostics/human-cast-request-timing-20260922/diagnose.py`. Stdlib only; reads only the named finalized032454 logs/schema and frozen numerical/evidence JSON. Writes this report and report.json here. Source hashes, exact nanoseconds, schema semantics and all control transitions are in report.json. No image/video decoding, labels, targets, model/horizon, old artifacts, policy/lane edits, training, input or admission changes.']
(BASE/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
assert sha(ADMITTED)=='b12f7013b24482b505e44468eb723245a03d1e5a56bb46ab9d282cdf3e1001d5'
for w in windows:
    print(w['grid_index'],'anchor_after_down_ms',w['anchor_after_right_receipt_ms'],
          'visual_after_down_ms',w['visual_onset_after_receipt_ms'],'transitions',len(w['all_control_transitions']))
print('report.json',sha(BASE/'report.json'))
print('report.md',sha(BASE/'report.md'))
