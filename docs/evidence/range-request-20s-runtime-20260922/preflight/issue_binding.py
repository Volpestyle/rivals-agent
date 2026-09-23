"""Materialize root's one-run review after effective-setup evidence exists."""
import hashlib
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
LIVE = Path('C:/Users/volpe/repos/rivals-agent-live')
sys.path.insert(0, str(LIVE))
from policy.range_skill_policy import SourceIdentity, SkillRuntimeIdentity, SkillDeploymentBinding, digest
from agent.learned_range_skill import LearnedRangeSkillBrain

def read(name):
    return json.loads((OUT / name).read_text(encoding='utf-8-sig'))

def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

def save(name, data):
    with (OUT / name).open('x', encoding='utf-8', newline='\n') as f:
        json.dump(data, f, indent=2); f.write('\n')
    return pin(OUT / name)['sha256']

setup = read('effective-setup.json')
assert setup['root_ready_for_one_diagnostic'] is True
assert all(setup['observed'][k] is True for k in ('normal_cooldown_menu', 'spiderman', 'pad_web_layout', 'luna_setup', 'range'))
for artifact in setup['evidence']:
    assert pin(Path(artifact['path']))['sha256'] == artifact['sha256']
for kind in ('controller', 'perception'):
    for path, values in read(f'{kind}-deployed.json')['files'].items():
        assert pin(LIVE / path)['sha256'] == values['sha256'], path
candidate = json.loads((ROOT / 'data/runtime/range-request-diagnostic-20260922/candidate.json').read_text())
source = SourceIdentity(**candidate['original_source_identity'])
source.validate()
checkpoint = ROOT / candidate['checkpoint']['path']
model_sha = pin(checkpoint)['sha256']
assert model_sha == candidate['checkpoint']['sha256']
settings = {'input_domain': 'virtual_pad', 'saved_values': pin(OUT / 'saved-settings.json'),
            'effective_setup': pin(OUT / 'effective-setup.json'),
            'limits': read('saved-settings.json')['limits'],
            'no_source_motor_conversion': True}
settings_sha = save('runtime-settings.json', settings)
decision = {
    'decision': 'lead_accepts_one_exploratory_runtime_diagnostic', 'at_utc': datetime.now(timezone.utc).isoformat(),
    'authority': 'Root lead under James authorized practice-range goal; independent semantic and caller reviews retained',
    'lead_semantic_review': pin(OUT / 'semantic-review.md'),
    'independent_caller_review': pin(OUT / 'caller-review.md'),
    'launcher': pin(OUT / 'run_instrumented.py'),
    'experiment_question': 'Test whether the unchanged request model completes a Luna kill in one fresh20-second phase; preserve every cast, failure and outcome without tuning or retry',
    'source': asdict(source), 'checkpoint': pin(checkpoint),
    'controller': pin(OUT / 'controller-deployed.json'), 'perception': pin(OUT / 'perception-deployed.json'),
    'runtime_settings': pin(OUT / 'runtime-settings.json'),
    'calibration': pin(ROOT / 'data/runtime/range-request-diagnostic-20260922/calibration-manifest.json'),
    'scope': {'run_name': 'range-request-20s-20260922-1', 'run_count': 1,
              'learned_phase_max_s': 20, 'startup_max_s': 14, 'absolute_authorization_budget_s': 34,
              'confidence': .7, 'scoreboard': False, 'cooldown_regime': 'normal',
              'scenario': 'Luna setup; generic continuous selector, not named-target lock'},
    'interpretation': 'request-start-owned-pulse-v1: immediate guarded start before original acquisition+100ms and original ammo+100ms; nominal end fixed at Controller acceptance+33ms, capped by phase/session; no exact human97.984ms delay, physical hold or visible completion guarantee',
    'limits': ['One source event/four negative labels; TRAIN-only fit, independent quality unknown',
               'MK/PAD and reset-window/continuous differences are exploratory uncertainties',
               'Fifth named measurement:20-second phase after fourth independently audited eight-hit/no-KO result; unchanged reviewed code/model/threshold and fresh full-health setup; not independent quality or a retry of any consumed binding',
               'One named run, no rerun/tuning to select success; request deadline expiry permits only completion of already-owned pulse; faults and send failures cancel with returned/recorded neutral before recovery; no replay or scripted offensive fallback',
               'Proof freshness/watchdog limits remain; no physical-write/process-exit precision claim',
               'Not independent validation, designated Galacta completion, pro parity or ten-trial acceptance'],
}
semantic_sha = save('runtime-semantic-review.json', decision)
runtime = SkillRuntimeIdentity(patch=source.patch, cooldown_regime='normal', runtime_settings_sha256=settings_sha,
    calibration_sha256=decision['calibration']['sha256'], controller_code_sha256=decision['controller']['sha256'],
    perception_sha256=decision['perception']['sha256'], semantic_review_sha256=semantic_sha,
    selector_sha256=source.selector_sha256, semantic_revision=source.semantic_revision, feature_revision=source.feature_revision)
runtime.validate()
review_sha = save('deployment-review.json', {'decision': 'accept_only_the_named_one_run_scope',
    'checkpoint_sha256': model_sha, 'source_identity_sha256': digest(asdict(source)),
    'runtime': asdict(runtime), 'semantic_review': pin(OUT / 'runtime-semantic-review.json'), 'scope': decision['scope']})
binding = SkillDeploymentBinding(model_sha, digest(asdict(source)), runtime, review_sha)
binding.validate(checkpoint_sha256=model_sha, source_identity=source, expected_runtime=runtime)
save('source-identity.json', asdict(source))
save('runtime-identity.json', asdict(runtime))
save('deployment-binding.json', asdict(binding))
consumer = LearnedRangeSkillBrain.from_checkpoint(checkpoint, expected_sha256=model_sha, expected_identity=source,
    expected_runtime=runtime, deployment_binding=binding, device='cpu', offline=False)
assert consumer.policy.spec.confidence == .7
save('loader-preflight.json', {'loaded': True, 'origin': consumer.policy.origin, 'spec': asdict(consumer.policy.spec),
                              'checkpoint_sha256': model_sha, 'inference_calls': 0, 'input': False})
print(json.dumps({'binding_sha256': pin(OUT / 'deployment-binding.json')['sha256'], 'loader': 'accepted; zero inference/input'}))
