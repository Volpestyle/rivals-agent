"""Only synthetic temporary JSON. No corpus, model, Modal import or network."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import make_receipt as m


class WriterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.context = dict(amendment=3, device='cuda', hardware={'class': 'cuda:SYNTHETIC'},
            sources={'d': {'role': 'dev', 'sidecar': None}, 'b': {'role': 'train'}, 'a': {'role': 'train'}})
        self.state = dict(stage_results={}, allocation=dict(approved_by='herdr-lead', cap_seconds=100,
            spent_seconds=3, stage_seconds=10, cloud_instance='cuda:SYNTHETIC', hourly_usd=1, cloud_cap_usd=50))
        self.ledger = {'approvals': []}
        self.w = m.Writer(self.context, self.state, self.ledger, [('/inputs', self.root / 'in'), ('/outputs', self.root / 'out')])

    def store(self, remote, value):
        return {'path': remote, 'sha256': m.write(self.w.local(remote), value)}

    def chain(self):
        refs = {}
        for stage in ('inputs', 'proof128', 'smoke'):
            approval = self.w.stage(stage, '/outputs/' + stage)
            ap = self.store('/inputs/' + stage + '.json', approval)
            self.ledger['approvals'].append(dict(stage=stage, **ap, approved_at='synthetic', approver='herdr-lead'))
            pairing = self.store('/outputs/' + stage + '/pairing.json', {'synthetic': True})
            result = dict(format='cm3-stage-result-v1', stage=stage, status='PASS', context_sha256=m.digest(self.context),
                approval=ap, artifacts={'pairing': pairing}, elapsed_stage_seconds=1,
                elapsed_total_seconds=approval['budget']['spent_seconds'] + 1)
            ref = self.store('/outputs/' + stage + '/result.json', result)
            refs[stage] = ref
            self.state['stage_results'][stage] = ref
            self.state['allocation']['spent_seconds'] = result['elapsed_total_seconds']
        return refs

    def test_draft_does_not_modify_ledger_and_orders_roles(self):
        before = deepcopy(self.ledger)
        value = self.w.stage('inputs', '/outputs/fresh')
        self.assertEqual(value['allowed_sources'], ['a', 'b'])
        self.assertEqual(before, self.ledger)
        self.assertFalse(self.w.local(value['output']).exists())

    def test_chain_binds_pairing(self):
        self.chain()
        refs, results = self.w.chain('extract')
        self.assertEqual(set(refs), {'inputs', 'proof128', 'smoke'})
        approval = self.w.doc(results['smoke']['approval'])
        self.assertEqual(approval['pairing'], results['inputs']['artifacts']['pairing'])

    def test_wrong_or_missing_ledger_stage_refuses(self):
        self.chain()
        for bad in ('fit', 'bad'):
            self.ledger['approvals'][0]['stage'] = bad
            with self.assertRaisesRegex(ValueError, 'ledger approval'):
                self.w.chain('extract')

    def test_tamper_incomplete_changed_context_and_completed_refuse(self):
        self.chain()
        ref = self.state['stage_results']['inputs']
        original = self.w.doc(ref)
        for field, value in (('status', 'INCOMPLETE'), ('context_sha256', 'different')):
            changed = dict(original, **{field: value})
            self.w.local(ref['path']).unlink()  # owned synthetic temporary file only
            updated = self.store(ref['path'], changed)
            with self.assertRaisesRegex(ValueError, 'wrong/incomplete'):
                self.w.result(updated, 'inputs')
        completed = self.store('/outputs/inputs/completed.json', original)
        with self.assertRaisesRegex(ValueError, 'partial completion'):
            self.w.result(completed, 'inputs')
        self.w.local(completed['path']).write_text('{}')
        with self.assertRaisesRegex(ValueError, 'bytes changed'):
            self.w.doc(completed)

    def test_unfilled_and_reserved_paths_refuse(self):
        with self.assertRaisesRegex(ValueError, 'unfilled'):
            m.Writer(dict(self.context, software=None), self.state, self.ledger)
        for output in ('/outputs/.modal-journal/run/task', '/outputs/../inputs/x', '/inputs/x'):
            with self.assertRaises(ValueError):
                self.w.stage('inputs', output)

    def test_prebudget_extract_refuses(self):
        self.chain()
        with self.assertRaises(KeyError):
            self.w.stage('extract', '/outputs/new-extract')

    def test_projection_counts_13_fits_and_full_schedule(self):
        refs = self.chain()
        smoke = {a: {'smoke': {'updates': 32, 'full_schedule_updates': 390, 'seconds_per_update': 2},
                    'timing': dict(dev_scores=False, per_epoch_dev_loss_seconds=3, teacher_seconds=4,
                                   self_seconds=5, teacher_metric_seconds=6, self_metric_seconds=7)} for a in 'AHIW'}
        smoke['extraction_and_rehash'] = {'views_per_second': 20}
        detail = self.store('/outputs/smoke/details.json', smoke)
        result = self.w.doc(refs['smoke'])
        result['artifacts']['details'] = detail
        self.w.local(refs['smoke']['path']).unlink()
        self.state['stage_results']['smoke'] = self.store(refs['smoke']['path'], result)
        self.state['projection'] = dict(total_cache_frames=100, per_fit_diagnostics_serialization_seconds=1,
            source_and_full_cache_hashing_seconds=20, verification_seconds=30, startup_shutdown_seconds=40,
            non_compute_usd=1, safety_factor=1.2)
        value = self.w.forecast()
        one_fit = 390 * 2 + 13 * 3 + 4 + 5 + 6 + 7 + 1
        self.assertEqual(value['measured_fit_seconds'], {'A': 3 * one_fit, 'H': 4 * one_fit, 'I': 3 * one_fit, 'W': 3 * one_fit})
        self.assertAlmostEqual(value['forecast_total_seconds'], 6 + 1.2 * (13 * one_fit + 10 + 20 + 30 + 40))

    def test_templates_are_unlaunchable_and_class_cost_blank(self):
        root = Path(__file__).parent
        ctx = m.read(root / 'context.draft.json')
        state = m.read(root / 'state.draft.json')
        self.assertEqual(set(state['fit_approvals']), set(m.PHASE1 + m.PHASE2))
        self.assertIsNone(ctx['hardware']['class'])
        with self.assertRaisesRegex(ValueError, 'unfilled'):
            m.Writer(ctx, {}, {'approvals': []})
        for phase, keys in (('phase1', m.PHASE1), ('phase2', m.PHASE2)):
            plan = m.read(root / (phase + '-fanout.draft.json'))
            self.assertEqual(set(plan['tasks']), set(keys))
            self.assertIsNone(plan['gpu'])
            self.assertIsNone(plan['resource_rate_usd_second'])
            self.assertIsNone(plan['cap_usd'])
            self.assertFalse(plan['fixes2_review_pass'])
            for key in keys:
                receipt = m.read(root / phase / (key + '.draft.json'))
                self.assertEqual(set(receipt['predecessors']), {'inputs', 'proof128', 'smoke', 'extract'})
                self.assertEqual(set(receipt['fit_predecessors']), set() if phase == 'phase1' else {'phase1_gate'})

    def test_fit_and_fanout_derive_freeze_and_gate(self):
        refs = self.chain()
        budget = dict(context_sha256=self.w.identity, predecessors=refs, hardware_class='cuda:SYNTHETIC',
            hourly_usd=1, cloud_cap_usd=50, forecast_total_seconds=50, projected_modal_usd=1)
        ref = self.store('/inputs/budget.json', budget)
        self.state['budget_approval'] = ref
        self.ledger['approvals'].append(dict(stage='budget', **ref))
        approval = self.w.stage('extract', '/outputs/extract')
        ap = self.store('/inputs/extract.json', approval)
        self.ledger['approvals'].append(dict(stage='extract', **ap))
        result = dict(format='cm3-stage-result-v1', stage='extract', status='PASS', context_sha256=self.w.identity,
            approval=ap, artifacts={'synthetic': 'full freeze'}, elapsed_stage_seconds=1, elapsed_total_seconds=7)
        self.state['stage_results']['extract'] = self.store('/outputs/extract/result.json', result)
        self.state['allocation']['spent_seconds'] = 7
        self.state['fit_approvals'] = {}
        for task in m.PHASE1:
            value = self.w.stage('fit', '/outputs/' + task, task, 'attempt-' + task)
            self.assertEqual(value['freeze'], result['artifacts'])
            self.assertEqual(value['fit_predecessors'], {})
            ref = self.store('/inputs/fits/' + task + '.json', value)
            self.state['fit_approvals'][task] = ref
            self.ledger['approvals'].append(dict(stage='fit', **ref))
        plan = self.w.fanout('phase1', {'fixes2_review_pass': False})
        self.assertFalse(plan['fixes2_review_pass'])
        self.assertEqual(plan['tasks']['H-repeat-0']['attempt_receipts'][0]['path'], 'fits/H-repeat-0.json')
        with self.assertRaises(KeyError):
            self.w.stage('fit', '/outputs/H-1', 'H-1', 'attempt-H-1')
        gate = self.store('/inputs/gate.json', {'context_sha256': self.w.identity, 'status': 'PASS'})
        self.state['phase1_gate'] = gate
        with self.assertRaisesRegex(ValueError, 'ledger approval'):
            self.w.stage('fit', '/outputs/H-1', 'H-1', 'attempt-H-1')
        self.ledger['approvals'].append(dict(stage='phase1_gate', **gate))
        value = self.w.stage('fit', '/outputs/H-1', 'H-1', 'attempt-H-1')
        self.assertEqual(value['fit_predecessors'], {'phase1_gate': gate})

    def test_gate_uses_pinned_judge_and_refuses_repeat_mutation(self):
        source = Path.cwd() / 'docs/evidence/range-bc-countermeasures-3-20260926/judge/judge_cm3-a3.py'
        target = self.w.local('/inputs/judge.py')
        target.parent.mkdir(parents=True)
        target.write_bytes(source.read_bytes())
        self.context['judge'] = {'path': '/inputs/judge.py', 'sha256': m.JUDGE_SHA}
        self.w.identity = m.digest(self.context)
        spec = m.importlib.util.spec_from_file_location('_test_judge', target)
        judge = m.importlib.util.module_from_spec(spec)
        spec.loader.exec_module(judge)
        self.state.update(fit_results={}, fit_records={}, judge_launch=self.store('/inputs/judge-launch.json', {'pins': {'synthetic': True}}))
        results = {}
        for task in m.PHASE1:
            details = dict(checkpoint_sha256='c' * 64, stable_sha256='d' * 64,
                evaluation={'self_fed_checks': dict(any_hold_observable_steps=judge.OBSERVABLE, any_hold_excluded_steps=0,
                    human_any_hold_share=judge.HUMAN, any_hold_share=0., hold_onset_recall=0., press_ratio=1.,
                    actions={a: {'press_ratio': 1.} for a in judge.LIVE}),
                    'self_fed': {'all': {'camera_mae_mean': 1.}}, 'zero_motion_camera_mae': judge.ZERO})
            dr = self.store('/outputs/' + task + '/details.json', details)
            ref = self.store('/outputs/' + task + '/result.json', {'synthetic': True})
            self.state['fit_results'][task] = ref
            self.state['fit_records'][task] = self.store('/outputs/' + task + '/wrapper.json',
                dict(status='COMPLETE', exit=0, result=ref, finished_at=1))
            results[ref['path']] = ({'artifacts': {'details': dr}},
                dict(arm=task[0], seed=int(task[-1]), purpose='repeat' if task == 'H-repeat-0' else 'registered'))
        with patch.object(self.w, 'result', side_effect=lambda ref, stage: results[ref['path']]):
            gate = self.w.gate()
            self.assertEqual(gate['H0_repeat']['H0'], gate['H0_repeat']['repeat'])
            result, _ = results[self.state['fit_results']['H-repeat-0']['path']]
            result['artifacts']['details'] = self.store('/outputs/mutated-details.json', dict(details, stable_sha256='e' * 64))
            with self.assertRaisesRegex(ValueError, 'repeat differs'):
                self.w.gate()


if __name__ == '__main__':
    unittest.main()
