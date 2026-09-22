"""Pin deployed bytes against reviewed main; does not issue live authority."""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LIVE = Path('C:/Users/volpe/repos/rivals-agent-live')
OUT = Path(__file__).resolve().parent
BASE = ROOT / 'data/runtime/range-request-diagnostic-20260922'

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def write(name, data):
    with (OUT / name).open('x', encoding='utf-8', newline='\n') as f:
        json.dump(data, f, indent=2); f.write('\n')
    return sha((OUT / name).read_bytes())

assert subprocess.check_output(['git', '-C', str(LIVE), 'status', '--porcelain'], text=True).strip() == ''
commit = subprocess.check_output(['git', '-C', str(LIVE), 'rev-parse', 'HEAD'], text=True).strip()
assert commit == sys.argv[1]
reviewed = {'agent/loop.py': sys.argv[2], 'agent/controller.py': sys.argv[3], 'perception/hud.py': sys.argv[4], 'scripts/range_cast_probe.py': '6792eb459b1a887c9d615e97cc53540c36e9750ffae44f3c39cbfeb6bb7c9a7b'}
for p, digest in reviewed.items():
    assert sha((ROOT / p).read_bytes()) == digest, p
results = {}
for kind in ('controller', 'perception'):
    baseline = BASE / f'{kind}-manifest.json'
    data = json.loads(baseline.read_text())
    data.update(status='deployed_code_pins_matching_independent_review', checkout=str(LIVE),
                git_commit=commit, frozen_utc=datetime.now(timezone.utc).isoformat(),
                baseline_manifest_sha256=sha(baseline.read_bytes()),
                caller_review_sha256=sha((OUT / 'caller-review.md').read_bytes()))
    for path in data['files']:
        live, main = (LIVE / path).read_bytes(), (ROOT / path).read_bytes()
        assert live.replace(b'\r\n', b'\n') == main.replace(b'\r\n', b'\n'), path
        data['files'][path] = {'sha256': sha(live), 'LF_normalized_sha256': sha(live.replace(b'\r\n', b'\n')),
                               'reviewed_main_raw_sha256': sha(main), 'difference_from_main_is_CRLF_only': live != main}
    data.update(run_limit_s=10, startup_limit_s=14, combined_authorization_s=24,
                budget_limit='proof authorization under existing freshness/watchdog limits; not hard process/physical timing',
                run_count=1, scoreboard=False, target_scope='single Luna setup; generic continuous selector')
    if 'D_comparisons' in data:
        data['historical_D_comparisons_before_caller_change'] = data.pop('D_comparisons')
        data['D_delta'] = 'Reviewed focus/deadline, phase and tracing preserved; added exact-output HUD mask reuse and typed request-expiry cancellation. Nominal pulse, resource and target guards remain unchanged; expired requests are never retried. Historical D remains primitive evidence, not current-code or latency equivalence.'
    results[kind] = write(f'{kind}-deployed.json', data)
selector_inputs = {p: sha((LIVE / p).read_bytes()) for p in ('agent/brain.py', 'agent/tracker.py')}
selector = sha(json.dumps(selector_inputs, sort_keys=True, separators=(',', ':')).encode())
assert selector == 'ddf1428a61c54805ce06164ef0daa7dfa1302fdf1735990336fdcab939ae098d'
results['selector'] = selector
write('deployment-check.json', {'commit': commit, 'manifest_sha256': results, 'selector_inputs': selector_inputs,
                                'live_authority': False, 'remaining': 'fresh effective setup and final reviewed runtime binding'})
print(json.dumps(results))
