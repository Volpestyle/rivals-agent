"""Read only named finalized timing files and saved survey JSON; no policy/media IO."""
import csv
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
RAW = Path('C:/Users/volpe/Videos/RivalsInput/20260922T032454-642Z-24328-1')
SURVEY = Path('data/human/skill-event-candidates/032454-support-v2/continuous-survey.json')
ADMITTED = Path('data/human/skill-events/032454-request-diagnostic-v1/examples.json')
PINS = {
    RAW / 'metadata.json': '9514a75db9bde99963a17dd9168144e7c9ee321d48d407ace81ab2922ae4e43f',
    RAW / 'inputs.jsonl': '1fa110de0f1a293e5fe17ccf94f6e0175451952b5a412de6faef1e9c0c51b9ca',
    RAW / 'frames.csv': 'f4252e9273e07f7895c4bea7c35a93b0acf89bdc399c0c1bc10442ae3e6a184c',
    ADMITTED: 'bd6cf4cb298379ac1a63fd226652e517ad6773ed6b4cead92dfb790abca91570',
}


def ref(path):
    return {'path': path.as_posix(), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


for path, expected in PINS.items():
    assert ref(path)['sha256'] == expected, path
meta = json.loads((RAW / 'metadata.json').read_text())
assert meta['complete'] and meta['clean_stop'] and not meta['writer_failed']
assert meta['queue_dropped_events'] == meta['raw_input_errors'] == 0
with (RAW / 'frames.csv').open() as stream:
    frames = list(csv.DictReader(stream))
first = 115370505348149
assert min(int(f['composition_ns']) for f in frames if int(f['composition_ns'])) == first
by_pts = {int(f['pts']): f for f in frames if int(f['track']) == 0}
survey = {r['grid_n']: r for r in json.loads(SURVEY.read_text())}
accepted = {r['grid_index']: r for r in json.loads(ADMITTED.read_text())['rows']}
events = sorted((json.loads(line) for line in (RAW / 'inputs.jsonl').read_text().splitlines()),
                key=lambda r: (r['t_ns'], r['seq']))
active, held, prior_up, focus = False, None, None, None
locators, controls = [], []
start_ns, end_ns = 10979000000, 22229000000
for event in events:
    delta = event['t_ns'] - first
    if delta > end_ns:
        break
    kind = event['type']
    if kind in ('focus', 'pause', 'gap', 'raw_input_status'):
        controls.append(event)
        if kind == 'focus':
            active = event['active']
            held = (2 in event['held_vk']) if active else None
            prior_up = None
            focus = event
        elif kind in ('pause', 'gap'):
            held, prior_up = None, None
    if kind != 'mouse':
        continue
    if 2 in event['buttons_down']:
        if start_ns <= delta <= end_ns:
            # (anchor, anchor+.1]; integer math preserves exact-boundary placement.
            n = (delta - 1) // 100000000
            history = [survey[k] for k in range(n - 4, n + 1) if k in survey]
            eligible = 114 <= n <= 221 and len(history) == 5
            for h in history:
                f = h['frame']; packet = by_pts[f['callback_pts']]
                assert int(packet['composition_ns']) == f['composition_ns']
                assert (f['composition_ns'] - first) / 1e9 == h['state']['t']
                assert h['state']['t'] <= h['grid_tick_t'] and h['available_t'] <= h['grid_tick_t']
                assert abs(h['state']['t'] - h['grid_tick_t']) <= .025
                assert f['file_pts_num'] / f['file_pts_den'] >= 11
                assert ref(Path(f['image']))['sha256'] == f['image_sha256']
            anchor = survey[n]
            locators.append({
                'grid_index': n, 'anchor_t': n / 10, 'horizon_end_t': (n + 1) / 10,
                'received_t': delta / 1e9, 'raw_event': event, 'prior_rmb_held': held,
                'fresh_rise_under_received_continuity': active and held is False,
                'preceding_raw_up': prior_up, 'focus_dependency': focus,
                'clock_history_eligible': eligible, 'history_saved': [h['frame'] for h in history],
                'actual_history_t': [h['state']['t'] for h in history],
                'actual_available_t': [h['available_t'] for h in history],
                'saved_continuous_ammo_history': [h['state']['webs'] for h in history],
                'saved_continuous_target': anchor['target'],
                'saved_continuous_detections': anchor['state']['detections'],
                'saved_continuous_coasting': anchor['state']['coasting'],
                'reset_window_evidence': 'accepted existing row' if n in (141, 198) else 'unknown; no saved reset window in selected candidate rows',
                'existing_request_disposition': accepted[n]['label'] if accepted[n]['label_known'] else 'unknown',
                'audit_semantic_label': None,
                'prior_up_requirement': 'received raw release available' if prior_up else 'focus snapshot establishes up; no preceding received RMB-up exists in this session before rise',
            })
        held = True
    if 2 in event['buttons_up']:
        held, prior_up = False, event
assert len(locators) == 9
assert all(r['fresh_rise_under_received_continuity'] and r['clock_history_eligible'] for r in locators)
assert {r['raw_event']['device'] for r in locators} == {65618}
assert not any(r['type'] in ('pause', 'gap') for r in controls)
notes = {
    122: 'Native saved anchor shows full ammo5, airborne approach through doorway, small green humanoid visible. Saved detector has no detections/target. No target agreement or cast association established.',
    131: 'Native saved anchor shows ammo4 and humanoid at hero-simulation platform through doorway. Saved detector has no detections/target. Not full ammo.',
    154: 'Native saved anchor names Luna Snow; ammo3; player airborne above her. Saved detector has only far upper-right fragment, not visible Luna; selector null.',
    158: 'Native saved anchor shows Luna KO/killfeed and ammo2; causal reader ammo unknown remains unknown. No selected target; do not infer valid cast from another RMB rise.',
    174: 'Native saved anchor shows swing/fall away from downed Luna toward distant Galacta, ammo2. No selected target; recipient/association unknown.',
    186: 'Native saved anchor shows two nearby Galacta, nearer body partly occluded by player; visual ammo2 while saved reader unknown. No detections/selected target; neither future recipient nor reset target established.',
    211: 'Native saved anchor shows falling below ledge, ammo1, distant Galacta/plates above. Saved selector null despite one small detection. Recipient/association unknown.',
}
for row in locators:
    row['new_anchor_inspection'] = notes.get(row['grid_index'], 'No new image inspection; existing accepted/adjudicated request evidence reused.')
report = {
    'status': 'bounded_support_audit_only_no_labels_or_admission',
    'source_refs': [ref(p) for p in PINS] + [ref(SURVEY)],
    'source_video_path_metadata_only': meta['video_path'], 'video_opened': False,
    'clock': {'composition_origin_ns': first, 'file_mux_offset_s': .021,
              'file_scope_s': [11, 22.25], 'composition_segment_s': [10.979, 22.229],
              'grid_origin': 0, 'period_s': .1, 'steps': 5, 'eligible_indices': [114, 221]},
    'input_semantics': meta['input_time_semantics'], 'continuity_controls_before_scope_end': controls,
    'rows': locators, 'additional_clock_eligible_bins': [122, 131, 154, 158, 174, 186, 211],
    'additional_semantically_established_requests': 0,
    'full_ammo_result': 'n122 is the earliest rise, all five saved causal ammo values are5 and history11.799999528..12.199999512 is fully inside gameplay. It does NOT precede complete history. No target selected in saved continuous replay; no prior received raw up, only focus37 up snapshot. Not recoverable as an unchanged accepted-contract positive from present evidence.',
    'limits': ['Fresh received RMB rises are locators, not web request labels.',
               'Saved continuous replay outputs are not substituted for accepted reset-window features.',
               'Seven saved anchors inspected; no new video decode, inference, policy imports, training or reset replay.',
               'Game telemetry packet loss is not recorder loss; no dense cast progression audited here.',
               'No full-ammo Galacta target-agreed request is established. All unknowns retained.'],
    'minimal_followup_if_root_authorizes': 'First resolve causal target eligibility from existing five saved frames only: reset-window replay for n154 (visible Luna) and/or n211 (Galacta region), preserving null/mismatched selections. For Galacta locator n186, saved anchor detector is empty, so no basis to promise recovery. Only after an actual same-target causal selection is established would bounded native cast association inspection be useful: n154 file15.421..15.721 or n211 file21.121..21.471, including raw overlap/releases. These spans are proposed followup, not inspected/authorized here. No need to decode missing history; all five saved images already exist. n122 additionally lacks the existing schema-required preceding raw-up event, which footage cannot supply.',
}
(OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'additional_bins': report['additional_clock_eligible_bins'], 'new_semantic_support': 0, 'earliest': locators[0]['received_t'], 'report': ref(OUT / 'report.json')}, indent=2))
