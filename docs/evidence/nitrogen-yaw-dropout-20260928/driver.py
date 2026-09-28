"""One approved three-app batch; no fit retry or guard changes."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback
from decimal import Decimal

packet = Path(sys.argv[1]).resolve()
launch = Path(sys.argv[2]).resolve()
os.chdir(packet/"code")
os.environ["PYTHONPATH"] = str(packet/"code")
sys.path.insert(0, str(packet/"code"))
code = 1
try:
    assembly = json.loads((packet/"assembly.json").read_bytes())
    assert hashlib.sha256((packet/"source-inventory.json").read_bytes()).hexdigest() == assembly["source_inventory_sha256"]
    for name, sha in json.loads((packet/"source-inventory.json").read_bytes()).items():
        assert hashlib.sha256((packet/"code"/name).read_bytes()).hexdigest() == sha
    for item in assembly["specs"]:
        assert hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest() == item["sha256"]
    assert Decimal(assembly["all_six_reserved_usd"]) == Decimal("6.154122") <= Decimal("6.25")
    from cloud.modal_guard.common import DEFAULT_ROOT
    from cloud.modal_guard.release import reviewed, verify
    from cloud.modal_guard.runner import isolated_batch
    verify(packet/"code/cloud/modal_guard", assembly["release_sha256"])
    reviewed(DEFAULT_ROOT, assembly["release_sha256"])
    if assembly["mode"] == "fit":
        probe = json.loads((packet.parent/"probe-results-01/collection.json").read_text())
        assert probe["status"] == "PASS" and len(probe["attempts"]) == 3
        assert probe["release_sha256"] == assembly["release_sha256"]
        assert probe["active_holds_usd"] == "0"
        assert Decimal(probe["bound_usd"]) <= Decimal("1.222980")
        # Reserve the entire prior shakedown envelope, not a discounted balance.
        assert Decimal("1.222980")+Decimal(assembly["total_reserved_usd"]) <= Decimal("6.25")
    commands = [[sys.executable, "-m", "cloud.modal_guard", "run", p["path"], p["sha256"],
                 assembly["release_sha256"]] for p in assembly["specs"]]
    (launch/"started.json").write_text(json.dumps({"unix": time.time(), "pid": os.getpid(), "commands": commands}))
    result = isolated_batch(commands)
    (launch/"batch-result.json").write_text(json.dumps(result, indent=2))
    code = 0 if all(x["status"] == "COMPLETE" for x in result) else 1
except BaseException:
    traceback.print_exc()
finally:
    (launch/"batch.exit").write_text(str(code)+"\n")
    (launch/"terminal.json").write_text(json.dumps({"unix": time.time(), "exit": code}))
raise SystemExit(code)
