"""Round 3 Amendment 3 judge, stdlib only, written before results (VUH-1346).

Extends judge_cm2's unchanged S/T/F/K mathematics. Does not import training code,
read media/checkpoints, fit anything, or accept a best-epoch/best-seed substitute.

CLI: --launch launch.json --launch-sha256 <LEAD-PINNED raw file SHA256>
     --reports packet.json --checkpoint-sha machine-sha256.txt
     --a-report historical-A-report.json [--mps-a-reference A-reread.json]
     --phase1-gate phase1-gate.json --phase1-gate-sha256 <LEAD-PINNED SHA256>
     [--reader-launch reader-launch.json
      --reader-launch-sha256 <independently pinned SHA256>] [--out reading.json]

Packet v1: {format: 'cm3-reports-v1', status: 'COMPLETE'|'INCOMPLETE',
  interruption: null|string, core: {A: report,H: report,I: report,W: report},
  execution: [{arm,seed,start,end,device,checkpoint_sha256,content_sha256}],
  phase1_gate: {format:'cm3-phase1-gate-v1',status:'PASS',completed:ISO8601,
    launch_pins_sha256:sha,A_control_gate:{status:'PASS',controls:{'0':identity,...}},
    H0_repeat:{status:'PASS',repeat_identical:true,H0:identity,repeat:identity}},
  reader: null|{report,parity}}. identity={checkpoint_sha256,content_sha256}.
execution includes H-repeat seed 0; list order is irrelevant. Phase 1 comprises
A0/A1/A2/H0/H-repeat0; Phase 2 comprises H1/H2/I0/I1/I2/W0/W1/W2. The gate follows
ALL phase-1 completions and precedes EVERY phase-2 start. Within-phase overlap is
permitted. launch.amendment=3 and execution_mode='two-phase' are required. The
base contract_commit remains 7083055; Amendment 3 is an explicit launch field
with contract_sha256 fixed to AMENDMENT3_SHA256 below.
On Modal, device.model and device.instance both denote the one modal:<GPU> class,
not a container host; benchmark_provider='modal'. Software pins remain identical.
Report v1: arm, seeds:[0,1,2], scope:'plumbing', config, cohort,
  device, pins, pairing (new arms only), audit_sha256 (new arms only),
  validation_opened:false, test_opened:false, sealed_opened:false,
  dev_weighted:false, checkpoints:{'0':sha,...}, epochs_log:{'0':[13 logs],...},
  metrics:{dev:{self_fed_checks:{model_nohud:{'0':checks,...}},
    executed_teacher_forced:{model_nohud:{'0':metric,...}},
    self_fed:{model_nohud:{'0':{all:metric},...}}}}, context.
context contains reported-not-judged diagnostics, NOT alternative selection data.
MPS null peak_memory_bytes requires peak_memory_status='unmeasurable_mps', finite
sampled_driver_high_water_bytes, integer memory_sample_count>=1,
memory_sample_interval_ms=10, and
memory_sample_source='torch.mps.driver_allocated_memory'. It is NOT a peak.
CUDA requires a finite peak and peak_memory_source='torch.cuda.max_memory_allocated'
with peak_memory_reset=true. No memory threshold affects S/K/selection.
Metric blocks retain the old window/steps/valid_steps/macro_press_f1_tol keys.
Additional metadata: evaluation={teacher_input:'true_previous',
  teacher_decode:'executor',self_input:'previous_executor',
  self_decode:'executor',live_actions:[...],dev_rows_sha256:sha}.

The test module's make_fixture() is an executable SYNTHETIC schema example.
All pending source/software/cache/proof pins must be supplied by the reviewed
launch manifest; there are no inferred or post-result defaults. Manifest proof
receipts are independently reviewed attestations, not proof that this JSON reader
reran model/cache/label tests. Reports repeat pins and paired manifests exactly.
The external launch pin is a trust anchor; never obtain it from the report itself.
The checkpoint SHA listing is generated on the compute host, not by loading .pt.
Only explicit JSON/text paths are read. JSON is bounded to 32 MiB; hashes stream.
Exit 0: valid complete core decision, 1: INVALID/control stop, 2: INCOMPLETE.
R never replaces the selected no-HUD recipe; reader failure cannot veto core.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from datetime import datetime

CORE = ('H', 'I', 'W')
MPS_PEAK_STATUS = 'unmeasurable_mps'
MPS_MEMORY_SAMPLE_INTERVAL_MS = 10
AMENDMENT3_SHA256 = '7dd39493b754d61df85dc02bc6362f1a53fb1d46f9f9de370b98af03a3b24d54'
SEEDS = ('0', '1', '2')
HEADS = ('held', 'press', 'release', 'camera')
LIVE = ('move_forward', 'move_left', 'move_back', 'move_right', 'jump',
        'web_swing', 'get_over_here', 'amazing_combo', 'spider_power', 'web_cluster')
HUMAN = .6992995601889559
ZERO = 1.2246451263967797
OBSERVABLE = 24556
MPS_A = '8a13a3fd20057a4d9289c732c9897439665f6f7076ca8e5ec9dfb016b28925b9'
SOURCE = 'd23b8b9efee7faeea469d3f10b4bf4ed5d765d00ceded4a2645edf9417a889d7'
SIDECAR = '03bbf9836dc06824d2380bcaa9c096ea2b6f8cea46758c18316bb70b7eb016ba'
WEIGHTS = 'ae1e99fcefd534ed978cdeb8326f08030c96e28b7a81ffcbc98a857c84d14be1'
HISTORICAL_T = (.04474455379689766, .028001206423263373, .032581811203401756)
STEPS = {
 '20260923T051828-422Z-33696-1':'d49224e3c4382a62ebb4c4252bcc5800138782688e1d0f60e03e46ce4b6e7edb',
 '20260923T200129-346Z-33696-6':'fcc9b0443e720648b899453ea3f04f82c0a6dd1735f30a420a36b3675549ba8e',
 '20260924T232304-170Z-12024-1':'8a6c63d4024b13d5b73ab0154f434782e6cfc853d6eaa8291bd9fa8ca8f3b1b1',
 '20260925T021320-371Z-7804-1':'841fe6953cf473e55c6becfe24143259fa48dca639bb9387bc04615edf6ea537',
 '20260925T025230-605Z-7804-2':'84cef39b81ce8a40637bb5cf9766cdfc6f4054b32cda5d94ac1082329434c288',
 '20260923T171533-187Z-33696-5':'dc28b0c1511f7847c8dde08c3e04addce8b57bc6c32cc2873405962d3235559e',
 '20260923T205528-900Z-45572-3':'941950f16edef6a88b14d6bc536e33a66a0e779867fa145c78e7142164e1fd98'}
TRAIN = tuple(STEPS)[:5]
COHORT = [{'session_id': s, 'role': 'train' if s in TRAIN else 'dev',
           'steps_sha256': h} for s, h in STEPS.items()]
COMMON = dict(epochs=13, batch_size=8, stride=64, window=96, min_run=48,
 burn_in=32, optimizer='AdamW', lr=.0003, weight_decay=.0001,
 warmup=500, warmup_capped=True, clip=1., train_fraction=1., max_steps=None,
 regime='normal', lag=0, precision='float32', amp=False, compile=False,
 flash=False, xformers=False, device_fallback=False, reduced_precision=False,
 jitter=0, drq_shift=0, hidden=512, history_width=64,
 normalization={'dim':256,'eps':1e-5,'affine':False},
 loss_multipliers={'held':1.,'press':1.,'release':1.,'camera':.5},
 pos_weight_cap=20, pos_weight_source='unweighted_train',
 self_condition=0, idle_corruption=0, self_roll=0, idle_k=30, idle_weight=.1,
 loss_denominator='original_known_mask', g1_press_source='executed_teacher_forced',
 action_count=15, camera_decode='scalar_median', checkpoint='final')
PIN_KEYS = ('source_cache','sidecar','weights','backbone_config','preprocess',
 'feature_manifest','feature_verification','registry','denylist','software',
 'code_closure','judge','judge_tests','paired_manifest','tag_manifest',
 'canonical_windows','audit','dev_rows','legacy_config','legacy_proof','legacy_report')
# Each named attestation needs a nonempty independently reviewed receipt hash.
# These identifiers deliberately enumerate the contract's failure/mutation cases.
PROOFS = tuple('''legacy_same_backend legacy_mps_blocks paired_tensors
 paired_reversed paired_dummy paired_single_rng_mutation r_preserved_columns
 effective_zero effective_masked_only effective_overlap effective_raw_only_mutation
 normalization_scale frozen_no_grad frozen_eval wrong_weights wrong_dtype
 wrong_shape wrong_channel wrong_pts wrong_row_order duplicate_conflicting_pts
 wrong_source wrong_role corrupt_cache_byte absent_history_invariant absent_no_bias
 w_mask_known_and_content w_cpu_repeat w_eval_no_dropout sf_future_labels
 null_unmapped_key null_held_button null_tap null_release null_wheel null_cancel_mouse
 null_subbin null_unknown null_gap null_29_30_31 null_window_boundary null_burnin
 null_recording_edges null_semantic_only_mutation weighted_handcalc weighted_all_idle
 weighted_one_identity weighted_unchanged_masks weighted_unchanged_posweights
 weighted_unchanged_windows weighted_unchanged_state dev_unweighted
 weighted_denominator_mutation weighted_drop_rows_mutation reader_known_zero_unknown
 reader_permutation reader_missing_fields reader_frame reader_future reader_structural
 reader_native_parity reader_no_ffill reader_wrong_schema reader_wrong_map
 median_float32_boundary executor_live_mask executed_tf_echo s4_observable
 feature_repeat cpu_feature_tolerance initialized_logits_tolerance
 initialized_decisions trained_logits_tolerance trained_decisions smoke_repeat
 backend_determinism no_dev_probe_scores'''.split())


class Invalid(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise Invalid(message)


def number(x, name, low=None, high=None):
    require(type(x) in (int, float) and math.isfinite(x), f'{name}: missing/nonfinite number')
    require(low is None or x >= low, f'{name}: below domain')
    require(high is None or x <= high, f'{name}: above domain')
    return x


def integer(x, name, low=0):
    require(type(x) is int and x >= low, f'{name}: integer required')
    return x


def sha(x, name):
    require(isinstance(x, str) and re.fullmatch('[0-9a-f]{64}', x), f'{name}: SHA256 required')
    return x


def digest(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, separators=(',', ':'),
                                   allow_nan=False).encode()).hexdigest()


def same(x, y, name):
    # JSON equality must not silently consider false == 0 or true == 1.
    require(type(x) is type(y) and x == y, f'{name}: differs from registered/pinned value')
    if isinstance(x, dict):
        for k in x:
            same(x[k], y[k], f'{name}.{k}')
    elif isinstance(x, list):
        for i, (a, b) in enumerate(zip(x, y)):
            same(a, b, f'{name}[{i}]')


def stamp(s):
    require(isinstance(s, str), 'timestamp missing')
    t = datetime.fromisoformat(s.replace('Z', '+00:00'))
    require(t.tzinfo is not None, 'timestamp must have timezone')
    return t


def config(arm):
    return {**COMMON, 'features': 'normalized_impala' if arm == 'I' else 'dinov2_small',
            'history': 'weak' if arm == 'W' else 'absent',
            'prev_dropout': .8 if arm == 'W' else 0., 'reader': False}


def stats(v):
    require(len(v) == 3, 'stats requires three seeds')
    for x in v:
        number(x, 'seed metric')
    return {'values': v, 'mean': sum(v)/3, 'range': max(v)-min(v)}


def seed_checks(c):
    """Unchanged round-2 inequalities, with explicit action/domain validation.

    Null shares fail S4 here; complete report validation rejects null metrics.
    No tolerance/rounding is applied to any pass boundary.
    """
    same(sorted(c['actions']), sorted(LIVE), 'S2 live action identities')
    ratios = [c['actions'][a]['press_ratio'] for a in LIVE]
    for v in [c['hold_onset_recall'], c['press_ratio'], c['camera_mae'], *ratios]:
        if v is not None:
            number(v, 'S metric', 0)
    m, h = c['any_hold_share'], c['human_any_hold_share']
    for v in (m, h):
        if v is not None:
            number(v, 'any hold share', 0, 1)
    z = number(c['zero_motion_camera_mae'], 'zero camera', 0)
    n = sum(v is not None and .5 <= v <= 2 for v in ratios)
    s1 = c['hold_onset_recall'] is not None and c['hold_onset_recall'] >= .05
    s2 = c['press_ratio'] is not None and .5 <= c['press_ratio'] <= 2 and n >= 6
    s3 = c['camera_mae'] is not None and c['camera_mae'] <= .95*z
    s4 = m is not None and h is not None and .5*h <= m <= 1.3*h
    return dict(S1=s1, S2=s2, S3=s3, S4=s4, **{'pass':s1 and s2 and s3 and s4},
                values={**{k:c[k] for k in ('hold_onset_recall','press_ratio','camera_mae',
                        'any_hold_share','human_any_hold_share')},
                        'actions_in_band':n, 'live_actions':10, 'camera_bar':.95*z,
                        'any_hold_excluded_steps':c.get('any_hold_excluded_steps')})


def arm(checks, executed, self_fed):
    """Same public math interface as judge_cm/judge_cm2; no new recipe checks here."""
    for block in (checks, executed, self_fed):
        same(sorted(block), list(SEEDS), 'seed keys')
    seeds = {s:seed_checks(checks[s]) for s in SEEDS}
    return {'seeds':seeds, 'passes_S':sum(x['pass'] for x in seeds.values()) >= 2,
            'T':stats([executed[s]['macro_press_f1_tol'] for s in SEEDS]),
            'F':stats([self_fed[s]['all']['macro_press_f1_tol'] for s in SEEDS]),
            'self_fed_camera_mae':[checks[s]['camera_mae'] for s in SEEDS]}


def select(arms):
    eligible = [a for a in CORE if arms[a]['passes_S'] and arms[a]['K']]
    if not eligible:
        return {'eligible':[], 'selected':None, 'near_tied':[], 'best_mean_F':None,
                'outcome':'Live but less skilled' if any(arms[a]['passes_S'] for a in CORE)
                          else 'Neither works'}
    best = max(eligible, key=lambda a: arms[a]['F']['mean'])
    near = [a for a in eligible if arms[best]['F']['mean']-arms[a]['F']['mean']
            <= arms[best]['F']['range']+arms[a]['F']['range']]
    chosen = near[0]
    title = {'H':'Headline works','I':'Feature control wins','W':'Weak history wins'}[chosen]
    return {'eligible':eligible, 'selected':chosen, 'near_tied':near, 'best_mean_F':best,
            'outcome':'Multiple work' if len(eligible)>1 else title,
            'selected_outcome':title, 'candidate_seed':0,
            'candidate_seed_passes_S':arms[chosen]['seeds']['0']['pass']}


def audit_check(a):
    same(a['format'], 'range-bc-cm3-effective-weight-v1', 'audit format')
    same(a['amendment'], 2, 'audit amendment')
    same(sorted(a['sessions']), sorted(TRAIN), 'audit train sessions')
    same(sorted(a['weight_vectors_sha256']), sorted(TRAIN), 'audit vectors')
    for s in TRAIN:
        sha(a['weight_vectors_sha256'][s], 'weight vector')
    integer(a['windows'], 'audit windows', 1)
    sha(a['canonical_windows_sha256'], 'audit windows hash')
    for group in [*a['sessions'].values(), a['totals']]:
        same(sorted(group), sorted(HEADS), 'audit heads')
        for h, v in group.items():
            u, c = integer(v['U'], 'U'), integer(v['C'], 'C')
            require(c <= u, 'C > U')
            same(v['E_tenths'], 10*u-9*c, 'exact E_tenths')
            number(v['E'], 'E', 0)
            require(v['E'] == v['E_tenths']/10, 'E inconsistent')
    for h in HEADS:
        for k in ('U','C','E_tenths'):
            same(a['totals'][h][k], sum(a['sessions'][s][h][k] for s in TRAIN), 'audit total')
    active = any(a['totals'][h]['C'] > 0 for h in HEADS)
    same(a['weighting_has_scored_effect'], active, 'audit effect')
    same(a['disposition'], 'scored idle weight reduced' if active else 'no scored idle-weight effect',
         'audit disposition')
    same(a['sha256'], digest({k:v for k,v in a.items() if k!='sha256'}), 'audit digest')
    return {**a, 'per_head_effect':{h:a['totals'][h]['C']>0 for h in HEADS},
            'selection_effect':'none; H/I/W always run', 'idle_contrast':'untested'}


def check_launch(l):
    same(l['format'], 'cm3-launch-v1', 'launch format')
    same(l['contract_commit'], '7083055', 'contract commit')
    same(l['amendment'],3,'launch amendment')
    same(l['contract_sha256'],AMENDMENT3_SHA256,'Amendment 3 contract pin')
    same(l['execution_mode'],'two-phase','execution mode')
    same(l['arms'], list(CORE), 'registered matrix/priority')
    same(l['seeds'], [0,1,2], 'launch seeds')
    same(l['cohort'], COHORT, 'launch cohort')
    same(l['live_actions'], list(LIVE), 'live actions')
    same(l['sidecar_sessions'], list(TRAIN), 'train-only sidecars')
    d = l['device']
    require(d['backend'] in ('mps','cuda'), 'unsupported backend')
    require(d['model'] in (('M5 Max',) if d['backend']=='mps' else
                          ('AWS L40S','AWS L4','modal:L4','modal:A10','modal:L40S')),
            'unsupported hardware model')
    if d['model'].startswith('modal:'):
        same(l['benchmark_provider'],'modal','Modal benchmark choice')
        same(d['instance'],d['model'],'Modal instance means class, not unique host')
    require(bool(d['instance']) and bool(d['software_description']), 'missing hardware/software identity')
    pins = l['pins']
    same(sorted(pins), sorted(PIN_KEYS), 'launch pins')
    for k,v in pins.items():
        if k=='code_closure':
            require(isinstance(v,dict) and bool(v), 'code closure missing')
            for path,h in v.items():
                require(bool(path), 'empty source path')
                sha(h, path)
        else:
            sha(v,k)
    for key,value in (('source_cache',SOURCE),('sidecar',SIDECAR),('weights',WEIGHTS)):
        same(pins[key],value,key)
    same(l['backbone'], {'revision':'ed25f3a31f01632728cabb09d1542f84ab7b0056',
         'size':88249960,'dim':6528,'dtype':'<f4','pooling':'CLS+4x4-grid',
         'preprocess':'registered-section-5','frozen':True}, 'backbone contract')
    for a in CORE:
        same(l['configs'][a],config(a),a+' config')
    same(sorted(l['configs']), sorted(CORE), 'config arms')
    # A config is a separately reviewed legacy object, NOT the new-arm config.
    same(digest(l['a_config']),pins['legacy_config'],'legacy A config hash')
    same(l['a_kind'], 'historical-reread' if d['backend']=='mps' else 'fresh-same-hardware', 'A branch')
    p = l['proofs']
    same(sorted(p), sorted(PROOFS), 'proof checklist')
    for name, receipt in p.items():
        same(receipt['passed'], True, name)
        sha(receipt['receipt_sha256'],name+' receipt')
        same(receipt['reviewed'],True,name+' independent review')
        same(receipt['dev_scores_produced'],False,name+' dev leakage')
    t = l['timeline']
    order = ('cloud_benchmark','device_choice','code_judge_freeze','identities_verified',
             'numerical_probe_start','numerical_proof','smoke_start','smoke_proof','audit_complete','budget_approved',
             'full_cache_start','full_cache_verified','manifest_frozen','launch_approved')
    ts = [stamp(t[k]) for k in order]
    require(all(a<=b for a,b in zip(ts,ts[1:])), 'preflight/approval chronology')
    for key in ('benchmark_receipt','device_receipt','budget_receipt','launch_receipt'):
        sha(l[key],key)
    for name,r in p.items():
        rt = stamp(r['completed'])
        lower = 'code_judge_freeze'
        if name in ('feature_repeat','cpu_feature_tolerance','initialized_logits_tolerance','initialized_decisions'):
            lower = 'numerical_probe_start'
        elif name in ('trained_logits_tolerance','trained_decisions','smoke_repeat'):
            lower = 'smoke_start'
        require(stamp(t[lower]) <= rt <= stamp(t['budget_approved']), name+' proof too late/early')
        same(r['code_closure_sha256'],digest(pins['code_closure']),name+' proof code closure')
    b = l['budget']
    same(b['core_hours_cap'],16,'core cap')
    number(b['forecast_hours_including_spent'], 'forecast', 0, 16)
    number(b['spent_preflight_hours'],'spent',0,b['forecast_hours_including_spent'])
    same(b['all_epochs_evaluations_controls_repeat_hashing_included'],True,'budget coverage')
    if d['backend']=='cuda':
        number(b['cloud_dollar_cap'],'cloud cap',.01)
        number(b['forecast_dollars'],'cloud forecast',0,b['cloud_dollar_cap'])
    audit_check(l['audit'])
    same(l['audit']['sha256'],pins['audit'],'audit pin')
    same(l['audit']['canonical_windows_sha256'],pins['canonical_windows'],'window audit pin')
    same(digest(l['pairing']),pins['paired_manifest'],'paired pin')
    same(digest(l['tags']),pins['tag_manifest'],'tag pin')
    require(bool(l['tags']), 'missing concrete module/tag map')
    require(set(('init/core','init/projector/global','init/projector/crosshair',
                 'init/impala/global','init/impala/crosshair','init/history')) <= set(l['tags'].values()),
            'missing registered initialization stream')
    require(any(tag.startswith('init/head/') for tag in l['tags'].values()),'missing output head streams')
    for module,tag in l['tags'].items():
        require(isinstance(module,str) and isinstance(tag,str) and
                (tag in ('init/core','init/projector/global','init/projector/crosshair',
                         'init/impala/global','init/impala/crosshair','init/history') or
                 tag=='init/head/'+module), 'unregistered initialization tag')
    same(sorted(l['pairing']),sorted(CORE),'pairing arms')
    for a in CORE:
        same(sorted(l['pairing'][a]),list(SEEDS),'pairing seeds')
        for s in SEEDS:
            v=l['pairing'][a][s]
            require(len(v['window_orders'])==13,'13 epoch orders required')
            for h in v['window_orders']:
                sha(h,'window order')
            for field in ('core','heads','initial_tensor_manifest'):
                sha(v[field],'initial '+field)
            for field in ('core','heads','window_orders'):
                same(v[field],l['pairing']['H'][s][field],'paired '+field)
            if a in ('H','W'):
                sha(v['projectors'],'projectors')
                same(v['projectors'],l['pairing']['H'][s]['projectors'],'paired projectors')
    return l


def metric_blocks(r):
    m=r['metrics']['dev']
    return (m['self_fed_checks']['model_nohud'],
            m['executed_teacher_forced']['model_nohud'],m['self_fed']['model_nohud'])


def check_memory(ctx,backend):
    """Public report validator; raises Invalid (or KeyError for absent fields).

    MPS_PEAK_STATUS and MPS_MEMORY_SAMPLE_INTERVAL_MS are explicit capabilities
    for an externally pinned A3 runner; this helper performs no measurements.
    """
    require(backend in ('mps','cuda'),'unsupported memory-report backend')
    peak=ctx['peak_memory_bytes']
    if peak is None:
        same(backend,'mps','null peak is MPS-only')
        same(ctx['peak_memory_status'],MPS_PEAK_STATUS,'MPS null disposition')
        number(ctx['sampled_driver_high_water_bytes'],'sampled driver high-water bytes',0)
        same(ctx['memory_sample_source'],'torch.mps.driver_allocated_memory','MPS sampling source')
        same(ctx['memory_sample_interval_ms'],MPS_MEMORY_SAMPLE_INTERVAL_MS,'fixed MPS sampling interval')
        integer(ctx['memory_sample_count'],'observed MPS memory samples',1)
    else:
        number(peak,'peak_memory_bytes',0)
        require(ctx.get('peak_memory_status')!=MPS_PEAK_STATUS,'numeric peak contradicts MPS null disposition')
    if backend=='cuda':
        same(ctx['peak_memory_source'],'torch.cuda.max_memory_allocated','CUDA peak source')
        same(ctx['peak_memory_reset'],True,'CUDA peak counter reset')


def check_report(r,a,l,host_hashes):
    same(r['arm'],a,'report arm')
    same(r['seeds'],[0,1,2],a+' seeds')
    same(r['scope'],'plumbing',a+' scope')
    same(r['cohort'],COHORT,a+' cohort')
    same(r['device'],l['device'],a+' hardware')
    same(r['pins'],l['pins'],a+' pins')
    same(r['config'],l['a_config'] if a=='A' else config(a),a+' config')
    for flag in ('validation_opened','test_opened','sealed_opened','dev_weighted'):
        same(r[flag],False,a+' '+flag)
    e=r['evaluation']
    same(e,dict(teacher_input='true_previous',teacher_decode='executor',
               self_input='previous_executor',self_decode='executor',live_actions=list(LIVE),
               dev_rows_sha256=l['pins']['dev_rows']),a+' evaluation contract')
    if a!='A':
        same(r['pairing'],l['pairing'][a],a+' initial/tag/order manifest')
        same(r['audit_sha256'],l['pins']['audit'],a+' audit')
    else:
        same(r['control_kind'],l['a_kind'],'A lineage')
    same(sorted(r['checkpoints']),list(SEEDS),a+' checkpoints')
    same(sorted(r['epochs_log']),list(SEEDS),a+' epoch seeds')
    checks,tf,sf=metric_blocks(r)
    for block in (checks,tf,sf):
        same(sorted(block),list(SEEDS),a+' metric seeds')
    for s in SEEDS:
        sha(r['checkpoints'][s],a+' checkpoint')
        host=host_hashes[a+'/'+s]
        same(r['checkpoints'][s],host['sha256'],a+' compute-host SHA256')
        folder=('interim94-s012' if l['device']['backend']=='mps' else 'cm3-a-s012') if a=='A' else 'cm3-'+a.lower()+'-s012'
        same(host['folder'],folder,a+' compute-host folder')
        c=checks[s]
        same(c['human_any_hold_share'],HUMAN,'human baseline')
        same(c['zero_motion_camera_mae'],ZERO,'zero baseline')
        same(c['any_hold_observable_steps'],OBSERVABLE,'observable rows')
        same(c['any_hold_excluded_steps'],0,'excluded rows')
        same(c['steps'],OBSERVABLE,'S steps')
        for k in ('hold_onset_recall','press_ratio','camera_mae','any_hold_share'):
            number(c[k],a+' '+s+' '+k,0,1 if k in ('hold_onset_recall','any_hold_share') else None)
        for act in LIVE:
            number(c['actions'][act]['press_ratio'],'action ratio',0)
        seed_checks(c)
        for metric,late in ((tf[s],0),(sf[s]['all'],1)):
            same(metric['window'],{'early':1,'late':late,'self_fed':True},'executed TF/SF window')
            same(metric['steps'],OBSERVABLE,'metric rows')
            same(metric['valid_steps'],OBSERVABLE,'valid rows')
            number(metric['macro_press_f1_tol'],'macro press F1',0,1)
        log=r['epochs_log'][s]
        require(len(log)==13,'13 complete epochs required')
        same([v['epoch'] for v in log],list(range(13)),'epoch identities')
        for v in log:
            number(v['train_loss'],'train loss',0)
            number(v['dev']['total'],'dev loss',0)
        ctx=r['context'][s]
        number(ctx['wall_seconds'],'wall_seconds',0)
        check_memory(ctx,l['device']['backend'])
        for key in ('held_change_f1','raw_teacher_forced','executed_counts'):
            require(key in ctx and ctx[key] is not None,'missing reported diagnostic '+key)
        if a!='A':
            number(ctx['unweighted_train_loss'],'unweighted train diagnostic',0)
            for key in ('normalized_feature_diagnostics','gate_diagnostics'):
                require(key in ctx and ctx[key] is not None,'missing reported diagnostic '+key)
    return arm(checks,tf,sf)


def check_execution(p,l):
    phase1={('A',s) for s in SEEDS}|{('H','0'),('H-repeat','0')}
    phase2={('H','1'),('H','2')}|{(a,s) for a in ('I','W') for s in SEEDS}
    ex=p['execution']
    identities=[(r['arm'],str(r['seed'])) for r in ex]
    same(sorted(identities),sorted(phase1|phase2),'exact two-phase matrix, no duplicates')
    by_id=dict(zip(identities,ex))
    gate=p['phase1_gate']
    same(gate['format'],'cm3-phase1-gate-v1','phase-1 gate format')
    same(gate['status'],'PASS','phase-1 gate status')
    same(gate['launch_pins_sha256'],digest(l['pins']),'phase-1 launch binding')
    control=gate['A_control_gate'];repeat=gate['H0_repeat']
    same(control['status'],'PASS','A_control_gate status')
    same(sorted(control['controls']),list(SEEDS),'phase-1 control seeds')
    same(repeat['status'],'PASS','H0_repeat status')
    same(repeat['repeat_identical'],True,'H0_repeat byte identity')
    def identity(r):
        return {k:r[k] for k in ('checkpoint_sha256','content_sha256')}
    for s in SEEDS:
        same(control['controls'][s],identity(by_id['A',s]),'A_control_gate bound output')
    same(repeat['H0'],identity(by_id['H','0']),'H0_repeat original output')
    same(repeat['repeat'],identity(by_id['H-repeat','0']),'H0_repeat repeat output')
    gate_time=stamp(gate['completed'])
    approved=stamp(l['timeline']['launch_approved'])
    require(approved<=gate_time,'phase-1 gate before launch approval')
    seconds=l['budget']['spent_preflight_hours']*3600
    for r in ex:
        same(r['device'],l['device'],'execution hardware')
        start,end=stamp(r['start']),stamp(r['end'])
        require(approved<=start<=end,'fit before approval or inverted interval')
        key=(r['arm'],str(r['seed']))
        if key in phase1:
            require(end<=gate_time,'phase-1 gate precedes a phase-1 completion')
        else:
            require(gate_time<=start,'phase-2 fit starts before phase-1 gate')
        # Sum container compute even where intervals overlap; never use makespan.
        seconds+=(end-start).total_seconds()
        a='H' if r['arm']=='H-repeat' else r['arm']
        s=str(r['seed'])
        same(r['checkpoint_sha256'],p['core'][a]['checkpoints'][s],'execution checkpoint')
        sha(r['content_sha256'],'non-timing metric/loss/decision digest')
    same(identity(by_id['H','0']),identity(by_id['H-repeat','0']),'H0 exact full repeat')
    # elapsed_compute_seconds also includes full extraction/hash/reference work.
    number(p['elapsed_compute_seconds'],'elapsed compute',seconds)
    return p['elapsed_compute_seconds']<=16*3600


def check_mps_reference(r, reference, legacy_report):
    require(reference is not None,'MPS requires the hash-verified historical A reread')
    eq=reference['equal']
    require(bool(eq) and all(type(v) is bool and v for v in eq.values()),'historical A identity failed')
    c,t,_=metric_blocks(r)
    same(c,reference['self_fed_checks']['model_nohud'],'MPS A stored checks')
    same(t,reference['executed_teacher_forced']['model_nohud'],'MPS A stored executed TF')
    require(legacy_report is not None,'MPS requires the pinned historical report, not new-arm config checks')
    same(metric_blocks(r)[2],legacy_report['metrics']['dev']['self_fed']['model_nohud'],
         'MPS A stored self-fed blocks')
    for s in SEEDS:
        key='model_nohud-seed'+s+'.pt'
        same(r['checkpoints'][s],legacy_report['checkpoints'][key],'MPS A checkpoint')
        same(r['epochs_log'][s],legacy_report['epochs_log'][key],'MPS A original epoch logs')


def check_cuda_reference(r, legacy_report):
    require(legacy_report is not None,'CUDA requires pinned legacy report for historical checkpoint exclusion')
    for s in SEEDS:
        sha(legacy_report['checkpoints']['model_nohud-seed'+s+'.pt'],'historical A checkpoint')
    historical = {sha(v,'historical checkpoint') for v in legacy_report['checkpoints'].values()}
    require(not historical.intersection(r['checkpoints'].values()),'CUDA A reuses a historical MPS checkpoint')
    t=metric_blocks(r)[1]
    require(tuple(t[s]['macro_press_f1_tol'] for s in SEEDS)!=HISTORICAL_T,
            'CUDA A T tuple equals historical MPS A')


def reader_parity(p, *, precheck=False):
    """Receipts carry per-field denominators, not only an aggregate PASS string."""
    same(p['fresh_authorized'],True,'fresh reader sources')
    same(p['validation_or_sealed'],False,'reader sealed sources')
    same(p['blinded_labels'],True,'reader labels')
    for k in ('labels_sha256','reader_sha256','schema_sha256','adapter_sha256','review_sha256'):
        sha(p[k],k)
    for key in ('known_zero_unknown_mutation','wrong_slot_mutation','wrong_layout_mutation'):
        same(p[key],True,'reader mutation '+key)
    same(sorted(p['layouts']),['mnk'] if precheck else ['mnk','pad'],'reader parity layouts')
    if precheck:
        same(p['initial_sample_per_session'],{s:40 for s in TRAIN},'reader initial sampling')
        integer(p['additional_predrawn_frames'],'reader additional sample')
        require(p['additional_predrawn_frames']<=200,'reader sample exceeds registered cap')
        same(p['sample_seed'],20260928,'reader sample seed')
        same(p['first_coverage_stop'],True,'reader rare-state sampling stop')
        same(p['all_inspected_retained'],True,'reader retained inspected frames')
    else:
        same(p['previous_parity_sources_reused'],False,'fresh parity source exclusion')
    require(bool(p['stratified_error_report']),'reader per-session/field/stratum audit missing')
    fields=('webs','hp','max_hp','ult_ready','ult_charge',*[a+'_'+q for a in
            ('swing','get_over_here','amazing_combo') for q in ('ready','charges','cooldown')])
    for layout, rows in p['layouts'].items():
        same(sorted(rows),sorted(fields),'all 14 reader fields')
        same(sorted(p['supported_fields'][layout]),
             sorted(name for name,v in rows.items() if not v['structurally_unavailable']),
             'reader supported field contract')
        # Required visible quantities cannot all be waived as unavailable.
        require(set(('webs','hp','max_hp','ult_ready','ult_charge','swing_ready',
                     'get_over_here_ready','amazing_combo_ready')) <= set(p['supported_fields'][layout]),
                'vacuous reader coverage')
        for name,v in rows.items():
            require(type(v['structurally_unavailable']) is bool,'reader availability flag')
            if v['structurally_unavailable']:
                same(v['declared_before_labels'],True,'structural declaration')
                same(v['known'],0,'unavailable known')
                continue
            n=integer(v['legible'],name+' legible',20)
            correct=integer(v['correct_known'],name+' correct')
            require(correct<=n and correct/n>=.95,'reader known accuracy/unknown share')
            same(v['known_wrong'],0,'reader contradiction')
            same(v['unreadable_known'],0,'unsafe non-abstention')
            if name=='ult_ready' or name.endswith('_ready'):
                integer(v['true_examples'],name+' true',5)
                integer(v['false_examples'],name+' false',5)
            if name=='webs':
                integer(v['low_resource_examples'],'low web',20)
            if name.endswith(('_charges','_cooldown')):
                integer(v['low_resource_examples'],'spent/running',20)
            if name=='ult_charge':
                same(v['absolute_tolerance'],.05,'ult tolerance')
        number(p['ready_occluded_share'][layout],'ready occlusion share',0,1)
        integer(p['ready_eligible_denominator'][layout],'ready eligible denominator',20)
    return True


def judge_reader(reader, authorization, selected, arms, l, host_hashes):
    if selected is None:
        return {'outcome':'R not run','status':'NOT RUN','reason':'no selected eligible core recipe'}
    if reader is None:
        return {'outcome':'R not run','status':'NOT RUN','reason':'no conditional reader packet supplied'}
    try:
        require(authorization is not None,'missing separately pinned reader launch')
        same(authorization['selected'],selected,'R selected recipe')
        same(authorization['device'],l['device'],'R hardware')
        same(authorization['scope'],'train-only-precheck','reader scope')
        same(authorization['copied_initialization_proof'],True,'R copied columns')
        same(authorization['smoke_updates'],32,'R smoke updates')
        same(authorization['dev_scores_in_smoke'],False,'R smoke dev leakage')
        number(authorization['forecast_hours_including_precheck'],'R forecast',0,6)
        for k in ('initialization_sha256','schema_sha256','adapter_sha256','cache_sha256',
                  'cache_verification_sha256','budget_receipt','launch_receipt'):
            sha(authorization[k],k)
        times=[stamp(authorization[k]) for k in ('core_judged','precheck_passed','smoke_passed',
               'budget_approved','full_cache_start','cache_verified','launch_approved','fit_start')]
        require(all(a<=b for a,b in zip(times,times[1:])),'R chronology')
        reader_parity(authorization['precheck'],precheck=True)
        r=reader['report']
        same(r['arm'],'R','reader arm')
        same(r['base_arm'],selected,'R base arm')
        expected={**config(selected),'reader':True,'reader_dim':28,'reader_width':64}
        same(r['config'],expected,'R exact clone')
        same(r['reader_authorization_sha256'],digest(authorization),'R launch binding')
        # Validate common report fields without applying the legacy A/new core exception.
        proxy=dict(r,arm=selected,config=config(selected),pairing=l['pairing'][selected])
        hashes=dict(host_hashes)
        for s in SEEDS:
            same(host_hashes['R/'+s]['folder'],'cm3-r-s012','R compute-host folder')
            hashes[selected+'/'+s]={**host_hashes['R/'+s],'folder':'cm3-'+selected.lower()+'-s012'}
        result=check_report(proxy,selected,l,hashes)
        same(r['copied_initialization_sha256'],authorization['initialization_sha256'],'R copied manifest')
        number(reader['elapsed_compute_seconds'],'R elapsed',0,21600)
        reader_parity(reader['parity'])
        for k in ('schema_sha256','adapter_sha256','reader_sha256'):
            same(reader['parity'][k],authorization[k],'reader parity identity')
            same(authorization['precheck'][k],authorization[k],'reader precheck identity')
        same(reader['parity']['supported_fields'],authorization['supported_fields'],
             'reader predeclared supported fields')
        same(authorization['precheck']['supported_fields']['mnk'],authorization['supported_fields']['mnk'],
             'reader precheck supported fields')
        require('unknown_interventions' in reader and bool(reader['unknown_interventions']),
                'missing full-vector/per-field unknown diagnostics')
        t=arms['A']['T']; rt=result['T']; f=arms[selected]['F']; rf=result['F']
        result['K_bar']=t['mean']-(t['range']+rt['range'])
        result['K']=rt['mean']>=result['K_bar']
        result['F_bar']=f['mean']-(f['range']+rf['range'])
        result['noninferior']=rf['mean']>=result['F_bar']
        result['outcome']='R qualifies' if result['passes_S'] and result['K'] and result['noninferior'] else 'R fails'
        result['real_fit_effect']='none; selected no-HUD recipe retained'
        return result
    except (Invalid,KeyError,TypeError,ValueError,OverflowError,AttributeError,IndexError) as exc:
        return {'outcome':'R fails / undecided','reason':str(exc),
                'real_fit_effect':'none; selected no-HUD recipe retained'}


def judge(launch,packet,host_hashes,*,mps_reference=None,legacy_report=None,reader_authorization=None):
    """Pure JSON evaluator; caller authenticates launch/reference bytes (CLI does)."""
    out={'status':'INVALID','outcome':'Invalid / sanity failure','selected':None,
         'check_failures':[], 'report_checks':{}, 'persistence_camera':.418,'ar2_camera':.376}
    try:
        l=check_launch(launch)
        same(packet['format'],'cm3-reports-v1','packet format')
        require(packet['status'] in ('COMPLETE','INCOMPLETE'),'unknown queue status')
        if packet['status']=='INCOMPLETE':
            require(isinstance(packet['interruption'],str) and bool(packet['interruption']), 'interruption reason required')
            out.update(status='INCOMPLETE',outcome='INCOMPLETE',reason=packet['interruption'])
            return out
        same(packet['interruption'],None,'complete queue interruption')
        same(sorted(packet['core']),sorted(('A',*CORE)),'exact core plus A')
        arms={}
        for a in ('A',*CORE):
            try:
                arms[a]=check_report(packet['core'][a],a,l,host_hashes)
                out['report_checks'][a]='PASS'
            except (Invalid,KeyError,TypeError,ValueError,OverflowError,AttributeError,IndexError) as exc:
                out['report_checks'][a]='FAIL: '+str(exc)
                out['check_failures'].append(a+': '+str(exc))
        require(not out['check_failures'],'per-report checks failed')
        if not check_execution(packet,l):
            out.update(status='INCOMPLETE',outcome='INCOMPLETE',reason='16-hour compute cap exceeded')
            return out
        if l['device']['backend']=='mps':
            check_mps_reference(packet['core']['A'],mps_reference,legacy_report)
        else:
            check_cuda_reference(packet['core']['A'],legacy_report)
        out['arms']=arms
        if arms['A']['passes_S']:
            out['outcome']='Changed control regime' if l['device']['backend']=='cuda' else 'Invalid / sanity failure'
            raise Invalid('A passes S; stop for control review, no countermeasure selection')
        ta=arms['A']['T']
        for a in CORE:
            v=arms[a]
            v['K_bar']=ta['mean']-(ta['range']+v['T']['range'])
            v['K']=v['T']['mean']>=v['K_bar']
        choice=select(arms)
        out.update(choice,status='COMPLETE',effective_weight_audit=audit_check(l['audit']),
                   a_reference=l['a_kind'], a_mean_T_minus_historical=ta['mean']-sum(HISTORICAL_T)/3)
        out['contrasts']={}
        for other in ('I','W'):
            out['contrasts']['H-'+other]={
                'T':[x-y for x,y in zip(arms['H']['T']['values'],arms[other]['T']['values'])],
                'F':[x-y for x,y in zip(arms['H']['F']['values'],arms[other]['F']['values'])],
                'S_measures':{s:{k:arms['H']['seeds'][s]['values'][k]-arms[other]['seeds'][s]['values'][k]
                    for k in ('hold_onset_recall','press_ratio','actions_in_band','camera_mae','any_hold_share')}
                    for s in SEEDS},
                'beyond_observed_F_spread':abs(arms['H']['F']['mean']-arms[other]['F']['mean']) >
                                          arms['H']['F']['range']+arms[other]['F']['range']}
        out['context']={a:{s:{**r['context'][s], 'argmin_epoch':min(r['epochs_log'][s],
                         key=lambda v:(v['dev']['total'],v['epoch']))['epoch']+1,
                         'final_dev_total':r['epochs_log'][s][-1]['dev']['total'],
                         'camera_vs_persistence':arms[a]['self_fed_camera_mae'][int(s)]/.418,
                         'camera_vs_ar2':arms[a]['self_fed_camera_mae'][int(s)]/.376}
                       for s in SEEDS} for a,r in packet['core'].items()}
        out['reader']=judge_reader(packet['reader'],reader_authorization,choice['selected'],arms,l,host_hashes)
        out['meaning']='Draft selected no-HUD recipe for a separately reviewed real fit' if choice['selected'] else 'No real fit'
        out['idle_disposition']="idle-target imbalance: not a factor at this cohort's idle rate (0.51% of rows at k=30); contrast untested"
        out['limitations']='Scope/budget disposition, not causal evidence; S/K are feasibility gates, not policy acceptance.'
    except (Invalid,KeyError,TypeError,ValueError,OverflowError,AttributeError,IndexError) as exc:
        out['status']='INVALID'
        out['selected']=None
        if out['outcome']!='Changed control regime':
            out['outcome']='Invalid / sanity failure'
        for key in ('candidate_seed','candidate_seed_passes_S','eligible','near_tied',
                    'selected_outcome','best_mean_F','meaning'):
            out.pop(key,None)
        out['check_failures'].append(str(exc))
    return out


def file_sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()


def load_json(path,expected=None):
    require(Path(path).stat().st_size<=32*1024*1024,'JSON exceeds 32 MiB bound')
    if expected is not None:
        sha(expected,'external pin')
        same(file_sha(path),expected,'file hash '+str(path))
    def pairs(items):
        d={}
        for k,v in items:
            require(k not in d,'duplicate JSON key: '+k)
            d[k]=v
        return d
    def constant(x):
        raise Invalid('nonfinite JSON constant '+x)
    with open(path,encoding='utf-8') as f:
        value=json.load(f,object_pairs_hook=pairs,parse_constant=constant)
    def finite(x):
        if isinstance(x,float):
            number(x,'JSON float')
        elif isinstance(x,dict):
            for v in x.values(): finite(v)
        elif isinstance(x,list):
            for v in x: finite(v)
    finite(value)
    return value


def load_host_sha(path):
    """shasum lines: <sha> [*/path/]cm3-h-s012/model_nohud-seed0.pt.

    A is cm3-a-s012 on CUDA or interim94-s012 on MPS; R is cm3-r-s012.
    Returns {arm/seed: {sha256, folder}}; retains A's provenance folder.
    Never dereferences these paths. Reject conflicting/duplicate/unknown entries.
    """
    require(Path(path).stat().st_size<=65536,'SHA listing too large')
    result={}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        m=re.fullmatch(r'([0-9a-f]{64})\s+\*?(?:.*/)?(cm3-[hiwar]-s012|interim94-s012)/model_nohud-seed([012])\.pt',line)
        require(m is not None,'unrecognized SHA listing line')
        h,folder,s=m.groups()
        a='A' if folder=='interim94-s012' else folder[4].upper()
        key=a+'/'+s
        require(key not in result,'duplicate checkpoint hash')
        result[key]={'sha256':h,'folder':folder}
    return result


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    for flag in ('launch','launch-sha256','reports','checkpoint-sha','a-report',
                 'phase1-gate','phase1-gate-sha256'):
        ap.add_argument('--'+flag,required=True)
    for flag in ('mps-a-reference','reader-launch','reader-launch-sha256','out'):
        ap.add_argument('--'+flag)
    x=ap.parse_args(argv)
    try:
        launch=load_json(x.launch,x.launch_sha256)
        same(launch['pins']['judge'],file_sha(__file__),'running judge pin')
        same(launch['pins']['judge_tests'],file_sha(Path(__file__).with_name('test_judge_cm3-a3.py')),
             'frozen synthetic tests pin')
        packet=load_json(x.reports)
        if packet['status']=='COMPLETE':
            same(packet['phase1_gate'],load_json(x.phase1_gate,x.phase1_gate_sha256),
                 'externally pinned phase-1 gate')
        reference=load_json(x.mps_a_reference,MPS_A) if x.mps_a_reference else None
        legacy=load_json(x.a_report,launch['pins']['legacy_report']) if x.a_report else None
        require(bool(x.reader_launch)==bool(x.reader_launch_sha256),'reader launch and external pin required together')
        reader=load_json(x.reader_launch,x.reader_launch_sha256) if x.reader_launch else None
        result=judge(launch,packet,load_host_sha(x.checkpoint_sha),mps_reference=reference,
                     legacy_report=legacy,reader_authorization=reader)
        result['input_sha256']={k:file_sha(v) for k,v in vars(x).items()
            if k in ('launch','reports','checkpoint_sha','mps_a_reference','a_report','reader_launch') and v}
        if packet['status']=='COMPLETE':
            result['input_sha256']['phase1_gate']=file_sha(x.phase1_gate)
    except (Invalid,KeyError,TypeError,ValueError,OSError,OverflowError,AttributeError,IndexError) as exc:
        result={'status':'INVALID','outcome':'Invalid / sanity failure','selected':None,'check_failures':[str(exc)]}
    text=json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n'
    if x.out:
        with open(x.out,'x',encoding='utf-8',newline='\n') as f: f.write(text)
    print(text,end='')
    return {'COMPLETE':0,'INVALID':1,'INCOMPLETE':2}[result['status']]


if __name__=='__main__':
    sys.exit(main())
