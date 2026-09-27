"""Synthetic-only contract tests. No repository data, reports, media, or weights.

Run python -B test_judge_cm3-a3.py. make_fixture is the JSON integration example;
its made-up hashes, receipts and metrics MUST NOT be used as launch evidence.
Pure judge() tests inject a synthetic MPS reference; the CLI separately pins
actual A-reread bytes and rejects a synthetic replacement. CUDA CLI cases use
only generated temporary JSON. No synthetic bypass exists in the CLI.
"""
import contextlib
import copy
import io
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import sys
import importlib.util

sys.path.insert(0,str(Path(__file__).resolve().parent))
_spec=importlib.util.spec_from_file_location('judge_cm3_a3',Path(__file__).with_name('judge_cm3-a3.py'))
J=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(J)


def h(s):
    return J.digest('SYNTHETIC ONLY: '+str(s))


def at(n):
    return f'2026-09-27T{n//60:02d}:{n%60:02d}:00+00:00'


def checks(passing=True):
    return dict(hold_onset_recall=.1 if passing else 0.,press_ratio=1.,camera_mae=1.,
                any_hold_share=.6,human_any_hold_share=J.HUMAN,zero_motion_camera_mae=J.ZERO,
                any_hold_observable_steps=J.OBSERVABLE,any_hold_excluded_steps=0,steps=J.OBSERVABLE,
                actions={a:{'press_ratio':1.} for a in J.LIVE})


def metric(value,late):
    return dict(window={'early':1,'late':late,'self_fed':True},steps=J.OBSERVABLE,
                valid_steps=J.OBSERVABLE,macro_press_f1_tol=value)


def make_audit(c=1):
    def cell(u,n): return dict(U=u,C=n,E_tenths=10*u-9*n,E=(10*u-9*n)/10)
    a=dict(format='range-bc-cm3-effective-weight-v1',amendment=2,
           sessions={s:{head:cell(10,c) for head in J.HEADS} for s in J.TRAIN},
           totals={head:cell(50,5*c) for head in J.HEADS},
           weight_vectors_sha256={s:h('weight '+s) for s in J.TRAIN},
           windows=5,canonical_windows_sha256=h('windows'),weighting_has_scored_effect=c>0,
           disposition='scored idle weight reduced' if c else 'no scored idle-weight effect')
    a['sha256']=J.digest(a)
    return a


def make_fixture(backend='mps',effect=1):
    device=dict(backend=backend,model='M5 Max' if backend=='mps' else 'AWS L40S',
                instance='SYNTHETIC-NOT-A-HOST',software_description='SYNTHETIC versions')
    names=('cloud_benchmark','device_choice','code_judge_freeze','identities_verified',
           'numerical_probe_start','numerical_proof','smoke_start','smoke_proof','audit_complete','budget_approved','full_cache_start',
           'full_cache_verified','manifest_frozen','launch_approved')
    audit=make_audit(effect)
    pairing={a:{s:dict(core=h('core'+s),heads=h('heads'+s),
                       initial_tensor_manifest=h('initial'+a+s),projectors=h('projectors'+s),
                       window_orders=[h(f'order{s}-{e}') for e in range(13)]) for s in J.SEEDS} for a in J.CORE}
    tags={'lstm':'init/core','global_projector':'init/projector/global',
          'crosshair_projector':'init/projector/crosshair','global_encoder':'init/impala/global',
          'crosshair_encoder':'init/impala/crosshair','history':'init/history','head':'init/head/head'}
    # Deliberately NOT the new-arm recipe: legacy A configuration is separately pinned.
    acfg=dict(recipe='synthetic legacy A',jitter=8,prev_dropout=.2)
    pins={k:h(k) for k in J.PIN_KEYS}
    pins.update(source_cache=J.SOURCE,sidecar=J.SIDECAR,weights=J.WEIGHTS,
                code_closure={'trainer.py':h('code')},audit=audit['sha256'],
                canonical_windows=audit['canonical_windows_sha256'],paired_manifest=J.digest(pairing),
                tag_manifest=J.digest(tags),legacy_config=J.digest(acfg))
    launch=dict(format='cm3-launch-v1',contract_commit='7083055',amendment=3,execution_mode='two-phase',
                contract_sha256=J.AMENDMENT3_SHA256,
                arms=list(J.CORE),seeds=[0,1,2],
                cohort=copy.deepcopy(J.COHORT),live_actions=list(J.LIVE),sidecar_sessions=list(J.TRAIN),
                device=device,pins=pins,configs={a:J.config(a) for a in J.CORE},a_config=acfg,
                a_kind='historical-reread' if backend=='mps' else 'fresh-same-hardware',
                backbone=dict(revision='ed25f3a31f01632728cabb09d1542f84ab7b0056',size=88249960,
                              dim=6528,dtype='<f4',pooling='CLS+4x4-grid',
                              preprocess='registered-section-5',frozen=True),
                proofs={k:dict(passed=True,reviewed=True,receipt_sha256=h(k),
                                completed=at(6),dev_scores_produced=False,
                                code_closure_sha256=J.digest(pins['code_closure'])) for k in J.PROOFS},
                timeline={k:at(i) for i,k in enumerate(names)},
                budget=dict(core_hours_cap=16,forecast_hours_including_spent=1.,spent_preflight_hours=.1,
                            all_epochs_evaluations_controls_repeat_hashing_included=True,
                            cloud_dollar_cap=10.,forecast_dollars=1.),
                audit=audit,pairing=pairing,tags=tags)
    for k in ('benchmark_receipt','device_receipt','budget_receipt','launch_receipt'):
        launch[k]=h(k)
    reports={}
    for a in ('A',*J.CORE):
        r=dict(arm=a,seeds=[0,1,2],scope='plumbing',cohort=copy.deepcopy(J.COHORT),
               device=copy.deepcopy(device),pins=copy.deepcopy(pins),
               config=copy.deepcopy(acfg if a=='A' else J.config(a)),
               validation_opened=False,test_opened=False,sealed_opened=False,dev_weighted=False,
               evaluation=dict(teacher_input='true_previous',teacher_decode='executor',
                               self_input='previous_executor',self_decode='executor',
                               live_actions=list(J.LIVE),dev_rows_sha256=pins['dev_rows']),
               checkpoints={s:h(a+s+('-cuda' if backend=='cuda' and a=='A' else '')) for s in J.SEEDS},
               epochs_log={s:[dict(epoch=e,train_loss=2.,dev={'total':1.}) for e in range(13)] for s in J.SEEDS},
               context={s:dict(wall_seconds=60.,peak_memory_bytes=100.,unweighted_train_loss=2.,
                              peak_memory_source='torch.cuda.max_memory_allocated',peak_memory_reset=True,
                              held_change_f1={act:.1 for act in J.LIVE},raw_teacher_forced={'synthetic':True},
                              executed_counts={'synthetic':True},normalized_feature_diagnostics={'synthetic':True},
                              gate_diagnostics={'synthetic':True}) for s in J.SEEDS})
        if a=='A':
            r['control_kind']=launch['a_kind']
        else:
            r['pairing']=copy.deepcopy(pairing[a]);r['audit_sha256']=pins['audit']
        r['metrics']={'dev':dict(self_fed_checks={'model_nohud':{s:checks(a!='A') for s in J.SEEDS}},
            executed_teacher_forced={'model_nohud':{s:metric(.03,0) for s in J.SEEDS}},
            self_fed={'model_nohud':{s:{'all':metric(.1 if a!='A' else 0.,1)} for s in J.SEEDS}})}
        reports[a]=r
    ex=[]
    order=[('A',s) for s in J.SEEDS]+[('H','0'),('H-repeat','0'),('H','1'),('H','2')]+[
        (a,s) for a in ('I','W') for s in J.SEEDS]
    for i,(a,s) in enumerate(order):
        base='H' if a=='H-repeat' else a
        ex.append(dict(arm=a,seed=int(s),start=at(20+i*2),end=at(21+i*2),device=copy.deepcopy(device),
                       checkpoint_sha256=reports[base]['checkpoints'][s],content_sha256=h('content'+base+s)))
    packet=dict(format='cm3-reports-v1',status='COMPLETE',interruption=None,core=reports,
                execution=ex,elapsed_compute_seconds=2000.,reader=None,phase1_gate=phase_gate(launch,ex))
    host={a+'/'+s:{'sha256':r['checkpoints'][s],
                  'folder':'interim94-s012' if a=='A' and backend=='mps' else 'cm3-'+a.lower()+'-s012'}
          for a,r in reports.items() for s in J.SEEDS}
    c,t,_=J.metric_blocks(reports['A'])
    reference=dict(equal={'synthetic_blocks':True},self_fed_checks={'model_nohud':copy.deepcopy(c)},
                   executed_teacher_forced={'model_nohud':copy.deepcopy(t)})
    return launch,packet,host,reference


def phase_gate(launch,execution,completed=None):
    by_id={(r['arm'],str(r['seed'])):r for r in execution}
    def identity(a,s):
        return {k:by_id[a,s][k] for k in ('checkpoint_sha256','content_sha256')}
    return dict(format='cm3-phase1-gate-v1',status='PASS',completed=completed or at(30),
                launch_pins_sha256=J.digest(launch['pins']),
                A_control_gate=dict(status='PASS',controls={s:identity('A',s) for s in J.SEEDS}),
                H0_repeat=dict(status='PASS',repeat_identical=True,H0=identity('H','0'),
                               repeat=identity('H-repeat','0')))


def parity():
    fields=('webs','hp','max_hp','ult_ready','ult_charge',*[a+'_'+q for a in
            ('swing','get_over_here','amazing_combo') for q in ('ready','charges','cooldown')])
    p=dict(fresh_authorized=True,validation_or_sealed=False,blinded_labels=True,
           known_zero_unknown_mutation=True,wrong_slot_mutation=True,wrong_layout_mutation=True,
           previous_parity_sources_reused=False,stratified_error_report={'synthetic':True},
           ready_occluded_share={'mnk':0.,'pad':0.},ready_eligible_denominator={'mnk':80,'pad':80},
           supported_fields={layout:list(fields) for layout in ('mnk','pad')},
           layouts={layout:{name:dict(structurally_unavailable=False,legible=40,correct_known=40,
                    known_wrong=0,unreadable_known=0,true_examples=20,false_examples=20,
                    low_resource_examples=20,absolute_tolerance=.05) for name in fields}
                    for layout in ('mnk','pad')})
    for k in ('labels_sha256','reader_sha256','schema_sha256','adapter_sha256','review_sha256'):
        p[k]=h(k)
    return p


def add_reader(l,p,host,base='H'):
    auth=dict(selected=base,device=l['device'],scope='train-only-precheck',copied_initialization_proof=True,
              smoke_updates=32,dev_scores_in_smoke=False,forecast_hours_including_precheck=1.,precheck=parity())
    auth['precheck']['layouts'].pop('pad');auth['precheck']['supported_fields'].pop('pad')
    auth['precheck'].update(initial_sample_per_session={s:40 for s in J.TRAIN},sample_seed=20260928,
                           additional_predrawn_frames=0,first_coverage_stop=True,all_inspected_retained=True)
    auth['supported_fields']=parity()['supported_fields']
    for k in ('initialization_sha256','schema_sha256','adapter_sha256','reader_sha256','cache_sha256',
              'cache_verification_sha256','budget_receipt','launch_receipt'):
        auth[k]=h(k)
    for i,k in enumerate(('core_judged','precheck_passed','smoke_passed','budget_approved',
                          'full_cache_start','cache_verified','launch_approved','fit_start')):
        auth[k]=at(80+i)
    r=copy.deepcopy(p['core'][base]);r['arm']='R';r['base_arm']=base
    r['config']={**J.config(base),'reader':True,'reader_dim':28,'reader_width':64}
    r['reader_authorization_sha256']=J.digest(auth)
    r['copied_initialization_sha256']=auth['initialization_sha256']
    host.update({'R/'+s:{'sha256':r['checkpoints'][s],'folder':'cm3-r-s012'} for s in J.SEEDS})
    p['reader']=dict(report=r,parity=parity(),elapsed_compute_seconds=3600.,
                     unknown_interventions={'full-vector':{'synthetic':True},'per-field':{'synthetic':True}})
    return auth


def legacy_report(r):
    return {'metrics':{'dev':{'self_fed':{'model_nohud':copy.deepcopy(J.metric_blocks(r)[2])}}},
            'checkpoints':{'model_nohud-seed'+s+'.pt':r['checkpoints'][s] for s in J.SEEDS},
            'epochs_log':{'model_nohud-seed'+s+'.pt':copy.deepcopy(r['epochs_log'][s]) for s in J.SEEDS}}


class MathTests(unittest.TestCase):
    def test_thresholds_just_below_equal_above(self):
        cases=[('hold_onset_recall',.05,'S1',(False,True,True)),
               ('press_ratio',.5,'S2',(False,True,True)),('press_ratio',2.,'S2',(True,True,False)),
               ('camera_mae',.95*J.ZERO,'S3',(True,True,False)),
               ('any_hold_share',.5*J.HUMAN,'S4',(False,True,True)),
               ('any_hold_share',1.3*J.HUMAN,'S4',(True,True,False))]
        for field,bar,key,wants in cases:
            for v,want in zip((math.nextafter(bar,-math.inf),bar,math.nextafter(bar,math.inf)),wants):
                with self.subTest(field=field,value=v):
                    c=checks();c[field]=v
                    self.assertEqual(J.seed_checks(c)[key],want)

    def test_action_boundaries_five_six_and_pooled(self):
        for threshold in (.5,2.):
            for v in (math.nextafter(threshold,-math.inf),threshold,math.nextafter(threshold,math.inf)):
                for n in (5,6,10):
                    c=checks()
                    for i,a in enumerate(J.LIVE): c['actions'][a]['press_ratio']=v if i<n else 0.
                    self.assertEqual(J.seed_checks(c)['S2'],n>=6 and .5<=v<=2)
        c=checks()
        for a in J.LIVE:c['actions'][a]['press_ratio']=0.
        self.assertFalse(J.seed_checks(c)['S2'])
        c=checks();c['press_ratio']=0.
        self.assertFalse(J.seed_checks(c)['S2'])

    def test_exact_action_identity_not_count(self):
        for mode in ('missing','extra','alias'):
            c=checks()
            if mode!='extra':del c['actions'][J.LIVE[0]]
            if mode!='missing':c['actions']['ALIEN']={'press_ratio':1.}
            with self.assertRaises(J.Invalid):J.seed_checks(c)

    def test_null_shares_fail(self):
        for k in ('any_hold_share','human_any_hold_share'):
            c=checks();c[k]=None
            self.assertFalse(J.seed_checks(c)['S4'])

    def test_two_complete_seed_passes_not_distributed(self):
        c={s:checks() for s in J.SEEDS}
        t={s:metric(.1,0) for s in J.SEEDS};f={s:{'all':metric(.1,1)} for s in J.SEEDS}
        c['0']['hold_onset_recall']=0.;c['1']['camera_mae']=2.;c['2']['any_hold_share']=0.
        self.assertFalse(J.arm(c,t,f)['passes_S'])
        c['1']=checks();c['2']=checks()
        self.assertTrue(J.arm(c,t,f)['passes_S'])

    def test_stats_range_and_unrounded(self):
        self.assertEqual(J.stats([.1,.2,.3]),dict(values=[.1,.2,.3],mean=(.1+.2+.3)/3,range=.3-.1))

    def test_legacy_math_interface_without_new_config(self):
        # Synthetic old-style blocks, deliberately no round-3 config or receipts.
        c={s:checks(False) for s in J.SEEDS}
        t={s:metric(.125,0) for s in J.SEEDS};f={s:{'all':metric(0.,1)} for s in J.SEEDS}
        a=J.arm(c,t,f)
        self.assertFalse(a['passes_S']);self.assertEqual(a['T']['mean'],.125)
        self.assertEqual(a['F']['mean'],0.);self.assertEqual(a['T']['range'],0.)


class PacketTests(unittest.TestCase):
    def setUp(self):
        self.l,self.p,self.host,self.ref=make_fixture()
        self.legacy=legacy_report(self.p['core']['A'])

    def run_judge(self,**kw):
        return J.judge(self.l,self.p,self.host,mps_reference=self.ref,legacy_report=self.legacy,**kw)

    def assert_invalid(self):
        r=self.run_judge();self.assertEqual(r['status'],'INVALID',r);self.assertIsNone(r['selected'])

    def test_complete_tie_is_H_and_seed_zero(self):
        r=self.run_judge()
        self.assertEqual(r['status'],'COMPLETE',r)
        self.assertEqual((r['outcome'],r['selected'],r['candidate_seed']),('Multiple work','H',0))
        self.assertTrue(all(r['report_checks'][a]=='PASS' for a in ('A',*J.CORE)))
        self.assertIn('per_head_effect',r['effective_weight_audit'])

    def test_all_single_arm_outcomes(self):
        for winner,title in (('H','Headline works'),('I','Feature control wins'),('W','Weak history wins')):
            self.setUp()
            for a in J.CORE:
                if a!=winner:
                    for c in J.metric_blocks(self.p['core'][a])[0].values():c['camera_mae']=2.
            r=self.run_judge()
            self.assertEqual((r['selected'],r['outcome']),(winner,title),r)

    def test_near_miss_is_failure_not_retuned(self):
        for a in J.CORE:
            for c in J.metric_blocks(self.p['core'][a])[0].values():c['hold_onset_recall']=math.nextafter(.05,0.)
        r=self.run_judge();self.assertEqual(r['outcome'],'Neither works');self.assertIsNone(r['selected'])

    def test_live_less_skilled(self):
        for a in J.CORE:
            for m in J.metric_blocks(self.p['core'][a])[1].values():m['macro_press_f1_tol']=0.
        r=self.run_judge();self.assertEqual(r['outcome'],'Live but less skilled')

    def test_K_equal_and_negative_bar_not_clipped(self):
        r=self.run_judge();self.assertEqual(r['arms']['H']['T']['mean'],r['arms']['H']['K_bar'])
        self.assertTrue(r['arms']['H']['K'])
        for s,v in zip(J.SEEDS,(0.,0.,.9)):
            J.metric_blocks(self.p['core']['H'])[1][s]['macro_press_f1_tol']=v
        r=self.run_judge();self.assertLess(r['arms']['H']['K_bar'],0);self.assertTrue(r['arms']['H']['K'])

    def test_K_just_below_equal_above(self):
        self.l,self.p,self.host,self.ref=make_fixture('cuda')
        for m in J.metric_blocks(self.p['core']['A'])[1].values():m['macro_press_f1_tol']=.125
        for v,want in ((math.nextafter(.125,0.),False),(.125,True),(math.nextafter(.125,1.),True)):
            for m in J.metric_blocks(self.p['core']['H'])[1].values():m['macro_press_f1_tol']=v
            self.assertEqual(self.run_judge()['arms']['H']['K'],want)

    def test_range_tie_boundary_inclusive(self):
        # Exact binary fractions: W mean .5/range .25; H mean .25/range 0.
        for a,vals in {'H':[.25]*3,'I':[0.]*3,'W':[.375,.5,.625]}.items():
            for s,v in zip(J.SEEDS,vals):J.metric_blocks(self.p['core'][a])[2][s]['all']['macro_press_f1_tol']=v
        r=self.run_judge();self.assertEqual(r['best_mean_F'],'W');self.assertEqual(r['selected'],'H')
        for s in J.SEEDS:J.metric_blocks(self.p['core']['H'])[2][s]['all']['macro_press_f1_tol']=.24
        self.assertEqual(self.run_judge()['selected'],'W')

    def test_near_tie_relative_to_best_not_chain(self):
        for a,vals in {'H':[0.,.02,.04],'I':[.07,.08,.09],'W':[.09,.10,.11]}.items():
            for s,v in zip(J.SEEDS,vals):J.metric_blocks(self.p['core'][a])[2][s]['all']['macro_press_f1_tol']=v
        r=self.run_judge();self.assertEqual(r['best_mean_F'],'W');self.assertEqual(r['selected'],'I')
        self.assertNotIn('H',r['near_tied'])

    def test_seed_zero_candidate_even_when_it_fails(self):
        J.metric_blocks(self.p['core']['H'])[0]['0']['hold_onset_recall']=0.
        r=self.run_judge();self.assertEqual(r['selected'],'H');self.assertEqual(r['candidate_seed'],0)
        self.assertFalse(r['candidate_seed_passes_S'])

    def test_null_and_nonfinite_report_metrics_invalid(self):
        for v in (None,math.nan,math.inf,-math.inf,True):
            for k in ('hold_onset_recall','press_ratio','camera_mae','any_hold_share'):
                self.setUp();J.metric_blocks(self.p['core']['H'])[0]['0'][k]=v
                self.assert_invalid()

    def test_missing_seed_metric_and_action(self):
        for index in range(3):
            self.setUp();del J.metric_blocks(self.p['core']['H'])[index]['1'];self.assert_invalid()
        self.setUp();del J.metric_blocks(self.p['core']['H'])[1]['0']['macro_press_f1_tol'];self.assert_invalid()
        self.setUp();del J.metric_blocks(self.p['core']['H'])[0]['0']['actions'][J.LIVE[0]];self.assert_invalid()

    def test_wrong_skill_block_late_counts_raw(self):
        for mutation in ('late','raw','counts','source','decode'):
            self.setUp();r=self.p['core']['H'];m=J.metric_blocks(r)[1]['0']
            if mutation=='late':m['window']['late']=1
            if mutation=='raw':m['window']['self_fed']=False
            if mutation=='counts':m['macro_press_count']=m.pop('macro_press_f1_tol')
            if mutation=='source':r['config']['g1_press_source']='teacher_forced'
            if mutation=='decode':r['evaluation']['teacher_decode']='raw'
            self.assert_invalid()

    def test_wrong_dev_denominators_baselines(self):
        for k in ('human_any_hold_share','zero_motion_camera_mae','any_hold_observable_steps',
                  'any_hold_excluded_steps','steps'):
            self.setUp();c=J.metric_blocks(self.p['core']['H'])[0]['0'];c[k]+=1;self.assert_invalid()
        self.setUp();self.p['core']['H']['evaluation']['live_actions'][0]='bad';self.assert_invalid()

    def test_all_pins_checked(self):
        for key in J.PIN_KEYS:
            self.setUp();self.p['core']['H']['pins'][key]=h('wrong');self.assert_invalid()
        for key in J.PIN_KEYS:
            self.setUp();del self.l['pins'][key];self.assert_invalid()

    def test_all_registered_config_fields_checked(self):
        for key in J.config('H'):
            self.setUp();del self.p['core']['H']['config'][key];self.assert_invalid()
        for a in J.CORE:
            for k,v in (('idle_k',29),('idle_weight',.2),('prev_dropout',.2)):
                self.setUp();self.p['core'][a]['config'][k]=v;self.assert_invalid()

    def test_cohort_changes_or_duplicates(self):
        for kind in ('role','session_id','steps_sha256','duplicate'):
            self.setUp();rows=self.p['core']['H']['cohort']
            if kind=='duplicate':rows.append(copy.deepcopy(rows[0]))
            else:rows[0][kind]='wrong'
            self.assert_invalid()

    def test_no_validation_test_sealed_or_dev_weight(self):
        for key in ('validation_opened','test_opened','sealed_opened','dev_weighted'):
            self.setUp();self.p['core']['H'][key]=True;self.assert_invalid()
        self.setUp();self.l['sidecar_sessions'].append(J.COHORT[-1]['session_id']);self.assert_invalid()

    def test_exact_arms_no_N_alias_or_missing(self):
        for mode in ('extra','missing','alias','duplicate_seed'):
            self.setUp()
            if mode=='extra':self.p['core']['N']=copy.deepcopy(self.p['core']['H'])
            if mode=='missing':del self.p['core']['W']
            if mode=='alias':self.p['core']['N']=self.p['core'].pop('W')
            if mode=='duplicate_seed':self.p['core']['H']['seeds']=[0,0,2]
            self.assert_invalid()

    def test_missing_each_proof_and_failed_mutation(self):
        for k in J.PROOFS:
            self.setUp();del self.l['proofs'][k];self.assert_invalid()
            self.setUp();self.l['proofs'][k]['passed']=False;self.assert_invalid()

    def test_timing_and_budget_gates(self):
        for event in ('device_choice','numerical_proof','budget_approved','manifest_frozen'):
            self.setUp();self.l['timeline'][event]=at(50);self.assert_invalid()
        self.setUp();self.p['execution'][0]['start']=at(1);self.assert_invalid()
        self.setUp();self.p['execution'][5]['start']=at(20);self.assert_invalid()
        self.setUp();self.l['proofs']['feature_repeat']['dev_scores_produced']=True;self.assert_invalid()
        self.setUp();self.l['budget']['forecast_hours_including_spent']=16.1;self.assert_invalid()

    def test_paired_hash_tag_order_changes(self):
        for field in ('core','heads','window_orders','initial_tensor_manifest','projectors'):
            self.setUp();self.p['core']['H']['pairing']['0'][field]=h('changed');self.assert_invalid()
        self.setUp();self.l['tags']['head']='init/other';self.assert_invalid()
        self.setUp();self.p['execution'][4]['content_sha256']=h('nondeterministic');self.assert_invalid()

    def test_incomplete_does_not_judge_favorable_subset(self):
        self.p['status']='INCOMPLETE';self.p['interruption']='time cap';del self.p['core']['I']
        r=self.run_judge();self.assertEqual(r['status'],'INCOMPLETE');self.assertIsNone(r['selected'])
        self.setUp();self.p['elapsed_compute_seconds']=16*3600+1
        r=self.run_judge();self.assertEqual(r['status'],'INCOMPLETE');self.assertIsNone(r['selected'])

    def test_final_epoch_and_host_pins(self):
        self.p['core']['H']['epochs_log']['0'].pop();self.assert_invalid()
        self.setUp();self.p['core']['H']['config']['checkpoint']='best';self.assert_invalid()
        self.setUp();self.host['H/0']['sha256']=h('wrong');self.assert_invalid()

    def test_mps_control_changed_or_missing(self):
        self.ref['executed_teacher_forced']['model_nohud']['0']['macro_press_f1_tol']=.99
        self.assert_invalid()
        self.setUp();self.ref=None;self.assert_invalid()
        self.setUp();self.ref['equal']['synthetic_blocks']=False;self.assert_invalid()

    def test_mps_legacy_self_fed_and_logs_stay_frozen(self):
        self.legacy['metrics']['dev']['self_fed']['model_nohud']['0']['all']['macro_press_f1_tol']=.5
        self.assert_invalid()
        self.setUp();self.legacy['epochs_log']['model_nohud-seed0.pt'][0]['dev']['total']=3.
        self.assert_invalid()

    def test_mps_A_passes_is_sanity_stop(self):
        for c in J.metric_blocks(self.p['core']['A'])[0].values():c['hold_onset_recall']=.1
        self.ref['self_fed_checks']['model_nohud']=copy.deepcopy(J.metric_blocks(self.p['core']['A'])[0])
        r=self.run_judge();self.assertEqual(r['status'],'INVALID')
        self.assertEqual(r['outcome'],'Invalid / sanity failure');self.assertIsNone(r['selected'])

    def test_cuda_same_hardware_A_and_control_stop(self):
        self.l,self.p,self.host,self.ref=make_fixture('cuda')
        r=self.run_judge();self.assertEqual(r['status'],'COMPLETE',r)
        for c in J.metric_blocks(self.p['core']['A'])[0].values():c['hold_onset_recall']=.1
        r=self.run_judge();self.assertEqual(r['status'],'INVALID');self.assertEqual(r['outcome'],'Changed control regime')

    def test_cuda_K_uses_fresh_A_not_MPS(self):
        self.l,self.p,self.host,self.ref=make_fixture('cuda')
        for m in J.metric_blocks(self.p['core']['A'])[1].values():m['macro_press_f1_tol']=.9
        r=self.run_judge();self.assertEqual(r['arms']['H']['K_bar'],.9);self.assertFalse(r['arms']['H']['K'])

    def test_cuda_wrong_A_lineage_model_or_seed(self):
        for mode in ('lineage','model','missing_seed','execution_device'):
            self.l,self.p,self.host,self.ref=make_fixture('cuda')
            if mode=='lineage':self.p['core']['A']['control_kind']='historical-reread'
            if mode=='model':self.p['core']['I']['device']['model']='AWS L4'
            if mode=='missing_seed':del self.p['core']['A']['checkpoints']['2']
            if mode=='execution_device':self.p['execution'][0]['device']['backend']='mps'
            self.assert_invalid()

    def test_F1_A_folder_enforced_on_both_backends(self):
        for backend,wrong in (('mps','cm3-a-s012'),('cuda','interim94-s012')):
            self.l,self.p,self.host,self.ref=make_fixture(backend)
            self.host['A/0']['folder']=wrong
            self.assert_invalid()

    def test_F1_cuda_rejects_any_historical_checkpoint_even_other_seed(self):
        self.l,self.p,self.host,self.ref=make_fixture('cuda')
        old=self.legacy['checkpoints']['model_nohud-seed2.pt']
        self.p['core']['A']['checkpoints']['0']=old
        self.host['A/0']['sha256']=old
        self.p['execution'][0]['checkpoint_sha256']=old
        self.p['phase1_gate']['A_control_gate']['controls']['0']['checkpoint_sha256']=old
        r=self.run_judge()
        self.assertEqual(r['status'],'INVALID')
        self.assertIn('historical MPS checkpoint',' '.join(r['check_failures']))

    def test_F1_cuda_historical_T_and_missing_legacy_are_invalid(self):
        self.l,self.p,self.host,self.ref=make_fixture('cuda')
        for s,v in zip(J.SEEDS,J.HISTORICAL_T):
            J.metric_blocks(self.p['core']['A'])[1][s]['macro_press_f1_tol']=v
        r=self.run_judge();self.assertEqual(r['status'],'INVALID')
        self.assertIn('T tuple equals historical',' '.join(r['check_failures']))
        self.l,self.p,self.host,self.ref=make_fixture('cuda');self.legacy=None
        self.assert_invalid()

    def test_F2_lists_in_core_and_launch_yield_invalid(self):
        self.p['core']=[];self.assert_invalid()
        self.setUp();self.p['core']['H']['metrics']['dev']['self_fed_checks']=[];self.assert_invalid()
        self.setUp();self.l=[];self.assert_invalid()
        self.setUp();self.l['audit']['sessions'][J.TRAIN[0]]=list(J.HEADS);self.assert_invalid()

    def test_F2_lists_in_reader_preserve_core(self):
        for field in ('packet','layouts','authorization'):
            self.setUp();auth=add_reader(self.l,self.p,self.host)
            if field=='packet':self.p['reader']=[]
            elif field=='layouts':self.p['reader']['parity']['layouts']=['mnk','pad']
            else:auth=[]
            r=self.run_judge(reader_authorization=auth)
            self.assertEqual((r['status'],r['selected']),('COMPLETE','H'),r)
            self.assertEqual(r['reader']['outcome'],'R fails / undecided')

    def test_F2_index_errors_are_converted_at_core_and_reader_boundaries(self):
        with mock.patch.object(J,'check_report',side_effect=IndexError('synthetic malformed core')):
            self.assert_invalid()
        with mock.patch.object(J,'check_launch',side_effect=IndexError('synthetic malformed launch')):
            self.assert_invalid()
        auth=add_reader(self.l,self.p,self.host)
        with mock.patch.object(J,'reader_parity',side_effect=IndexError('synthetic malformed reader')):
            r=self.run_judge(reader_authorization=auth)
        self.assertEqual((r['status'],r['selected']),('COMPLETE','H'))
        self.assertEqual(r['reader']['outcome'],'R fails / undecided')

    def test_F3_proofs_cannot_predate_stage_or_change_code(self):
        for proof,early in (('legacy_same_backend',1),('feature_repeat',3),
                            ('cpu_feature_tolerance',3),('initialized_logits_tolerance',3),
                            ('initialized_decisions',3),('trained_logits_tolerance',5),
                            ('trained_decisions',5),('smoke_repeat',5)):
            self.setUp();self.l['proofs'][proof]['completed']=at(early);self.assert_invalid()
        for proof in J.PROOFS:
            self.setUp();self.l['proofs'][proof]['code_closure_sha256']=h('different code');self.assert_invalid()
        self.setUp();del self.l['proofs']['feature_repeat']['code_closure_sha256'];self.assert_invalid()

    def test_F3_exact_stage_lower_bounds_pass(self):
        for proof,stage in (('legacy_same_backend','code_judge_freeze'),
                            ('feature_repeat','numerical_probe_start'),('smoke_repeat','smoke_start')):
            self.l['proofs'][proof]['completed']=self.l['timeline'][stage]
        self.assertEqual(self.run_judge()['status'],'COMPLETE')

    def test_F4_no_selected_core_means_reader_NOT_RUN(self):
        for supplied in (False,True):
            self.setUp();auth=add_reader(self.l,self.p,self.host) if supplied else None
            for a in J.CORE:
                for c in J.metric_blocks(self.p['core'][a])[0].values():c['hold_onset_recall']=0.
            r=self.run_judge(reader_authorization=auth)
            self.assertEqual(r['status'],'COMPLETE');self.assertEqual(r['outcome'],'Neither works')
            self.assertEqual(r['reader'],{'outcome':'R not run','status':'NOT RUN',
                                          'reason':'no selected eligible core recipe'})

    def test_F5_late_invalid_clears_every_selection_field(self):
        del self.p['reader']  # Failure after selection/contrasts, before conditional reader.
        r=self.run_judge();self.assertEqual(r['status'],'INVALID');self.assertIsNone(r['selected'])
        for k in ('eligible','near_tied','selected_outcome','best_mean_F','candidate_seed',
                  'candidate_seed_passes_S','meaning'):
            self.assertNotIn(k,r)

    def test_zero_audit_keeps_all_three_arms(self):
        self.l,self.p,self.host,self.ref=make_fixture(effect=0)
        r=self.run_judge();self.assertEqual(r['status'],'COMPLETE',r);self.assertEqual(r['selected'],'H')
        self.assertFalse(r['effective_weight_audit']['weighting_has_scored_effect'])
        self.assertEqual(set(r['arms']),{'A','H','I','W'})

    def test_audit_raw_count_cannot_replace_scored_mass(self):
        self.l['audit']['weighted_raw_rows']=753
        del self.l['audit']['sessions'][J.TRAIN[0]]['camera']['C']
        self.assert_invalid()

    def test_audit_mismatch_integer_bounds_and_total(self):
        for key,val in (('U',-1),('C',11),('C',.1),('E_tenths',100),('E',100.)):
            self.setUp();self.l['audit']['sessions'][J.TRAIN[0]]['held'][key]=val;self.assert_invalid()
        self.setUp();self.l['audit']['totals']['camera']['C']+=1;self.assert_invalid()

    def test_reader_qualifies_but_no_promotion(self):
        auth=add_reader(self.l,self.p,self.host)
        r=self.run_judge(reader_authorization=auth)
        self.assertEqual(r['reader']['outcome'],'R qualifies',r['reader'])
        self.assertEqual(r['selected'],'H')

    def test_reader_wrong_recipe_missing_parity_and_coverage(self):
        for mode in ('base','missing','coverage','wrong','unknown','layout','power','authorization'):
            self.setUp();auth=add_reader(self.l,self.p,self.host)
            if mode=='base':self.p['reader']['report']['base_arm']='I'
            if mode=='missing':del self.p['reader']['parity']['review_sha256']
            if mode=='coverage':self.p['reader']['parity']['layouts']['pad']['webs']['legible']=19
            if mode=='wrong':self.p['reader']['parity']['layouts']['mnk']['hp']['known_wrong']=1
            if mode=='unknown':self.p['reader']['parity']['known_zero_unknown_mutation']=False
            if mode=='layout':del self.p['reader']['parity']['layouts']['pad']
            if mode=='power':self.p['reader']['parity']['layouts']['pad']['ult_ready']['false_examples']=0
            if mode=='authorization':auth=None
            r=self.run_judge(reader_authorization=auth)
            self.assertEqual(r['status'],'COMPLETE');self.assertNotEqual(r['reader']['outcome'],'R qualifies')

    def test_reader_noninferiority_boundary_and_failure(self):
        auth=add_reader(self.l,self.p,self.host)
        self.assertEqual(self.run_judge(reader_authorization=auth)['reader']['outcome'],'R qualifies')
        for m in J.metric_blocks(self.p['reader']['report'])[2].values():m['all']['macro_press_f1_tol']=.01
        self.assertEqual(self.run_judge(reader_authorization=auth)['reader']['outcome'],'R fails')

    def test_reader_vacuous_all_unavailable_cannot_qualify(self):
        auth=add_reader(self.l,self.p,self.host)
        for layout,rows in self.p['reader']['parity']['layouts'].items():
            for v in rows.values():v.update(structurally_unavailable=True,declared_before_labels=True,known=0)
            self.p['reader']['parity']['supported_fields'][layout]=[]
        r=self.run_judge(reader_authorization=auth)
        self.assertEqual(r['status'],'COMPLETE');self.assertNotEqual(r['reader']['outcome'],'R qualifies')

    def test_reader_bad_sampling_budget_and_different_selected_recipe(self):
        for mode in ('sample','budget','device','selected','cache_time'):
            self.setUp();auth=add_reader(self.l,self.p,self.host)
            if mode=='sample':auth['precheck']['additional_predrawn_frames']=201
            if mode=='budget':auth['forecast_hours_including_precheck']=6.01
            if mode=='device':auth['device']={**auth['device'],'model':'AWS L4'}
            if mode=='selected':auth['selected']='I'
            if mode=='cache_time':auth['full_cache_start']=at(0)
            self.p['reader']['report']['reader_authorization_sha256']=J.digest(auth)
            r=self.run_judge(reader_authorization=auth)
            self.assertNotEqual(r['reader']['outcome'],'R qualifies');self.assertEqual(r['selected'],'H')


class Amendment3Tests(unittest.TestCase):
    def setUp(self):
        self.l,self.p,self.host,self.ref=make_fixture('cuda')
        self.legacy=legacy_report(make_fixture()[1]['core']['A'])
        self.set_model('modal:L4')
        for r in self.p['execution']:
            first=r['arm']=='A' or (r['arm'] in ('H','H-repeat') and r['seed']==0)
            r['start']=at(20 if first else 22)
            r['end']=at(21 if first else 23)
        self.p['phase1_gate']=phase_gate(self.l,self.p['execution'],at(22))

    def set_model(self,model):
        self.l['device'].update(model=model,instance=model)
        self.l['benchmark_provider']='modal'
        for r in self.p['core'].values():r['device']=copy.deepcopy(self.l['device'])
        for r in self.p['execution']:r['device']=copy.deepcopy(self.l['device'])

    def run_judge(self):
        return J.judge(self.l,self.p,self.host,legacy_report=self.legacy)

    def test_parallel_phase1_and_phase2_pass_for_all_Modal_classes(self):
        for model in ('modal:L4','modal:A10','modal:L40S'):
            self.set_model(model)
            self.p['execution'].reverse()  # receipt/list order is not execution order
            result=self.run_judge()
            self.assertEqual((result['status'],result['selected']),('COMPLETE','H'),result)

    def test_phase2_before_gate_rejected_even_after_all_phase1_fits(self):
        for row in self.p['execution']:
            if row['arm']=='I' and row['seed']==0:row['start']=at(21)
        r=self.run_judge();self.assertEqual(r['status'],'INVALID')
        self.assertIn('phase-2 fit starts before phase-1 gate',' '.join(r['check_failures']))

    def test_gate_before_any_phase1_fit_finishes_rejected(self):
        for row in self.p['execution']:
            if row['arm']=='A' and row['seed']==2:row['end']=at(23)
        r=self.run_judge();self.assertEqual(r['status'],'INVALID')
        self.assertIn('phase-1 completion',' '.join(r['check_failures']))

    def test_mixed_hardware_class_rejected_in_report_or_execution(self):
        for field in ('report','execution'):
            self.setUp()
            if field=='report':self.p['core']['I']['device']['model']='modal:A10'
            else:self.p['execution'][4]['device']['model']='modal:L40S'
            self.assertEqual(self.run_judge()['status'],'INVALID')

    def test_Modal_requires_its_benchmark_and_pre_result_choice(self):
        self.l['benchmark_provider']='aws'
        self.assertEqual(self.run_judge()['status'],'INVALID')
        self.setUp();self.l['timeline']['device_choice']=at(23)
        self.assertEqual(self.run_judge()['status'],'INVALID')
        self.setUp();self.l['contract_sha256']=h('wrong preregistration')
        self.assertEqual(self.run_judge()['status'],'INVALID')

    def test_gate_missing_failed_or_not_bound_to_phase1_outputs(self):
        for mode in ('missing','control','repeat','reference','launch'):
            self.setUp();gate=self.p['phase1_gate']
            if mode=='missing':del self.p['phase1_gate']
            if mode=='control':gate['A_control_gate']['status']='FAIL'
            if mode=='repeat':gate['H0_repeat']['repeat_identical']=False
            if mode=='reference':gate['A_control_gate']['controls']['0']['checkpoint_sha256']=h('other attempt')
            if mode=='launch':gate['launch_pins_sha256']=h('other launch')
            self.assertEqual(self.run_judge()['status'],'INVALID')

    def test_control_PASS_claim_cannot_override_actual_A_S(self):
        for c in J.metric_blocks(self.p['core']['A'])[0].values():c['hold_onset_recall']=.1
        r=self.run_judge()
        self.assertEqual((r['status'],r['outcome']),('INVALID','Changed control regime'))
        self.assertIsNone(r['selected'])

    def test_repeat_PASS_claim_cannot_override_bytes(self):
        for r in self.p['execution']:
            if r['arm']=='H-repeat':r['content_sha256']=h('different decisions')
        self.p['phase1_gate']=phase_gate(self.l,self.p['execution'],at(22))
        r=self.run_judge();self.assertEqual(r['status'],'INVALID')
        self.assertIn('H0 exact full repeat',' '.join(r['check_failures']))

    def test_duplicates_and_missing_fits_cannot_hide_in_parallel_matrix(self):
        self.p['execution'].append(copy.deepcopy(self.p['execution'][0]))
        self.assertEqual(self.run_judge()['status'],'INVALID')
        self.setUp();self.p['execution'].pop()
        self.assertEqual(self.run_judge()['status'],'INVALID')

    def test_parallel_budget_charges_sum_not_makespan(self):
        # All jobs take 60s each: 13*60 + 360 preflight, NOT the 180s makespan.
        self.p['elapsed_compute_seconds']=540.
        self.assertEqual(self.run_judge()['status'],'INVALID')
        self.p['elapsed_compute_seconds']=1140.
        self.assertEqual(self.run_judge()['status'],'COMPLETE')
        self.p['elapsed_compute_seconds']=16*3600+1
        self.assertEqual(self.run_judge()['status'],'INCOMPLETE')

    def test_MPS_null_peak_with_sampled_driver_high_water_passes_all_arms(self):
        self.l,self.p,self.host,self.ref=make_fixture('mps')
        baseline=J.judge(self.l,self.p,self.host,mps_reference=self.ref,legacy_report=self.legacy)
        for r in self.p['core'].values():
            for ctx in r['context'].values():ctx.update(mps_memory())
        actual=J.judge(self.l,self.p,self.host,mps_reference=self.ref,legacy_report=self.legacy)
        self.assertEqual(actual['status'],'COMPLETE',actual)
        self.assertEqual(actual['arms'],baseline['arms'])
        self.assertEqual(actual['selected'],baseline['selected'])
        self.assertIsNone(actual['context']['H']['0']['peak_memory_bytes'])
        self.assertEqual(actual['context']['H']['0']['sampled_driver_high_water_bytes'],123456.)

    def test_MPS_memory_disposition_missing_wrong_or_nonfinite_rejected(self):
        for field,bad in (('peak_memory_status','unknown'),('sampled_driver_high_water_bytes',None),
                          ('sampled_driver_high_water_bytes',math.inf),('sampled_driver_high_water_bytes',-1),
                          ('memory_sample_interval_ms',200),('memory_sample_interval_ms',None),
                          ('memory_sample_count',0),('memory_sample_count',1.5),('memory_sample_count',True),
                          ('memory_sample_source','torch.mps.current_allocated_memory')):
            l,p,host,ref=make_fixture('mps')
            p['core']['H']['context']['0'].update(mps_memory())
            p['core']['H']['context']['0'][field]=bad
            result=J.judge(l,p,host,mps_reference=ref,legacy_report=self.legacy)
            self.assertEqual(result['status'],'INVALID',field)
        for field in mps_memory():
            l,p,host,ref=make_fixture('mps')
            p['core']['A']['context']['0'].update(mps_memory())
            del p['core']['A']['context']['0'][field]
            self.assertEqual(J.judge(l,p,host,mps_reference=ref,legacy_report=self.legacy)['status'],'INVALID')

    def test_CUDA_rejects_MPS_null_and_numeric_dispositions(self):
        for peak in (None,100.):
            self.setUp();ctx=self.p['core']['A']['context']['0'];ctx.update(mps_memory())
            ctx['peak_memory_bytes']=peak
            self.assertEqual(self.run_judge()['status'],'INVALID')

    def test_CUDA_requires_finite_reset_peak_counter(self):
        for field,bad in (('peak_memory_bytes',None),('peak_memory_bytes',math.nan),
                          ('peak_memory_bytes',math.inf),('peak_memory_bytes',-1),
                          ('peak_memory_source','sampled'),('peak_memory_reset',False)):
            self.setUp();self.p['core']['W']['context']['2'][field]=bad
            self.assertEqual(self.run_judge()['status'],'INVALID')
        self.setUp();self.p['core']['W']['context']['2']['peak_memory_bytes']=10**15
        self.assertEqual(self.run_judge()['status'],'COMPLETE')  # no memory performance bar

    def test_MPS_reader_accepts_same_null_memory_disposition(self):
        l,p,host,ref=make_fixture('mps');auth=add_reader(l,p,host)
        for ctx in p['reader']['report']['context'].values():ctx.update(mps_memory())
        result=J.judge(l,p,host,mps_reference=ref,legacy_report=self.legacy,reader_authorization=auth)
        self.assertEqual(result['reader']['outcome'],'R qualifies')

    def test_MPS_explicit_capability_and_public_validator(self):
        self.assertEqual(J.MPS_PEAK_STATUS,'unmeasurable_mps')
        self.assertEqual(J.MPS_MEMORY_SAMPLE_INTERVAL_MS,10)
        self.assertIsNone(J.check_memory(mps_memory(),'mps'))
        with self.assertRaises(J.Invalid):J.check_memory(mps_memory(),'cuda')


def mps_memory():
    return dict(peak_memory_bytes=None,peak_memory_status='unmeasurable_mps',
                sampled_driver_high_water_bytes=123456.,memory_sample_interval_ms=10,memory_sample_count=100,
                memory_sample_source='torch.mps.driver_allocated_memory')


class FileTests(unittest.TestCase):
    def test_duplicate_nonfinite_missing_pin_and_huge_exponent(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as d:
            path=Path(d)/'synthetic.json'
            for text in ('{"0":1,"0":2}','{"v":NaN}','{"v":Infinity}','{"v":1e999}'):
                path.write_text(text,encoding='utf-8')
                with self.assertRaises(J.Invalid):J.load_json(path)
            path.write_text('{}',encoding='utf-8')
            with self.assertRaises(J.Invalid):J.load_json(path,h('wrong'))

    def test_host_sha_parser(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as d:
            path=Path(d)/'sha.txt'
            good=f'{h("H0")}  /synthetic/cm3-h-s012/model_nohud-seed0.pt\n'
            path.write_text(good,encoding='utf-8')
            self.assertEqual(J.load_host_sha(path),{'H/0':{'sha256':h('H0'),'folder':'cm3-h-s012'}})
            for text in (good+good,good.replace('cm3-h','cm3-n'),good.replace('seed0','seed3')):
                path.write_text(text,encoding='utf-8')
                with self.assertRaises(J.Invalid):J.load_host_sha(path)
            for folder in ('cm3-a-s012','interim94-s012'):
                path.write_text(good.replace('cm3-h-s012',folder),encoding='utf-8')
                self.assertEqual(J.load_host_sha(path)['A/0']['folder'],folder)

    def test_F2_cli_attribute_and_index_errors_emit_invalid_reading(self):
        for error in (AttributeError,IndexError):
            with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as d:
                out=Path(d)/'reading.json'
                args=['--launch','unused','--launch-sha256',h('unused'),'--reports','unused',
                      '--checkpoint-sha','unused','--a-report','unused','--phase1-gate','unused',
                      '--phase1-gate-sha256',h('unused'),'--out',str(out)]
                with mock.patch.object(J,'load_json',side_effect=error('synthetic malformed shape')):
                    with contextlib.redirect_stdout(io.StringIO()):rc=J.main(args)
                self.assertEqual(rc,1);self.assertEqual(J.load_json(out)['status'],'INVALID')

    def test_cli_cuda_generated_files_only(self):
        l,p,host,_=make_fixture('cuda')
        for key,path in (('judge',J.__file__),('judge_tests',__file__)):
            l['pins'][key]=J.file_sha(path)
            for r in p['core'].values():r['pins'][key]=l['pins'][key]
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as d:
            root=Path(d);lp=root/'launch.json';rp=root/'packet.json';sp=root/'sha.txt';out=root/'reading.json'
            old=root/'synthetic-legacy.json'
            old.write_text(json.dumps(legacy_report(make_fixture()[1]['core']['A'])),encoding='utf-8')
            l['pins']['legacy_report']=J.file_sha(old)
            for r in p['core'].values():r['pins']['legacy_report']=J.file_sha(old)
            p['phase1_gate']['launch_pins_sha256']=J.digest(l['pins'])
            gate=root/'synthetic-phase1-gate.json'
            gate.write_text(json.dumps(p['phase1_gate']),encoding='utf-8')
            lp.write_text(json.dumps(l),encoding='utf-8');rp.write_text(json.dumps(p),encoding='utf-8')
            sp.write_text(''.join(f'{value["sha256"]}  {value["folder"]}/model_nohud-seed{key[2]}.pt\n'
                                 for key,value in host.items()),encoding='utf-8')
            args=['--launch',str(lp),'--launch-sha256',J.file_sha(lp),'--reports',str(rp),
                  '--checkpoint-sha',str(sp),'--a-report',str(old),'--phase1-gate',str(gate),
                  '--phase1-gate-sha256',J.file_sha(gate),'--out',str(out)]
            with contextlib.redirect_stdout(io.StringIO()):rc=J.main(args)
            self.assertEqual(rc,0,out.read_text());self.assertEqual(J.load_json(out)['selected'],'H')
            bad_gate_args=args[:-2]
            bad_gate_args[bad_gate_args.index('--phase1-gate-sha256')+1]=h('wrong gate pin')
            with contextlib.redirect_stdout(io.StringIO()) as buf:rc=J.main(bad_gate_args)
            self.assertEqual(rc,1);self.assertEqual(json.loads(buf.getvalue())['status'],'INVALID')
            # An incorrect external pin fails before metrics are read.
            args[3]=h('wrong');args=args[:-2]
            with contextlib.redirect_stdout(io.StringIO()) as buf:rc=J.main(args)
            self.assertEqual(rc,1);self.assertEqual(json.loads(buf.getvalue())['status'],'INVALID')

    def test_cli_rejects_synthetic_MPS_reference(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as d:
            p=Path(d)/'synthetic-reference.json';p.write_text(json.dumps(make_fixture()[3]),encoding='utf-8')
            with self.assertRaises(J.Invalid):J.load_json(p,J.MPS_A)


if __name__=='__main__':
    unittest.main(verbosity=2)
