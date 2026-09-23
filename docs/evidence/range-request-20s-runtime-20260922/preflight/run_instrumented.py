"""Same accepted CLI; record this process's thread settings without tuning them."""
import json
import os
from pathlib import Path
import platform
import runpy
import sys
from datetime import datetime, timezone

OUT = Path(__file__).resolve().parent
LIVE = Path("C:/Users/volpe/repos/rivals-agent-live")
assert Path.cwd().resolve() == LIVE
sys.path.insert(0, str(LIVE))
import torch

def counts():
    return {"intra_op": torch.get_num_threads(), "inter_op": torch.get_num_interop_threads()}

record = {"pid": os.getpid(), "python": platform.python_version(), "torch": torch.__version__,
          "observed_utc": datetime.now(timezone.utc).isoformat(), "before_main": counts(),
          "thread_settings_modified": False, "model_inference_by_wrapper": False}
path = OUT / "actual-thread-settings.json"
with path.open("x", encoding="utf-8") as f:
    json.dump(record, f, indent=2)
try:
    runpy.run_module("agent.loop", run_name="__main__", alter_sys=True)
finally:
    record["after_main"] = counts()
    record["finished_utc"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
