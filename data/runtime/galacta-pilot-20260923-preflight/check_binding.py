"""Load checkpoint 698d8831 through the issued binding exactly as agent/loop.py main does; zero inference, no input.

    uv run --offline --no-project --python 3.11 --with torch==2.14.0 python -B check_binding.py [--live DIR] [--out DIR]

Reads source-identity.json, runtime-identity.json and deployment-binding.json from --out the way `agent.loop` reads
--range-identity/--range-runtime/--range-deployment, then calls LearnedRangeSkillBrain.from_checkpoint(offline=False),
the live load. Then it proves the binding refuses: each control below must raise, and the check fails if any passes.
Writes loader-preflight.json (mode 'x').
"""
import argparse
from dataclasses import asdict, replace
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LIVE = Path('C:/Users/volpe/repos/rivals-agent-live')
OLD_CHECKPOINT = '6ee388070599e3df042ea73876e391340bf228a9e626cc212c60875d8191aeef'
OLD_SELECTOR = 'ddf1428a61c54805ce06164ef0daa7dfa1302fdf1735990336fdcab939ae098d'
LF_PERCEPTION = '75912d7f50effc47d876b3194174d7009e64027e391c83f561e6e37dea00f8c1'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--live', type=Path, default=LIVE)
    ap.add_argument('--out', type=Path, default=HERE)
    a = ap.parse_args(argv)
    live, out = a.live.resolve(), a.out.resolve()
    sys.path.insert(0, str(live))
    from agent.learned_range_skill import LearnedRangeSkillBrain
    from agent.loop import RangeDecisionSlots
    from policy.range_skill_policy import SkillDeploymentBinding, SkillRuntimeIdentity, SourceIdentity, digest
    for module in ('agent.learned_range_skill', 'agent.loop', 'policy.range_skill_policy'):
        assert Path(sys.modules[module].__file__).resolve().is_relative_to(live), module

    cand = json.loads((HERE / 'candidate.json').read_text(encoding='utf-8'))
    checkpoint = ROOT / cand['checkpoint']['path']
    expected_sha = cand['checkpoint']['sha256']
    assert hashlib.sha256(checkpoint.read_bytes()).hexdigest() == expected_sha
    # agent/loop.py main, --range-identity / --range-runtime / --range-deployment:
    identity_data = json.loads((out / 'source-identity.json').read_text(encoding='utf-8'))
    identity = SourceIdentity(**identity_data)
    runtime = SkillRuntimeIdentity(**json.loads((out / 'runtime-identity.json').read_text(encoding='utf-8')))
    binding_data = json.loads((out / 'deployment-binding.json').read_text(encoding='utf-8'))
    binding_data['runtime'] = SkillRuntimeIdentity(**binding_data['runtime'])
    binding = SkillDeploymentBinding(**binding_data)
    assert identity_data == cand['source_identity'] and digest(identity_data) == cand['source_identity_sha256']
    assert (runtime.perception_sha256, runtime.selector_sha256) == (identity.perception_sha256, identity.selector_sha256)
    assert binding.review_sha256 == cand['review_reference']['git_blob_sha256']

    def load(sha=expected_sha, ident=identity, rt=runtime, bd=binding):
        return LearnedRangeSkillBrain.from_checkpoint(checkpoint, expected_sha256=sha, expected_identity=ident,
                                                      expected_runtime=rt, deployment_binding=bd, device='cpu', offline=False)

    brain = load()
    spec = brain.policy.spec
    assert spec.confidence == cand['checkpoint']['confidence'] and brain.policy.origin == 'reviewed_human'
    RangeDecisionSlots.validate_timing(spec.period_s, spec.tolerance_s)
    assert abs(10 * spec.period_s - 1) < 1e-9          # --decision-hz 10

    def runtime_with(**kw):
        rt = replace(runtime, **kw)
        return rt, replace(binding, runtime=rt)          # binding and expected profile both carry the change

    controls = {
        'binding names the first pilot checkpoint': dict(bd=replace(binding, checkpoint_sha256=OLD_CHECKPOINT)),
        'expected checkpoint hash is the first pilot one': dict(sha=OLD_CHECKPOINT),
        'runtime selector is the first pilot selector': dict(zip(('rt', 'bd'), runtime_with(selector_sha256=OLD_SELECTOR))),
        'runtime patch differs from the source': dict(zip(('rt', 'bd'), runtime_with(patch='1.1.3870121/build25364677'))),
        'runtime cooldown regime is off': dict(zip(('rt', 'bd'), runtime_with(cooldown_regime='off'))),
        'runtime settings hash is the source profile': dict(zip(('rt', 'bd'), runtime_with(runtime_settings_sha256=identity.source_profile_sha256))),
        'runtime semantics are the onset revision': dict(zip(('rt', 'bd'), runtime_with(semantic_revision='web-cluster-onset-v1'))),
        'expected runtime differs from the bound one (LF perception)': dict(rt=replace(runtime, perception_sha256=LF_PERCEPTION)),
        'review reference is not a sha256': dict(bd=replace(binding, review_sha256='driver-review.md')),
        'binding source digest is of another identity': dict(bd=replace(binding, source_identity_sha256=OLD_SELECTOR)),
        'expected identity is the first pilot source': dict(ident=replace(identity, perception_sha256='e9d40f7a12442335866df16edaa8ceea7116177ab8546b3267ac096c1c616798', selector_sha256=OLD_SELECTOR)),
        'no binding at all (live load)': dict(bd=None),
    }
    refused = {}
    for name, kw in controls.items():
        try:
            load(**kw)
        except Exception as e:  # noqa: BLE001 - any refusal counts; a pass fails the check below
            refused[name] = f'{type(e).__name__}: {e}'
        else:
            refused[name] = None
    passed = [n for n, why in refused.items() if why is None]
    report = {'loaded': True, 'live_load': True, 'origin': brain.policy.origin, 'spec': asdict(spec),
              'checkpoint_sha256': expected_sha, 'binding_sha256': hashlib.sha256((out / 'deployment-binding.json').read_bytes()).hexdigest(),
              'runtime': asdict(runtime), 'review_sha256': binding.review_sha256, 'code_tree': str(live),
              'inference_calls': 0, 'input': False, 'refusal_controls': refused, 'controls_passed_wrongly': passed}
    with (out / 'loader-preflight.json').open('x', encoding='utf-8', newline='\n') as f:
        json.dump(report, f, indent=2)
        f.write('\n')
    print(json.dumps({'loaded': True, 'confidence': spec.confidence, 'controls': len(refused),
                      'refused': len(refused) - len(passed), 'passed_wrongly': passed}))
    if passed:
        raise SystemExit('REFUSED: a refusal control loaded; the binding does not bind')


if __name__ == '__main__':
    main()
