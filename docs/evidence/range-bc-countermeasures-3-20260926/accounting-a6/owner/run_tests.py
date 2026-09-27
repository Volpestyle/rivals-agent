import os, sys
from pathlib import Path
import pytest
root = Path(__file__).resolve().parent
sys.path.insert(0, str(root))
import cm3_accounting, make_accounting_bundle
repo = Path.cwd()
base = repo / 'docs/evidence/range-bc-countermeasures-3-20260926/accounting-a5'
raise SystemExit(pytest.main(['-q', '-p', 'no:cacheprovider', str(root/'test_appcreate_rejection.py'), str(base/'tests/test_canonical_accounting.py'), str(base/'writer/test_make_receipt.py')]))
