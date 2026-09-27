"""Offline draft writer. Reads JSON receipts only; never executes a stage or writes approvals.

Run where remote paths are mounted, or supply --mount /inputs=LOCAL --mount /outputs=LOCAL.
The only approval authority is the separately lead-written approvals.json ledger.
"""
import cm3_accounting as accounting
import cm3_budget_plan as budget_plan
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path, PurePosixPath
import re
from datetime import datetime, timezone

STAGES = ('inputs', 'proof128', 'smoke', 'extract', 'fit')
SUBSETS = dict(inputs='train-inputs-assets-pairing', proof128='128-unique-train-frames-both-views',
    smoke='first-complete-96-per-train-session-32-full-schedule-updates',
    extract='all-cached-frames-seven-frozen-sessions', fit='one-registered-fit')
PHASE1 = ('A-0', 'A-1', 'A-2', 'H-0', 'H-repeat-0')
PHASE2 = ('H-1', 'H-2', 'I-0', 'I-1', 'I-2', 'W-0', 'W-1', 'W-2')
JUDGE_SHA = 'e23b3212a0eadc98bc590e5081a92c9fab6740e93808aba2d245d6020b3f8eb0'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                                   allow_nan=False).encode()).hexdigest()


def read(path):
    def pairs(rows):
        result = {}
        for k, v in rows:
            require(k not in result, 'duplicate JSON key')
            result[k] = v
        return result
    def invalid(v):
        raise ValueError('nonfinite JSON: ' + v)
    require(Path(path).stat().st_size <= 32 * 1024 * 1024, 'oversize JSON')
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=pairs, parse_constant=invalid)


def write(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(obj, f, indent=2, sort_keys=True, allow_nan=False)
        f.write('\n')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def complete(obj, name='value'):
    require(obj is not None and obj != '', 'unfilled field: ' + name)
    if isinstance(obj, dict):
        for k, v in obj.items():
            # These are the only intentional nulls in a CUDA context.
            if k == 'sidecar' and v is None:
                continue
            complete(v, name + '.' + k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            complete(v, name + f'[{i}]')


class Writer:
    def __init__(self, context, state, ledger, mounts=()):
        complete(context, 'context')
        require(context['amendment'] == 3 and context['device'] == 'cuda', 'A3 CUDA only')
        require(context['hardware']['class'].startswith('cuda:'), 'CUDA hardware CLASS required')
        self.context, self.state, self.ledger = context, state, ledger['approvals']
        self.identity = digest(context)
        self.mounts = sorted([(a.rstrip('/'), Path(b)) for a, b in mounts], key=lambda p: -len(p[0]))

    def local(self, remote):
        p = PurePosixPath(remote)
        require(p.is_absolute() and '..' not in p.parts, 'absolute normalized remote path required')
        for prefix, root in self.mounts:
            if remote == prefix or remote.startswith(prefix + '/'):
                target = (root / remote[len(prefix):].lstrip('/')).resolve()
                require(target.is_relative_to(root.resolve()), 'mount escape')
                return target
        return Path(remote)

    def pinned(self, ref, *, json_only=True):
        require(set(ref) == {'path', 'sha256'} and re.fullmatch('[0-9a-f]{64}', ref['sha256']), 'bad reference')
        path = self.local(ref['path'])
        require(not json_only or path.suffix == '.json', 'writer reads JSON metadata only')
        require(hashlib.sha256(path.read_bytes()).hexdigest() == ref['sha256'], 'pinned bytes changed')
        return path

    def doc(self, ref):
        return read(self.pinned(ref))

    def approved(self, ref, stage):
        require(any(row.get('stage') == stage and row.get('path') == ref['path']
                    and row.get('sha256') == ref['sha256'] for row in self.ledger),
                'missing lead ledger approval for ' + stage)
        return self.doc(ref)

    def result(self, ref, stage):
        result = self.doc(ref)
        require(result['format'] == 'cm3-stage-result-v1' and result['stage'] == stage
                and result['status'] == 'PASS' and result['context_sha256'] == self.identity,
                'wrong/incomplete result or changed context')
        require(PurePosixPath(ref['path']).name == 'result.json', 'partial completion is not PASS')
        approval = self.approved(result['approval'], stage)
        require(approval['format'] == 'cm3-stage-approval-v1' and approval['stage'] == stage
                and approval['approved_by'] == 'herdr-lead', 'wrong approval stage/schema')
        require(approval['context'] == self.context and approval['context_sha256'] == self.identity,
                'approval context changed')
        require(ref['path'] == approval['output'].rstrip('/') + '/result.json', 'result outside approved output')
        require(result['elapsed_total_seconds'] >= approval['budget']['spent_seconds'] + result['elapsed_stage_seconds'],
                'invalid elapsed ledger')
        return result, approval

    def chain(self, stage):
        refs, results = {}, {}
        for name in STAGES[:STAGES.index(stage)]:
            ref = self.state['stage_results'][name]
            result, approval = self.result(ref, name)
            require(approval['predecessors'] == refs, 'broken predecessor chain')
            if refs:
                require(approval['pairing'] == results['inputs']['artifacts']['pairing'], 'pairing changed')
            refs[name], results[name] = ref, result
        return refs, results

    def budget(self, stage, results):
        budget = dict(self.state['allocation'])
        complete(budget, 'allocation')
        require(budget['approved_by'] == 'herdr-lead', 'allocation is a proposal for the lead')
        require(0 < budget['cap_seconds'] <= 57600 and 0 < budget['stage_seconds']
                <= budget['cap_seconds'] - budget['spent_seconds'], 'invalid remaining compute allocation')
        require(budget['spent_seconds'] >= max((r['elapsed_total_seconds'] for r in results.values()), default=0),
                'spent compute moved backwards')
        require(budget['cloud_instance'] == self.context['hardware']['class'], 'budget class mismatch')
        if 'accounting' in budget:
            accounting.allocation(budget, self.doc, required_results=[self.state['stage_results'][s] for s in results], local_path=self.local)
            require(budget['spent_seconds'] + budget['hold_seconds'] + budget_plan.VERIFICATION_HOLD_SECONDS
                    <= budget['cap_seconds'], 'verification compute reserve exhausted')
            reserve_usd = accounting.usd_up(accounting.Decimal(budget_plan.VERIFICATION_HOLD_SECONDS)
                * accounting.Decimal(str(budget_plan.RATE)) + accounting.Decimal(str(budget_plan.VERIFY_OVERHEAD_USD)))
            require(accounting.Decimal(str(budget['spent_usd'])) + accounting.Decimal(str(budget['hold_usd']))
                    + reserve_usd <= accounting.Decimal(str(budget['cloud_cap_usd'])),
                    'verification dollar reserve exhausted')
        require(0 < budget['hourly_usd'] and 0 < budget['cloud_cap_usd'] <= 50
                and ('accounting' in budget or budget['hourly_usd'] * budget['cap_seconds'] / 3600 <= budget['cloud_cap_usd']), 'cloud ceiling exceeded')
        if stage in ('extract', 'fit'):
            approved = self.approved(self.state['budget_approval'], 'budget')
            require(approved['context_sha256'] == self.identity and approved['predecessors'] ==
                    {s: self.state['stage_results'][s] for s in ('inputs', 'proof128', 'smoke')}, 'budget input mismatch')
            if 'accounting' in budget:
                require(approved.get('status') == 'ELIGIBLE', 'budget STOP or missing eligibility')
                require(approved['reservation_plan'] == budget_plan.derive(self.doc(results['smoke']['artifacts']['details'])), 'approved task holds changed')
            budget['forecast_total_seconds'] = approved['forecast_total_seconds']
            require(0 < budget['forecast_total_seconds'] <= budget['cap_seconds'], 'forecast exceeds cap')
            require(approved['hardware_class'] == budget['cloud_instance']
                    and approved['hourly_usd'] == budget['hourly_usd']
                    and approved['cloud_cap_usd'] == budget['cloud_cap_usd'], 'approved cost/class changed')
            require(0 < approved['projected_modal_usd'] <= budget['cloud_cap_usd'], 'projected Modal cap exceeded')
        return budget

    def stage(self, name, output, task=None, attempt=None):
        refs, results = self.chain(name)
        require(PurePosixPath(output).is_relative_to('/outputs') and '..' not in PurePosixPath(output).parts,
                'output must be new normalized /outputs path')
        require(not PurePosixPath(output).is_relative_to('/outputs/.modal-journal'), 'reserved wrapper journal')
        require(not self.local(output).exists(), 'output already exists')
        value = dict(format='cm3-stage-approval-v1', approved_by='herdr-lead', stage=name,
            context=self.context, context_sha256=self.identity, subset=SUBSETS[name], predecessors=refs,
            budget=self.budget(name, results), output=output,
            allowed_sources=sorted(s for s, row in self.context['sources'].items() if row['role'] == 'train')
                + (sorted(s for s, row in self.context['sources'].items() if row['role'] == 'dev')
                   if name in ('extract', 'fit') else []))
        if name != 'inputs':
            value['pairing'] = results['inputs']['artifacts']['pairing']
            self.doc(value['pairing'])
        if name in ('extract', 'fit'):
            value['budget_approval'] = self.state['budget_approval']
        if name == 'fit':
            require(task in PHASE1 + PHASE2 and attempt and re.fullmatch('[a-zA-Z0-9_.-]+', attempt), 'task/attempt required')
            value.update(arm=task[0], seed=int(task[-1]), purpose='repeat' if task == 'H-repeat-0' else 'registered',
                attempt_id=attempt, freeze=results['extract']['artifacts'], fit_predecessors={})
            if task in PHASE2:
                gate = self.approved(self.state['phase1_gate'], 'phase1_gate')
                require(gate['context_sha256'] == self.identity and gate['status'] == 'PASS', 'wrong phase gate')
                value['fit_predecessors']['phase1_gate'] = self.state['phase1_gate']
        return value

    def forecast(self):
        refs, results = self.chain('extract')
        smoke = self.doc(results['smoke']['artifacts']['details'])
        measured, costs = {}, self.state['projection']
        complete(costs, 'projection')
        require(costs['safety_factor'] >= 1 and costs['total_cache_frames'] > 0
                and all(math.isfinite(v) and v >= 0 for v in costs.values()), 'invalid projection inputs')
        for arm, count in (('A', 3), ('H', 4), ('I', 3), ('W', 3)):
            row = smoke[arm]
            require(row['smoke']['updates'] == 32 and row['timing']['dev_scores'] is False, 'wrong smoke/workload')
            timing = row['timing']
            measured[arm] = count * (row['smoke']['full_schedule_updates'] * row['smoke']['seconds_per_update']
                + 13 * timing['per_epoch_dev_loss_seconds'] + sum(timing[k] for k in
                    ('teacher_seconds', 'self_seconds', 'teacher_metric_seconds', 'self_metric_seconds'))
                + costs['per_fit_diagnostics_serialization_seconds'])
        extraction = 2 * costs['total_cache_frames'] / smoke['extraction_and_rehash']['views_per_second']
        forecast = costs['safety_factor'] * (sum(measured.values()) + extraction
            + costs['source_and_full_cache_hashing_seconds'] + costs['verification_seconds']
            + costs['startup_shutdown_seconds']) + self.state['allocation']['spent_seconds']
        allocation = self.state['allocation']
        if 'accounting' in allocation:
            self.budget('smoke', results)
            spent_usd = allocation['spent_usd']
        else:
            spent_usd = allocation['spent_seconds'] * allocation['hourly_usd'] / 3600
        hourly = self.state['allocation']['hourly_usd']
        require(hourly is not None and hourly > 0, 'benchmark rate unfilled')
        reservation_fields = {}
        if 'accounting' in allocation:
            require(costs['safety_factor'] >= 1.25 and costs['startup_shutdown_seconds'] >= 4050,
                    'registered forecast allowance omitted')
            plan = budget_plan.derive(smoke)
            require(hourly / 3600 == budget_plan.RATE, 'selected all-in rate changed')
            require(costs['per_fit_diagnostics_serialization_seconds'] >= budget_plan.DIAGNOSTICS_SECONDS
                    and costs['source_and_full_cache_hashing_seconds'] >= 14 * budget_plan.SOURCE_HASH_SECONDS,
                    'hash/diagnostic projection allowance omitted')
            require(accounting.Decimal(str(costs['non_compute_usd'])) >= accounting.Decimal(str(budget_plan.FUTURE_NONCOMPUTE_USD)), 'future overhead allowance omitted')
            require(costs['verification_seconds'] >= budget_plan.VERIFICATION_HOLD_SECONDS,
                    'verification allowance omitted')
            extract_hold = budget_plan.EXTRACTION_HOLD_SECONDS
            require(extract_hold >= costs['safety_factor'] * (extraction + budget_plan.SOURCE_HASH_SECONDS)
                    + budget_plan.STARTUP_SECONDS + budget_plan.CLEANUP_SECONDS,
                    'extraction hold below measured work and allowances')
            # Full eligibility uses the registered measured-work forecast. Current
            # launch holds are checked separately; no future phase is reserved now.
            future_holds = plan['matrix_hold_seconds'] + extract_hold + costs['verification_seconds']
            future_prediction = forecast - allocation['spent_seconds']
            total_usd = float(accounting.usd_up(accounting.Decimal(str(spent_usd))
                + accounting.Decimal(str(future_prediction)) * accounting.Decimal(str(budget_plan.RATE))
                + accounting.Decimal(str(costs['non_compute_usd']))))
            reasons = []
            if forecast > allocation['cap_seconds']: reasons.append('aggregate compute exceeds cap')
            if total_usd > allocation['cloud_cap_usd']: reasons.append('gross dollar estimate exceeds cap')
            reservation_fields = dict(status='STOP' if reasons else 'ELIGIBLE', stop_reasons=reasons,
                reservation_plan=plan, accounting=allocation['accounting'],
                settled_spent_seconds=allocation['spent_seconds'], settled_spent_usd=spent_usd,
                all_remaining_max_hold_seconds_informational=future_holds, extraction_hold_seconds=extract_hold,
                verification_hold_seconds=costs['verification_seconds'],
                eligibility_basis='settled-plus-full-measured-forecast',
                hold_admission_basis='settled-plus-current-launch-plus-verification-reserve')
        return dict(format='cm3-budget-approval-v1', approved_by='herdr-lead', context_sha256=self.identity,
            predecessors=refs, hardware_class=self.context['hardware']['class'], hourly_usd=hourly,
            cloud_cap_usd=self.state['allocation']['cloud_cap_usd'], forecast_total_seconds=forecast,
            projected_modal_usd=(total_usd if 'accounting' in allocation else
                spent_usd + (forecast - allocation['spent_seconds']) * hourly / 3600 + costs['non_compute_usd']),
            measured_fit_seconds=measured, extraction_and_rehash_seconds=extraction,
            projection_inputs=costs, smoke_details=results['smoke']['artifacts']['details'], **reservation_fields)

    def gate(self):
        judge_ref = self.context['judge']
        require(judge_ref['sha256'] == JUDGE_SHA, 'wrong A3 judge')
        spec = importlib.util.spec_from_file_location('_draft_judge', self.pinned(judge_ref, json_only=False))
        judge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(judge)
        refs, identities, passing, end = {}, {}, 0, 0
        for task in PHASE1:
            ref = self.state['fit_results'][task]
            result, approval = self.result(ref, 'fit')
            require((approval['arm'], approval['seed'], approval['purpose']) ==
                    (task[0], int(task[-1]), 'repeat' if task == 'H-repeat-0' else 'registered'), 'wrong phase1 fit')
            details = self.doc(result['artifacts']['details'])
            record = self.doc(self.state['fit_records'][task])
            require(record['status'] == 'COMPLETE' and record['exit'] == 0 and record['result'] == ref,
                    'wrapper attempt incomplete or substituted')
            end = max(end, record['finished_at'])
            key = 'H0_repeat' if task == 'H-repeat-0' else task.replace('-', '')
            refs[key] = ref
            identities[key] = dict(checkpoint_sha256=details['checkpoint_sha256'], content_sha256=details['stable_sha256'])
            if task.startswith('A'):
                report = details['evaluation']
                checks = dict(report['self_fed_checks'], camera_mae=report['self_fed']['all']['camera_mae_mean'],
                              zero_motion_camera_mae=report['zero_motion_camera_mae'])
                require(checks['any_hold_observable_steps'] == judge.OBSERVABLE and checks['any_hold_excluded_steps'] == 0
                        and checks['human_any_hold_share'] == judge.HUMAN and checks['zero_motion_camera_mae'] == judge.ZERO,
                        'A baseline/denominator changed')
                passing += judge.seed_checks(checks)['pass']
        require(passing < 2, 'CONTROL_REGIME_STOP')
        require(identities['H0'] == identities['H0_repeat'], 'H0 repeat differs')
        now = datetime.now(timezone.utc)
        require(end <= now.timestamp(), 'future completion time')
        launch = self.doc(self.state['judge_launch'])
        return dict(format='cm3-phase1-gate-v1', approved_by='herdr-lead', status='PASS', context_sha256=self.identity,
            completed=now.isoformat(), launch_pins_sha256=digest(launch['pins']), outputs=refs,
            A_control_gate={'status': 'PASS', 'controls': {str(s): identities[f'A{s}'] for s in range(3)}},
            H0_repeat={'status': 'PASS', 'repeat_identical': True, 'H0': identities['H0'], 'repeat': identities['H0_repeat']})

    def fanout(self, phase, template):
        """Populate routing only from lead-approved per-fit drafts. Review flags stay untouched."""
        tasks = PHASE1 if phase == 'phase1' else PHASE2
        plan = dict(template, phase=phase, context_sha256=self.identity,
                    gpu=self.context['hardware']['class'].removeprefix('cuda:'),
                    device_class='modal:' + self.context['hardware']['class'].removeprefix('cuda:'), tasks={})
        ids, outputs = set(), set()
        for task in tasks:
            ref = self.state['fit_approvals'][task]
            approval = self.approved(ref, 'fit')
            require(approval['context'] == self.context, 'mixed routing context')
            require((approval['arm'], approval['seed'], approval['purpose']) ==
                    (task[0], int(task[-1]), 'repeat' if task == 'H-repeat-0' else 'registered'), 'wrong routing task')
            relative = PurePosixPath(ref['path']).relative_to('/inputs')
            require('..' not in relative.parts, 'receipt traversal')
            output = PurePosixPath(approval['output'])
            require(output.is_relative_to('/outputs') and not output.is_relative_to('/outputs/.modal-journal')
                    and '..' not in output.parts, 'invalid fit output namespace')
            expected = {} if phase == 'phase1' else {'phase1_gate': self.state['phase1_gate']}
            require(approval['fit_predecessors'] == expected, 'wrong phase dependencies')
            require(approval['attempt_id'] not in ids and str(output) not in outputs, 'duplicate attempt/output')
            ids.add(approval['attempt_id']); outputs.add(str(output))
            plan['tasks'][task] = {'attempt_receipts': [dict(path=str(relative), sha256=ref['sha256'],
                attempt_id=approval['attempt_id'], output=str(output))]}
        if phase == 'phase2':
            ref = self.state['phase1_gate']
            self.approved(ref, 'phase1_gate')
            plan['phase1_gate'] = dict(local_path=str(self.local(ref['path'])), sha256=ref['sha256'], remote_ref=ref)
        else:
            plan['phase1_gate'] = None
        return plan


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=(*STAGES, 'budget', 'phase1_gate', 'phase1-plan', 'phase2-plan'))
    p.add_argument('--context', required=True)
    p.add_argument('--state', required=True)
    p.add_argument('--approvals', required=True)
    p.add_argument('--mount', action='append', default=[], metavar='/REMOTE=LOCAL')
    p.add_argument('--output', help='new remote /outputs directory for runner stage')
    p.add_argument('--task', choices=PHASE1 + PHASE2)
    p.add_argument('--attempt-id')
    p.add_argument('--plan-template')
    p.add_argument('--out', required=True, help='new local draft JSON; never approvals.json')
    a = p.parse_args()
    require(Path(a.out).resolve() != Path(a.approvals).resolve() and Path(a.out).name != 'approvals.json', 'lead-only ledger')
    writer = Writer(read(a.context), read(a.state), read(a.approvals), [v.split('=', 1) for v in a.mount])
    if a.stage == 'budget':
        value = writer.forecast()
    elif a.stage == 'phase1_gate':
        value = writer.gate()
    elif a.stage.endswith('-plan'):
        require(a.plan_template, '--plan-template required')
        value = writer.fanout(a.stage.split('-')[0], read(a.plan_template))
    else:
        require(a.output, '--output required')
        value = writer.stage(a.stage, a.output, a.task, a.attempt_id)
    print(json.dumps({'status': 'DRAFT_ONLY', 'path': str(Path(a.out).resolve()), 'sha256': write(a.out, value)}))


if __name__ == '__main__':
    main()
