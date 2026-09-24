"""Write the operator's effective-setup.json (mode 'x') from a spec, pinning each evidence file by sha256.

    python write_setup.py <spec.json>

spec: {game_pid, range_entry, observed:{...}, display_idle_off_disabled, cpu_percent, observations:[...], limits:[...],
       evidence:[paths]}. Refuses unless every required observation is true; mock is always false here.
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PRE = Path(r"C:\Users\volpe\repos\rivals-agent\data\runtime\galacta-pilot-20260923-preflight")
REQUIRED = ("range", "spiderman", "normal_cooldown_menu", "friendly_fire_off", "pad_web_layout", "galacta_setup",
            "monitor_present", "capture_preflight")
spec = json.loads(Path(sys.argv[1]).read_text("utf-8"))
assert all(spec["observed"].get(k) is True for k in REQUIRED), spec["observed"]
record = {
    "mock": False, "root_ready_for_pilot": True, "observed_utc": datetime.now(timezone.utc).isoformat(),
    "observer": "pilot operator (Claude pane), native frames inspected before the binding",
    "game_pid": spec["game_pid"], "range_entry": spec["range_entry"], "frame": [2560, 1440],
    "observed": spec["observed"], "display_idle_off_disabled": spec["display_idle_off_disabled"], "cpu_percent": spec["cpu_percent"],
    "observations": spec["observations"], "limits": spec["limits"],
    "evidence": [{"path": str(Path(p)), "sha256": hashlib.sha256(Path(p).read_bytes()).hexdigest()} for p in spec["evidence"]],
}
with (PRE / "effective-setup.json").open("x", encoding="utf-8", newline="\n") as f:
    json.dump(record, f, indent=2)
    f.write("\n")
print(json.dumps({"written": str(PRE / "effective-setup.json"), "evidence": len(record["evidence"])}))
