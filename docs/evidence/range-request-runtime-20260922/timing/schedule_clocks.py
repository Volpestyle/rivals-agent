"""Clock-selection feasibility only; never constructs alternate States or inputs."""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LOG = ROOT / "data/l1/range-request-diagnostic-20260922-1/frames.jsonl"
EXPECTED = "f735585c44b1657569da4a4a2447c3b5605f12411728cc122f1618287ace47ec"
data = LOG.read_bytes()
assert hashlib.sha256(data).hexdigest() == EXPECTED
rows = [json.loads(line) for line in data.splitlines()]
clocks = [r["send_result"]["observation_t"] for r in rows if "send_result" in r]
origin, slot, selected = clocks[0], 0, []
for t in clocks:
    if t >= origin + slot * .1:
        selected.append(t)
        slot = math.floor((t - origin) / .1) + 1  # skip missed slots; never catch-up burst
bad = []
for i, t in enumerate(selected):
    if i >= 4:
        history = selected[i - 4:i + 1]
        residuals = [(s - (t - (4 - j) * .1)) * 1000 for j, s in enumerate(history)]
        if max(map(abs, residuals)) > 25 + 1e-6:
            bad.append({"selected_index_1based": i + 1, "history_t": history, "residual_ms": residuals})
gaps = [{"selected_index_1based": i + 2, "gap_ms": (b - a) * 1000}
        for i, (a, b) in enumerate(zip(selected, selected[1:])) if abs(b - a - .1) > .025 + 1e-9]
result = {"scope": "fixed_phase_clock_selection_feasibility_not_runtime_or_model_replay",
          "input_sha256": EXPECTED, "origin_t": origin,
          "rule": "first actual reflex acquisition at/after origin+n*.1; skip missed slots",
          "actual_reflex_clocks": len(clocks), "selected_actual_clocks": selected,
          "selected_count": len(selected), "complete_five_clock_windows": len(selected) - 4,
          "irregular_windows_before_any_reset": bad, "adjacent_gap_violations": gaps,
          "limits": ["No new States, detector/selector outputs, features or model predictions constructed.",
                     "No clock rewritten and Spec unchanged; hypothetical selection of existing acquisition clocks only.",
                     "Does not simulate worker availability, altered gameplay, consumer resets, actuation or new target correspondence.",
                     "Absolute phase alone still leaves four irregular windows in these clocks; not a claim of complete repair."]}
assert hashlib.sha256(LOG.read_bytes()).hexdigest() == EXPECTED
out = Path(__file__).with_name("schedule-clocks.json")
with out.open("x", encoding="utf-8", newline="\n") as stream:
    json.dump(result, stream, indent=2)
    stream.write("\n")
print(json.dumps({"selected_actual_clocks": len(selected), "complete_windows": len(selected)-4,
                  "irregular_windows": len(bad), "adjacent_violations": len(gaps)}))
