import json, sys
from policy.range_bc import hudparity
src = json.load(open("docs/evidence/range-bc-20260923/hud-parity-1.json", encoding="utf-8"))["sources"]
hudparity.main(["--rule", "p2", "--pad", *src["pad"], "--mk", *src["mk"], "--out", sys.argv[1]])
