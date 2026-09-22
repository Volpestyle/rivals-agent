"""Read the finalized diagnostic logs; no model, media, capture or input imports."""
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / 'data/l1/range-request-diagnostic-20260922-1'
PRE = ROOT / 'data/runtime/range-request-preflight-20260922'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def summarize():
    meta = read(RUN / 'meta.json')
    rows = [json.loads(line) for line in (RUN / 'frames.jsonl').read_text().splitlines()]
    decisions = [row['decision_trace'] for row in rows if 'decision_trace' in row]
    ids = [d['decision_id'] for d in decisions]
    assert len(ids) == len(set(ids))
    steps = [r for r in rows if r.get('range_skill_trace', {}).get('event') == 'step']
    accepted = [r for r in steps if r['range_skill_trace']['accepted']]
    lt = [r for r in steps if r.get('pad', {}).get('lt') and r.get('send_result', {}).get('status') == 'returned']
    terminal = [r for r in rows if r.get('type') == 'executor_release']
    assert terminal == meta['executor_events']
    receipt = meta['range_policy']
    assert receipt['source_identity'] == read(PRE / 'source-identity.json')
    assert receipt['runtime'] == read(PRE / 'runtime-identity.json')
    assert receipt['deployment'] == read(PRE / 'deployment-binding.json')
    assert receipt['checkpoint_sha256'] == sha(ROOT / 'data/diagnostics/range-request-human-fit-20260922/run-1/model.pt')
    owned = {r['range_skill_trace']['pulse_decision_id'] for r in rows if r.get('range_skill_trace', {}).get('pulse_decision_id') is not None}
    report = {
        'scope': 'read_only_logged_execution_accounting_not_gameplay_scoring',
        'run': RUN.name,
        'source_sha256': {str(p.relative_to(ROOT)): sha(p) for p in [RUN / 'meta.json', RUN / 'frames.jsonl', PRE / 'deployment-binding.json', PRE / 'binding-consumed.json']},
        'receipt_matches_issued_source_runtime_binding_checkpoint': True,
        'origin': receipt['origin'],
        'semantic_revision': receipt['source_identity']['semantic_revision'],
        'stop': meta['stop'],
        'learned_phase_s': meta['seconds'],
        'decision_counter': meta['decisions'],
        'persisted_decisions': len(decisions),
        'missing_decision_ids': sorted(set(range(1, meta['decisions'] + 1)) - set(ids)),
        'persisted_decision_reasons': dict(Counter(d['reason'] for d in decisions)),
        'persisted_proposals': dict(Counter(d['web_cluster_request'] for d in decisions if d.get('web_cluster_request') is not None)),
        'persisted_step_acceptance_ids': [r['range_skill_trace']['decision_id'] for r in accepted],
        'observed_owned_pulse_ids': sorted(owned),
        'returned_lt_calls': [{'step': r['range_skill_trace'], 'send': r['send_result']} for r in lt],
        'returned_rt_calls': sum(bool(r.get('pad', {}).get('rt')) and r.get('send_result', {}).get('status') == 'returned' for r in rows),
        'terminal_events': terminal,
        'run_statistics': {k: meta[k] for k in ['ticks', 'reflex_hz', 'period_ms', 'tick_ms', 'aim_ms', 'decision_hz', 'decide_ms', 'decision_lag_ms', 'range_gaps', 'errors']},
        'live_scope': meta['start']['live_scope'],
        'limitations': [
            'The failed final send omitted decision/step 84; cancellation proves its pulse ownership, not its absent State/probabilities.',
            'Returned LT calls are software delivery reports, not a physical button-duration measurement.',
            'Visible cast/impact attribution requires the separate native-video audit.',
            'One exploratory Luna run does not count toward the designated Galacta benchmark or independent-session validation.'
        ]
    }
    return report


if __name__ == '__main__':
    import sys
    result = json.dumps(summarize(), indent=2) + '\n'
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(result, encoding='utf-8')
    else:
        print(result, end='')
