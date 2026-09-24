"""Same accepted CLI; record this process's thread settings without tuning them.

    python run_instrumented.py --thread-record <slot dir>/actual-thread-settings.json <agent.loop arguments>

The slot-4 wrapper with the record path as an argument, so each slot keeps its own record.
"""
import json
import os
from pathlib import Path
import platform
import runpy
import sys
from datetime import datetime, timezone

LIVE = Path("C:/Users/volpe/repos/rivals-agent-live")
assert Path.cwd().resolve() == LIVE
assert sys.argv[1] == "--thread-record"
path = Path(sys.argv[2])
sys.argv = [sys.argv[0]] + sys.argv[3:]
sys.path.insert(0, str(LIVE))
import torch


def counts():
    return {"intra_op": torch.get_num_threads(), "inter_op": torch.get_num_interop_threads()}


record = {"pid": os.getpid(), "python": platform.python_version(), "torch": torch.__version__,
          "observed_utc": datetime.now(timezone.utc).isoformat(), "before_main": counts(),
          "thread_settings_modified": False, "model_inference_by_wrapper": False}
with path.open("x", encoding="utf-8") as f:
    json.dump(record, f, indent=2)
try:
    runpy.run_module("agent.loop", run_name="__main__", alter_sys=True)
finally:
    record["after_main"] = counts()
    record["finished_utc"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
