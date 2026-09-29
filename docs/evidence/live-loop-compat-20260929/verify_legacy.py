"""Compare 1,500 synthetic steps with the landed c34e6c8 controller; no IO."""
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from agent.controller import Controller
from agent.intents import Search, Disengage, Engage, Idle
from agent.state import State, Detection, ENEMY

raw = subprocess.check_output(['git', 'show', 'c34e6c8:agent/controller.py'], cwd=ROOT)
assert hashlib.sha256(raw).hexdigest() == '25a635d7b6e923c024485995960eb2c35ba4d9777b396b8166e338ea863c0c3c'
with tempfile.TemporaryDirectory(prefix='compat-legacy-') as d:
    path = Path(d) / 'controller.py'
    path.write_bytes(raw)
    spec = importlib.util.spec_from_file_location('agent.compat_legacy_reference', path)
    old_module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = old_module
    spec.loader.exec_module(old_module)
    old, current = old_module.Controller(), Controller()
    bot = Detection(ENEMY, (630, 300, 650, 420), .9)
    for i in range(1500):
        intent = Search() if i < 400 else Disengage() if i < 500 else Engage(bot) if i < 900 else Idle()
        state = State(t=i/60, frame=(1280,720), detections=[bot])
        assert old.step(state, intent) == current.step(state, intent), i
        assert old.cam == current.cam, i
print('1500 exact legacy pad reports and camera states match c34e6c8')
