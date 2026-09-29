"""Verify the pending patch in disposable files; never apply it to the checkout.

Run with uv run [--group perception] python <this file> --root <checkout>.
Uses only synthetic tests. Frozen runtime preimages must still match.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    packet = Path(__file__).resolve().parent
    bases = json.loads((packet / 'base-sha256.json').read_text())
    with tempfile.TemporaryDirectory(prefix='rivals-rebind-verify-') as scratch:
        scratch = Path(scratch)
        for name, expected in bases.items():
            raw = (root / name).read_bytes()
            if hashlib.sha256(raw).hexdigest() != expected:
                raise SystemExit(f'preimage changed: {name}; refresh and review the patch')
            target = scratch / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        for name in ('agent/camera_map.py', 'agent/camera_maps/legacy-265-75.json',
                     'agent/camera_maps/alt-247-124.json', 'docs/spiderman-kit.md'):
            target = scratch / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / name, target)
        patch = str(packet / 'integration.patch')
        subprocess.run(['git', 'apply', '--check', patch], cwd=scratch, check=True)
        subprocess.run(['git', 'apply', patch], cwd=scratch, check=True)
        sys.path[:0] = [str(root), str(root / 'scripts'), str(root / 'tests')]
        import agent
        spec = importlib.util.spec_from_file_location('agent.pre_rebind_controller', root / 'agent/controller.py')
        before = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = before
        spec.loader.exec_module(before)
        agent.__path__.insert(0, str(scratch / 'agent'))
        from agent.controller import Controller, Cal
        from agent.intents import Search, Disengage, Engage, Idle
        from agent.state import State, Detection, ENEMY
        old, new = before.Controller(), Controller(cal=Cal.from_profile(live=True))
        bot = Detection(ENEMY, (630, 300, 650, 420), .9)
        for i in range(1500):
            intent = Search() if i < 400 else Disengage() if i < 500 else Engage(bot) if i < 900 else Idle()
            state = State(t=i/60, frame=(1280, 720), detections=[bot])
            assert old.step(state, intent) == new.step(state, intent), i
            assert old.cam == new.cam, i
        print('1500 exact pad reports and camera states match the pinned pre-patch controller')
        import agent.loop as loop
        loop.ROOT = root
        import pytest
        tests = ['test_camera_map.py', 'test_controller.py', 'test_startup.py', 'test_loop.py',
                 'test_range_skill_controller.py', 'test_range_pulse_lifetime.py']
        return pytest.main([str(scratch / 'tests/test_camera_rebind.py'),
                            *[str(root / 'tests' / name) for name in tests], '-q'])


if __name__ == '__main__':
    raise SystemExit(main())
