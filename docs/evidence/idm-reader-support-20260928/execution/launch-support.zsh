set -euo pipefail
cd /Users/james/dev/idm-data/reader-support-20260928
test "$(cat read.exit)" = 0
test ! -e support.pid
/usr/bin/python3 - <<'PY'
import hashlib,json,tarfile
from pathlib import Path
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha('support-closure-a1.tar.gz')=='56864772dacc3ec89a8d023abc93803ada7287a4e25ee86d19ce9fa9a76a9ef8'
assert not Path('code-support').exists()
with tarfile.open('support-closure-a1.tar.gz') as t:t.extractall()
assert sha('inventory-support.json')=='096ad1aa5afe4f167fc11a16d314400e0c3b8f21b2d79d94372fcc9d95a19111'
for p,h in json.loads(Path('inventory-support.json').read_bytes()).items():assert sha(Path('code-support')/p)==h,p
assert sha('support-manifest-a1.json')=='fbb76e4e47d549179e9db72b64cab294e1b212c71a850e7bc20a3309e95a64a1'
# Separate immutable supervisor: reader deployment remains unchanged.
text=Path('phase.py').read_text().replace("str(root/'code')","str(root/'code-support')")
text=text.replace("root/'support-manifest.json'","root/'support-manifest-a1.json'")
text=text.replace('57d098cbc88ad0f8081982183720d3eac0c1be3c2d81f28e1ee19171b4024e3b','fbb76e4e47d549179e9db72b64cab294e1b212c71a850e7bc20a3309e95a64a1')
Path('phase-support-a1.py').write_text(text)
print('support closure verified')
PY
export PYTHONPATH=$PWD/code-support OMP_NUM_THREADS=2 VECLIB_MAXIMUM_THREADS=2 OPENBLAS_NUM_THREADS=2
nice -n 10 /Users/james/dev/idm-data/explore-20260927/code-54bae68/.venv/bin/python - <<'PY'
import torch,json
from pathlib import Path
from policy.idm import train
torch.set_num_threads(2)
m=json.loads(Path('support-manifest-a1.json').read_bytes())
model,p=train.load_checkpoint(m['checkpoint'])
for e in m['sessions']:
 if e['role']=='train':
  assert p['meta']['targets'][e['session_id']]['sha256']==e['targets_sha256'],e['session_id']
  assert p['meta']['frame_stores'][e['session_id']]['manifest_sha256']==e['frames_sha256'],e['session_id']
print('all eleven TRAIN target/store pins match full03 checkpoint provenance')
PY
nohup nice -n 10 /usr/bin/python3 phase-support-a1.py support > support-supervisor.log 2>&1 < /dev/null &
print $! > support-supervisor.pid
cat support-supervisor.pid
