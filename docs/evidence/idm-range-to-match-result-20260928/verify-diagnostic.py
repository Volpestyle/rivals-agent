"""Recompute the frozen camera report from collected predictions; no inference."""
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from policy import idm_targets as T
from policy.idm import match_targets as M, match_diagnostic as D

b = ROOT/'data/idm/range-to-match-20260928'
collected = b/'diagnostic-collected'
for rel, pin in json.loads((collected/'diagnostic-hashes.json').read_bytes()).items():
    assert T.sha256(collected/rel) == pin
r = json.loads((collected/'diagnostic-result/report.json').read_bytes())
raw = json.loads((collected/'diagnostic-result/camera-predictions.json').read_bytes())
pred = {name: {sid: {int(i): p for i, p in values.items()} for sid, values in sessions.items()}
        for name, sessions in raw.items()}
prep = json.loads((b/'preparation.json').read_bytes())
deny = T.load_denylist()
admission = M.load_references([row['admission'] for row in prep],
                             registry=ROOT/'data/human/session-splits.corpus.json', denylist=deny)
targets = []
for row in prep:
    path = ROOT/row['targets']
    assert T.sha256(path) == row['targets_sha256']
    target = T.load(path, denylist=deny, match_admission=admission)
    selected, selection = D.choose(target)
    assert selection == r['selection'][target.session_id]
    targets.append(T.Targets(target.header, selected))
    for name, sessions in pred.items():
        assert set(sessions[target.session_id]) == {x['i'] for x in selected}
        for p in sessions[target.session_id].values():
            assert set(p) == {'yaw_deg', 'pitch_deg'}
            assert all(v is None or math.isfinite(v) for v in p.values())
            if name == 'zero':
                assert p == {'yaw_deg': 0.0, 'pitch_deg': 0.0}
common = D.common_answers(pred)
assert {n: D.summaries(targets, p) for n, p in pred.items()} == r['own_coverage']
assert {n: D.summaries(targets, p) for n, p in common.items()} == r['shared_answered_rows']
# Separate arithmetic check of per-source common-row overall/still/moving MAE.
for target in targets:
    sid = target.session_id
    for axis in ('yaw_deg', 'pitch_deg'):
        for name in pred:
            pairs = [(x[axis], common[name][sid][x['i']][axis]) for x in target.rows
                     if common[name][sid][x['i']][axis] is not None]
            for key, selected in [('abs_error_deg', pairs),
                                  ('abs_error_moving_deg', [(a, z) for a, z in pairs if abs(a) >= .5]),
                                  ('abs_error_still_deg', [(a, z) for a, z in pairs if abs(a) < .5])]:
                stat = r['shared_answered_rows'][name]['sessions'][sid][axis][key]
                assert len(selected) == stat['n']
                assert round(sum(abs(a-z) for a,z in selected)/len(selected), 4) == stat['mean']
out = {'report_sha256': T.sha256(collected/'diagnostic-result/report.json'),
       'prediction_sha256': T.sha256(collected/'diagnostic-result/camera-predictions.json'),
       'rows': sum(len(t.rows) for t in targets), 'exact_row_selection_pass': True,
       'report_recompute_pass': True, 'independent_slice_mean_arithmetic_pass': True,
       'finite_or_explicit_unknown_pass': True, 'current_admission_pass': True,
       'no_inference_or_decode': True}
(b/'verification.json').write_text(json.dumps(out, indent=2)+'\n', newline='\n')
print(json.dumps(out, indent=2))
