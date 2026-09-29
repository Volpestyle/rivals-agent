"""Run selected failures with the lane's runtime removed, without editing checkout.

The loop is loaded from 8331c45. Other lanes' current files remain in place.
Controller/startup/capture/record/l4_measure must still equal 8331c45 exactly.
No camera integration patch is applied. Pass pytest node IDs after --root PATH.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--nodes-json', type=Path)
    args, tests = parser.parse_known_args()
    if args.nodes_json:
        tests.extend(json.loads(args.nodes_json.read_text(encoding='utf-8')))
    root = args.root.resolve()
    for name in ('agent/controller.py', 'agent/startup.py', 'scripts/capture.py',
                 'scripts/record.py', 'scripts/l4_measure.py'):
        expected = subprocess.check_output(['git', 'show', '8331c45:' + name], cwd=root)
        if (root / name).read_bytes() != expected:
            raise SystemExit(f'baseline runtime changed: {name}')
    raw = subprocess.check_output(['git', 'show', '8331c45:agent/loop.py'], cwd=root)
    with tempfile.TemporaryDirectory(prefix='rivals-baseline-loop-') as folder:
        path = Path(folder) / 'agent/loop.py'
        path.parent.mkdir()
        path.write_bytes(raw)
        kit = path.parent.parent / 'docs/spiderman-kit.md'
        kit.parent.mkdir()
        kit.write_bytes((root / 'docs/spiderman-kit.md').read_bytes())
        sys.path[:0] = [str(root), str(root / 'scripts'), str(root / 'tests')]
        import agent
        spec = importlib.util.spec_from_file_location('agent.loop', path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        module.ROOT = root
        agent.loop = module
        print(json.dumps({'loop_source': '8331c45:agent/loop.py',
                          'deferred_camera_patch': 'not applied',
                          'other_files': 'current shared checkout', 'tests': tests}))
        import pytest
        return pytest.main(tests + ['-q', '--tb=short'])


if __name__ == '__main__':
    raise SystemExit(main())
