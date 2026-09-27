import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('idm_worker_test', ROOT / 'idm_worker.py')
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


def test_report_context_preserves_metrics(tmp_path):
    path = tmp_path / 'report.json'
    metrics = {'real': {'precision': .3}, 'zero': {'precision': .1}}
    path.write_text(json.dumps({'controls': metrics}))
    roster = [{'session_id': 'a', 'role': 'train', 'targets_sha256': '1'*64, 'frames_sha256': '2'*64}]
    worker.report_context(path, {'sessions': roster}, '3'*64)
    result = json.loads(path.read_text())
    assert result['controls'] == metrics
    assert result['manifest_sha256'] == '3'*64
    assert result['preflight'] == {'passed': True, 'sessions': roster}
