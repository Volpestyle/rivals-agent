import importlib.util
from pathlib import Path
import sys
import pytest
ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
import policy.range_bc as package
source = (ROOT/'policy/range_bc/cm3_run.py').read_text(encoding='utf-8')
needle = 'budget["approved_by"] == "herdr-lead" and 0 < budget["cap_seconds"] <= 69120'
assert source.count(needle) == 1
source = source.replace(needle, needle.replace('69120', '69121'))
module = importlib.util.module_from_spec(importlib.util.spec_from_file_location('policy.range_bc.cm3_run', ROOT/'policy/range_bc/cm3_run.py'))
sys.modules[module.__name__] = module
exec(compile(source, module.__file__, 'exec'), module.__dict__)
package.cm3_run = module
result = pytest.main(['-q', '-p', 'no:cacheprovider', str(ROOT/'tests/test_range_bc_cm3_run.py'), '-k', 'complete_synthetic_matrix'])
if result != pytest.ExitCode.TESTS_FAILED:
    raise SystemExit('verification mutant unexpectedly survived: '+str(result))
print('EXPECTED TEST FAILURE: verification cap 69121 mutant killed; production source untouched.')
