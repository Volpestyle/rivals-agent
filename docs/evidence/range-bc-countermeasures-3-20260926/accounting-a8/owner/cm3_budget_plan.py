"""Writer packaging adapter; cm3_timeouts is the sole timeout formula owner."""
import cm3_timeouts as timing

PHASE1 = ('A-0', 'A-1', 'A-2', 'H-0', 'H-repeat-0')
PHASE2 = ('H-1', 'H-2', 'I-0', 'I-1', 'I-2', 'W-0', 'W-1', 'W-2')
RATE = .00071784
SOURCE_HASH_SECONDS = timing.HASH_SECONDS
DIAGNOSTICS_SECONDS = timing.DIAGNOSTICS_SECONDS
STARTUP_SECONDS = timing.STARTUP_SECONDS
CLEANUP_SECONDS = timing.STOP_SECONDS
OWNER_MARGIN_SECONDS = timing.OWNER_MARGIN_SECONDS
EXTRACTION_HOLD_SECONDS = 2320
VERIFICATION_HOLD_SECONDS = timing.VERIFICATION_SECONDS
PHASE_OVERHEAD_USD = .75
VERIFY_OVERHEAD_USD = .2678032
EXTRACTION_OVERHEAD_USD = .2678032
CONTINGENCY_USD = 1.7136384
FUTURE_NONCOMPUTE_USD = 3.7492448



def derive(smoke):
    measured = timing.measured_seconds(smoke)
    work = timing.work_limits(measured)
    holds = timing.holds(PHASE1 + PHASE2, work, RATE)
    phase1 = sum(holds[k]['total_seconds'] for k in PHASE1)
    phase2 = sum(holds[k]['total_seconds'] for k in PHASE2)
    return {'measured_full_workload_seconds_by_arm': measured,
        'per_fit_source_hash_seconds': SOURCE_HASH_SECONDS,
        'per_fit_diagnostics_seconds': DIAGNOSTICS_SECONDS,
        'attempt_timeout_seconds_by_arm': work,
        'owner_stage_seconds_by_arm': {a: holds[a+'-0']['owner_stage_seconds'] for a in timing.ARMS},
        'task_holds': holds, 'phase1_hold_seconds': phase1, 'phase2_hold_seconds': phase2,
        'matrix_hold_seconds': phase1 + phase2}
