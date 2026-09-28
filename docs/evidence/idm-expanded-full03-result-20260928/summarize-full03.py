"""Read-only full03 collection checks and matched-baseline comparison; no inference."""
from pathlib import Path
import collections
import hashlib
import json
import math
import numpy as np
import torch

torch.set_num_threads(2)
BASE = Path('data/idm/cloud-20260927')
ROOT = BASE / 'full03-result-collected'
ART = ROOT / 'artifacts'
def read(path):
    return json.loads(path.read_bytes())
def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

for rel, pin in read(ROOT/'hashes.json').items():
    p = ROOT/rel
    assert p.stat().st_size == pin['bytes'] and digest(p) == pin['sha256'], rel
collection = read(ROOT/'collection.json')
assert collection['volume_id'] == 'vo-dpykVEKfIL22lf5pWsMeQA'
assert all(x['status'] in ('receipt', 'hash_verified') for x in collection['artifacts'].values())
terminal = read(ROOT/'terminal.json')
assert terminal['terminal'] and terminal['app']['state'] == 'stopped'
assert str(terminal['app']['tasks']) == '0' and terminal['containers'] == []
new = read(ART/'report/report.json')
old_press_path = Path('docs/evidence/idm-press-diagnostic-result-20260927/report.json')
old_camera_path = Path('docs/evidence/idm-expanded-full03-launch-20260928/baseline-camera.json')
assert digest(old_press_path) == 'dd09f3b33b2a27c458fca580bec8da7753b38584d73950aa35a4fe14efed6a98'
assert digest(old_camera_path) == 'bce156fcf7cd941a3ee77d16a7eac93e709e3f04d35c32a40ad90e773bdf6e2a'
old = read(old_press_path)
old_camera = read(old_camera_path)['result']['gate1_diagnostic']
old_rows_path = BASE/'press02-result/collected/stages/real/row-ids.json'
assert digest(old_rows_path) == read(Path('docs/evidence/idm-press-diagnostic-result-20260927/real-stage-complete.json'))['artifacts']['row-ids.json']['sha256']
rows = read(ART/'real/row-ids.json')
assert rows == read(old_rows_path) == read(ART/'zero/row-ids.json')
assert len(rows) == len(set(map(tuple, rows))) == new['heldout_rows'] == old['heldout_rows'] == 49080
assert new['calibration']['method'] == old['calibration']['method']
train_rows = read(ART/'calibration/row-ids.json')
assert len(train_rows) == 653842
assert set(x[0] for x in train_rows).isdisjoint(x[0] for x in rows)
probabilities = {}
for phase, count in [('calibration',653842),('real',49080),('zero',49080)]:
    a = np.load(ART/phase/'probabilities.npy', allow_pickle=False)
    assert a.shape == (count,3) and a.dtype == np.float32
    assert np.isfinite(a).all() and ((a>=0)&(a<=1)).all()
    probabilities[phase] = {'shape':list(a.shape),'dtype':str(a.dtype)}
    if phase == 'zero':
        assert (a == a[0]).all()
        probabilities[phase]['constant_values'] = a[0].tolist()
        assert (a < .5).all()

final = torch.load(ART/'fit/refit.pt', map_location='cpu', weights_only=False)
assert digest(ART/'fit/refit.pt') == new['checkpoint_sha256']
epochs = []
for receipt_path in sorted((ART/'fit/epochs').glob('*.complete.json')):
    receipt = read(receipt_path)
    path = receipt_path.parent/receipt['artifact']['path']
    assert digest(path) == receipt['artifact']['sha256']
    payload = torch.load(path, map_location='cpu', weights_only=False)
    state = payload['resume']
    assert state['next_epoch'] == receipt['completed_epochs']
    assert state['step_count'] == receipt['step_count'] == state['next_epoch']*40866
    assert state['next_batch'] == 0 and state['optimizer']['state']
    assert all(torch.isfinite(v).all() for v in payload['model'].values())
    if state['next_epoch'] == 3:
        assert all(torch.equal(v,final['model'][k]) for k,v in payload['model'].items())
    epochs.append({'epoch':state['next_epoch'],'steps':state['step_count'],
                   'checkpoint_sha256':digest(path),'receipt_sha256':digest(receipt_path)})
assert [x['epoch'] for x in epochs] == [1,2,3]
assert [x['epoch'] for x in new['fit']['history']] == [0,1,2]

camera = {}
for axis in ('yaw_deg','pitch_deg'):
    camera[axis] = {}
    for label, data in [('baseline',old_camera),('expanded',new['camera'])]:
        m = data['model']['pooled']['camera'][axis]
        assert m['evaluable'] == 49080
        camera[axis][label] = {
            'mae':m['abs_error_deg']['mean'], 'answered':m['abs_error_deg']['n'],
            'eligible':m['evaluable'], 'coverage':m['abs_error_deg']['n']/m['evaluable'],
            'moving_mae':m['abs_error_moving_deg']['mean'],
            'still_mae':m['abs_error_still_deg']['mean'],
            'per_session':{sid:v['camera'][axis]['abs_error_deg'] for sid,v in data['model']['sessions'].items()},
        }
    camera[axis]['zero'] = new['camera']['zero']['pooled']['camera'][axis]['abs_error_deg']
    camera[axis]['persistence'] = new['camera']['persistence']['pooled']['camera'][axis]['abs_error_deg']
    camera[axis]['relative_mae_reduction'] = 1-camera[axis]['expanded']['mae']/camera[axis]['baseline']['mae']
press = {}
for method in ('fixed_0.5','train_rate'):
    press[method] = {}
    for action in ('amazing_combo','jump','web_cluster'):
        comparison = {}
        for label, report in [('baseline',old),('expanded',new)]:
            for control in ('real','zero_visuals'):
                v = report['controls'][control][method][action]
                known = sum(x['known_rows'] for x in v['sessions'].values())
                answered = sum(x['answered_rows'] for x in v['sessions'].values())
                assert known == answered == 49080
                assert v['tp']+v['fn'] == sum(x['heldout_positives'] for x in v['sessions'].values())
                if v['precision'] is not None:
                    assert math.isclose(v['precision'],v['tp']/(v['tp']+v['fp']))
                assert math.isclose(v['recall'],v['tp']/(v['tp']+v['fn']))
                comparison[label+'_'+control] = {k:v[k] for k in ('precision','recall','f1','tp','fp','fn','chance_mean','chance_std','decides')}
                comparison[label+'_'+control].update(coverage=answered/known, known_rows=known,
                    predicted_rows=v['tp']+v['fp'],predicted_row_rate=(v['tp']+v['fp'])/known)
        press[method][action] = comparison
summary = {
    'scope':'EXPLORATORY; no Gate 2 or corpus-labeling permission',
    'final_checkpoint_sha256':new['checkpoint_sha256'], 'epochs':epochs,
    'collection_counts':dict(collections.Counter(v['status'] for v in collection['artifacts'].values())),
    'same_ordered_dev_rows':True,'dev_rows':len(rows),'train_rows':len(train_rows),
    'dev_by_session':dict(collections.Counter(x[0] for x in rows)),
    'old_rows_sha256':digest(old_rows_path),'new_rows_sha256':digest(ART/'real/row-ids.json'),
    'probability_checks':probabilities,'camera':camera,'press':press,
    'camera_caveat':'Same eligible rows, model-specific answered subsets; MPS baseline fit/evaluation versus CUDA new fit/evaluation. No matched-intersection prediction dump available.',
    'press_caveat':'Both press evaluations CUDA; baseline model was trained on MPS. TRAIN-only quantile method unchanged but fitted thresholds and TRAIN corpus differ. No causal attribution to extra data alone.',
    'fit_seconds':new['fit']['seconds'], 'fit_history':new['fit']['history'],
    'accounting':{'method':'lead metered-delta read, not an invoice','full03_approx_usd':21.9,
                  'metered_month_usd':101.89,'billed_usd':70.40,'ledger_commit':'210a67b',
                  'prior_lane_allocation_including_storage_usd':19.676993068670252,
                  'approx_lane_plus_full03_usd':41.576993068670254,
                  'lane_allocation_usd':50,'warning':'Mixed historical bounds and new estimate; not an exact cumulative invoice. Storage attribution pending lead reconciliation.'},
    'input_retention':'Lead correction: retain for next refit until its inputs are staged or James decides otherwise. Keep full03 output volume. No deletion or retry.',
}
(ROOT/'comparison.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({'verified':True,'epochs':epochs,'collection_counts':summary['collection_counts'],
                  'camera':camera,'comparison_sha256':digest(ROOT/'comparison.json')},indent=2))
