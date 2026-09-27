import importlib.util
from pathlib import Path
import sys
import pytest

HERE = Path(__file__).resolve().parent
ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
import policy.range_bc as package
import cm3_accounting
sys.modules['policy.range_bc.cm3_accounting'] = cm3_accounting
package.cm3_accounting = cm3_accounting
spec = importlib.util.spec_from_file_location('policy.range_bc.cm3_run', HERE/'cm3_run.py')
runner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = runner
spec.loader.exec_module(runner)
runner.ROOT = ROOT
package.cm3_run = runner
raise SystemExit(pytest.main(['-q', '-p', 'no:cacheprovider', str(HERE/'test_cap60.py'),
    str(ROOT/'tests/test_range_bc_cm3_run.py')]))
