"""Materialize root's pilot-scoped deployment binding for checkpoint 698d8831 once the effective setup exists.

    uv run --offline --no-project --python 3.11 --with torch==2.14.0 python -B issue_binding.py [--live DIR] [--out DIR]

Needs, in --out: effective-setup.json (the operator's, README checklist), saved-settings.json (collect_settings.py) and the
freeze outputs (freeze_deployed.py). Re-checks every deployed byte against the freeze, reads the driver review's hash from
the live tree's committed blob, builds the SkillRuntimeIdentity, validates the binding and writes it. A mock effective
setup or a dry-run settings receipt is refused unless --out is outside this directory. Every output is mode 'x'.
The binding covers the pilot's ten learned allocations for ONE game PID and ONE range entry; see README "Re-issue".
"""
import argparse
from dataclasses import asdict
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LIVE = Path('C:/Users/volpe/repos/rivals-agent-live')
HANDOFF = Path('C:/Users/volpe/AppData/Local/Temp/claude/C--Users-volpe/7e6e33ed-20c0-4115-b6e2-59dc2d360929/scratchpad/handoff')
REQUIRED_OBSERVED = ('range', 'spiderman', 'normal_cooldown_menu', 'friendly_fire_off', 'pad_web_layout',
                     'galacta_setup', 'monitor_present', 'capture_preflight')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def pin(path):
    return {'path': str(path), 'sha256': sha(Path(path).read_bytes())}


def refuse(why):
    raise SystemExit(f'REFUSED: {why}')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--live', type=Path, default=LIVE)
    ap.add_argument('--out', type=Path, default=HERE)
    a = ap.parse_args(argv)
    live, out = a.live.resolve(), a.out.resolve()
    scratch = out != HERE
    sys.path.insert(0, str(live))
    from policy.range_skill_policy import SourceIdentity, SkillRuntimeIdentity, SkillDeploymentBinding, digest

    def read(name):
        return json.loads((out / name).read_text(encoding='utf-8-sig'))

    def save(name, data):
        with (out / name).open('x', encoding='utf-8', newline='\n') as f:
            json.dump(data, f, indent=2)
            f.write('\n')
        return sha((out / name).read_bytes())

    cand = json.loads((HERE / 'candidate.json').read_text(encoding='utf-8'))
    check = read('deployment-check.json')
    head = subprocess.check_output(['git', '-C', str(live), 'rev-parse', 'HEAD'], text=True).strip()
    if head != check['commit'] or subprocess.check_output(['git', '-C', str(live), 'status', '--porcelain']).strip():
        refuse(f'live tree moved or is dirty since the freeze ({check["commit"]} -> {head})')
    for kind in ('controller', 'perception'):
        for path, values in read(f'{kind}-deployed.json')['files'].items():
            if sha((live / path).read_bytes()) != values['sha256']:
                refuse(f'deployed bytes changed since the freeze: {path}')

    setup, saved = read('effective-setup.json'), read('saved-settings.json')
    if (setup.get('mock') or saved.get('dry_run')) and not scratch:
        refuse('mock effective setup or dry-run settings cannot issue a binding in the preflight directory')
    if setup.get('root_ready_for_pilot') is not True or not all(setup['observed'].get(k) is True for k in REQUIRED_OBSERVED):
        refuse(f'effective setup not ready: {setup.get("observed")}')
    for artifact in setup['evidence']:
        if pin(artifact['path'])['sha256'] != artifact['sha256']:
            refuse(f'effective-setup evidence changed: {artifact["path"]}')
    if not saved['patch_equals_source_identity'] or not saved['swing_hold_saved'] or \
            not all(saved['comparison_to_slot04_receipt'][k] for k in ('installed_client', 'steam_build_id', 'display_saved',
                                                                       'controller_saved_profiles', 'enemy_color_saved_raw')):
        refuse('saved settings differ from the source patch or the slot-4 receipt')
    if not saved.get('dry_run') and saved['game_process']['pid'] != setup['game_pid']:
        refuse('saved-settings and effective-setup name different game processes')

    source = SourceIdentity(**cand['source_identity'])
    source.validate()
    if digest(asdict(source)) != cand['source_identity_sha256']:
        refuse('source identity digest differs from the fit report')
    checkpoint = ROOT / cand['checkpoint']['path']
    if pin(checkpoint)['sha256'] != cand['checkpoint']['sha256']:
        refuse('checkpoint bytes differ from the handed-over hash')
    for report in cand['fit_reports']:
        if pin(ROOT / report['path'])['sha256'] != report['sha256']:
            refuse(f'fit report changed: {report["path"]}')
    ref = cand['review_reference']
    blob = subprocess.check_output(['git', '-C', str(live), 'cat-file', 'blob', f'{head}:{ref["path"]}'])
    review_sha = sha(blob)
    if review_sha != ref['git_blob_sha256']:
        refuse(f'{ref["path"]} at {head} is not the reviewed blob ({review_sha})')

    settings_sha = save('runtime-settings.json', {
        'input_domain': 'virtual_pad', 'saved_values': pin(out / 'saved-settings.json'),
        'effective_setup': pin(out / 'effective-setup.json'), 'limits': saved['limits'],
        'no_source_motor_conversion': True})
    schedule_path = ROOT / cand['schedule']['path']
    schedule = json.loads(schedule_path.read_text(encoding='utf-8'))
    learned = [t for t in schedule['trials'] if t['policy_role'] == 'learned']
    def review_pin(name):
        path = ROOT / name if name.startswith('data/') else HANDOFF / name
        return pin(path) if path.exists() else {'path': str(path), 'absent': True}

    reviews = {change: [review_pin(f) for f in files]
               for change, files in cand['changed_boundary_reviews'].items() if change != 'note'}
    decision = {
        'decision': 'lead_accepts_galacta_pilot_20260923_learned_allocations' if not scratch else 'DRY_RUN_not_a_decision',
        'at_utc': datetime.now(timezone.utc).isoformat(),
        'authority': 'Root lead under James authorized practice-range goal; independent reviews retained',
        'experiment_question': 'Execute the ten learned allocations of the predeclared galacta-pilot-20260923 schedule, each once; preserve every result against the frozen 20-slot matched schedule',
        'source': asdict(source), 'checkpoint': pin(checkpoint), 'fit_reports': [pin(ROOT / r['path']) for r in cand['fit_reports']],
        'driver_review': {'path': ref['path'], 'git_commit': head, 'git_blob_sha256': review_sha},
        'changed_boundary_reviews': reviews,
        'controller': pin(out / 'controller-deployed.json'), 'perception': pin(out / 'perception-deployed.json'),
        'calibration': pin(out / 'calibration-current.json'), 'deployment_check': pin(out / 'deployment-check.json'),
        'runtime_settings': pin(out / 'runtime-settings.json'),
        'scope': {'schedule': {'path': cand['schedule']['path'], 'sha256': sha(schedule_path.read_bytes())},
                  'allocations': [{'schedule_index': t['schedule_index'], 'run_name': t['planned_run_name'],
                                   'scenario': t['spec']['scenario']} for t in learned],
                  'each_allocation_once': True, 'game_pid': setup['game_pid'], 'range_entry': setup.get('range_entry'),
                  'learned_phase_max_s': 20, 'startup_max_s': 14, 'absolute_authorization_budget_s': 34,
                  'confidence': cand['checkpoint']['confidence'], 'scoreboard': True, 'collect_episode': True,
                  'stop_on_feed': True, 'cooldown_regime': 'normal', 'decision_hz': 10, 'reflex_hz': 60,
                  'scenario': 'designated right Galacta by the courtyard stair railing; generic continuous selector; target identity, full health and bin require the actual episode audit',
                  'reissue_on': ['game PID change', 'range re-entry', 'any deployed byte change', 'live tree move']},
        'interpretation': 'request-start-owned-pulse-v1 unchanged from slot 4; tracker body witness (0f71336) active in range mode',
        'limits': ['TRAIN-only fit on 76 known rows (37 starts / 39 controls); independent quality unknown',
                   'MK source vs PAD runtime and reset-window vs continuous selection remain exploratory uncertainties',
                   'Fused two-bot boxes are not refused by shape (VUH-1356); the courtyard pair can produce one',
                   'Stacked _bodies groups stay refused (VUH-1314 residual)',
                   'No rerun/tuning to select success; no replay or scripted offensive fallback',
                   'Proof freshness/watchdog limits remain; no physical-write/process-exit precision claim'],
    }
    semantic_sha = save('runtime-semantic-review.json', decision)
    ident = read('deployment-check.json')['identity']
    runtime = SkillRuntimeIdentity(patch=source.patch, cooldown_regime='normal', runtime_settings_sha256=settings_sha,
        calibration_sha256=decision['calibration']['sha256'], controller_code_sha256=decision['controller']['sha256'],
        perception_sha256=ident['perception'], semantic_review_sha256=semantic_sha,
        selector_sha256=ident['selector'], semantic_revision=source.semantic_revision, feature_revision=source.feature_revision)
    runtime.validate()
    binding = SkillDeploymentBinding(cand['checkpoint']['sha256'], digest(asdict(source)), runtime, review_sha)
    binding.validate(checkpoint_sha256=cand['checkpoint']['sha256'], source_identity=source, expected_runtime=runtime)
    save('source-identity.json', asdict(source))
    save('runtime-identity.json', asdict(runtime))
    save('deployment-binding.json', asdict(binding))
    print(json.dumps({'binding_sha256': pin(out / 'deployment-binding.json')['sha256'], 'runtime': asdict(runtime),
                      'review_sha256': review_sha, 'next': 'check_binding.py'}))


if __name__ == '__main__':
    main()
