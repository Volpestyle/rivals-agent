"""EXPLORATORY zero-visual inference/report recovery; never fit or read pixels."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import torch

from policy.idm import press_diagnostic as D, press_stages as S, train as TR
from policy import idm_targets as T

HELDOUT = ('20260923T171533-187Z-33696-5', '20260923T205528-900Z-45572-3')
CHECKPOINT = '1b9bcc6a6f909d0e5cbd1cb5fb64c71c89a6cc5320c8c8989ac51cb952cbf541'


class ZeroInputs:
    """Same batch shapes/dtype as Examples.inputs; no source frame is needed."""
    def __init__(self, count, config):
        self.count, self.config = count, config

    def __len__(self):
        return self.count

    def inputs(self, indices):
        c = self.config
        return (torch.zeros(len(indices), c.differences, c.height, c.width, dtype=torch.float32),
                torch.zeros(len(indices), 6, 80, 200, dtype=torch.float32))


def select_rows(targets, row_ids):
    """Select precisely the original real-pass rows, without rebuilding eligibility."""
    S.require(len({tuple(x) for x in row_ids}) == len(row_ids), 'duplicate saved row identity')
    lookup = {t.session_id: (t, {r['i']: r for r in T.training_rows(t)}) for t in targets}
    S.require(set(lookup) == set(HELDOUT), 'exact frozen dev roster required')
    items = []
    for sid, index in row_ids:
        S.require(sid in lookup and index in lookup[sid][1], 'saved row missing or ineligible')
        target, rows = lookup[sid]
        items.append((target, None, rows[index], None))
    return SimpleNamespace(actions=D.ACTIONS, items=items)


def verify_origin(origin, pins):
    origin = Path(origin)
    for rel, pin in pins['artifacts'].items():
        path = origin / rel
        S.require(not Path(rel).is_absolute() and '..' not in Path(rel).parts
                  and path.resolve().is_relative_to(origin.resolve()), 'origin path escape')
        S.require(path.is_file() and S.digest(path) == pin, 'origin artifact pin mismatch')
    old = json.loads((origin / 'stage-identity.json').read_text())
    S.require(old == pins['identity'] and old['checkpoint_sha256'] == CHECKPOINT, 'origin identity mismatch')
    train_rows = json.loads((origin / 'stages/train-inference/row-ids.json').read_text())
    real_rows = json.loads((origin / 'stages/real/row-ids.json').read_text())
    S.require(len(train_rows) == 289722 and len(real_rows) == 49080, 'origin row count mismatch')
    _, calibration = S.load(origin / 'stages/train-inference', 'train-inference', old, train_rows)
    real, _ = S.load(origin / 'stages/real', 'real', old, real_rows)
    return old, calibration, real_rows, real


def run(origin, pins, inputs, out, identity, *, device, progress=lambda _: None):
    old, calibration, row_ids, real = verify_origin(origin, pins)
    S.identity_check(identity)
    S.require(identity['checkpoint_sha256'] == CHECKPOINT
              and identity['run_config_sha256'] == old['run_config_sha256']
              and identity['input_manifest_sha256'] == old['input_manifest_sha256'], 'recovery identity mismatch')
    inputs, out = Path(inputs), Path(out)
    manifest_path = inputs / 'run-manifest.json'
    S.require(S.digest(manifest_path) == old['run_config_sha256'], 'original run manifest mismatch')
    manifest = json.loads(manifest_path.read_text())
    held = [item for item in manifest['sessions'] if item['role'] == 'heldout']
    S.require(tuple(item['session_id'] for item in held) == HELDOUT, 'heldout manifest roster mismatch')
    S.require(S.digest(inputs / 'refit.pt') == CHECKPOINT, 'checkpoint hash mismatch')
    model, payload = TR.load_checkpoint(inputs / 'refit.pt', device=device)
    targets = []
    for item in held:
        sid = item['session_id']
        path = inputs / 'targets' / (sid + '.idm.jsonl')
        S.require(S.digest(path) == item['targets_sha256']
                  == payload['meta']['targets'][sid]['sha256'], 'target/checkpoint provenance mismatch')
        target = T.load(path)
        S.require(target.session_id == sid and target.header['split'] == 'train', 'target identity/split mismatch')
        targets.append(target)
    examples = select_rows(targets, row_ids)
    progress('Verified completed TRAIN calibration and real stage; zero-only inference')
    zero_dir = out / 'stages/zero_visuals'
    zero, _ = S.scores(zero_dir, 'zero_visuals', identity, row_ids,
                       lambda: D.infer(model, ZeroInputs(len(row_ids), model.config),
                                       device=device, zero=True, batch=32, progress=progress),
                       resume=zero_dir.exists())
    report = {'scope': 'EXPLORATORY', 'checkpoint_sha256': CHECKPOINT,
              'manifest_sha256': old['run_config_sha256'], 'device': device, 'actions': D.ACTIONS,
              'heldout_rows': len(row_ids), 'calibration': calibration, 'controls': {},
              'recovery': {'original_identity': old, 'origin_pins': pins,
                           'operation': 'Completed TRAIN and real reused; zero-only inference plus paired report',
                           'pixels_opened': False, 'fit_performed': False,
                           'zero_inputs': 'float32 zero motion [B,16,252,448] and HUD [B,6,80,200]; batch32 including tail'},
              'preflight': {'passed': True, 'sessions': [{key: item[key] for key in
                  ('session_id', 'role', 'targets_sha256', 'frames_sha256')} for item in manifest['sessions']]},
              'scoring': 'Same saved eligible rows; no probability abstention band. One-to-one +/-2 intervals; '
                         '20 deterministic Bernoulli chance draws at each session predicted rate. '
                         'Fixed-0.5 differs from the historical abstained-row report by design.'}
    supported = [model.support[a] for a in D.ACTIONS]
    for label, values in [('fixed_0.5', [0.5] * 3),
                          ('train_rate', [calibration['thresholds'][a] for a in D.ACTIONS])]:
        for control, probabilities in [('real', real), ('zero_visuals', zero)]:
            progress(f'{control}: {label} scoring')
            report['controls'].setdefault(control, {})[label] = D.score(
                examples, probabilities, values, supported, progress)
    D.persist_scores(out / 'zero_visuals-probabilities.npy', zero)
    D.persist_json(out / 'calibration.json', calibration)
    D.persist_json(out / 'heldout-row-ids.json', row_ids)
    D.persist_json(out / 'report.json', report)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('origin', 'pins', 'pins-sha256', 'inputs', 'out', 'identity', 'identity-sha256'):
        p.add_argument('--' + name, required=True)
    p.add_argument('--device', choices=('cuda', 'cpu'), required=True)
    a = p.parse_args()
    S.require(S.digest(a.pins) == a.pins_sha256 and S.digest(a.identity) == a.identity_sha256, 'recovery pin mismatch')
    torch.set_num_threads(8 if a.device == 'cuda' else 2)
    from scripts.job_status import write
    out = Path(a.out)
    write('idm-press-diagnostic', root=out/'jobs', owner='idm-owner', host='modal', stage='running', evidence=str(out/'report.json'))
    try:
        run(a.origin, json.loads(Path(a.pins).read_text()), a.inputs, out,
            json.loads(Path(a.identity).read_text()), device=a.device,
            progress=lambda value: write('idm-press-diagnostic', root=out/'jobs', progress=value))
        write('idm-press-diagnostic', root=out/'jobs', stage='done')
    except BaseException:
        write('idm-press-diagnostic', root=out/'jobs', stage='failed')
        raise


if __name__ == '__main__':
    main()
