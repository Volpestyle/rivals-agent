"""Verify the exact Mac-trained artifact on Windows CPU, with no live IO."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from agent.state import State, Detection
from policy.range_skill_policy import (
    SourceIdentity, Snapshot, EventExample, cohort, evidence_digest,
    load_checkpoint, event_metrics, OUTCOMES,
)
from policy.execution import torch_module

OUT = Path(__file__).resolve().parent / "run-1"
mac = json.loads((OUT / "mac-report.json").read_text())
assert hashlib.sha256((OUT / "mac-report.json").read_bytes()).hexdigest() == "d5fd7574ca3b815cf718cbb2a376f6028790b67f76c5a752b02ac44d3ea998c4"
assert mac["checkpoint_sha256"] == "7f6f9dafc14e3459e6e7835707b177c3c7fd6357574fc13969a3db25ead1cdc8"
for name, digest in mac["input_artifacts"].items():
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
code_checks = {}
for name, digest in mac["code_sha256"].items():
    raw = (ROOT / name).read_bytes()
    raw_sha = hashlib.sha256(raw).hexdigest()
    blob = subprocess.check_output(["git", "show", f"{mac['git_commit']}:{name}"], cwd=ROOT)
    assert hashlib.sha256(blob).hexdigest() == digest, name
    # The existing Windows State file has CRLF checkout conversion; the Mac
    # and committed blob have LF. Restrict this exception to that observed file.
    if raw_sha != digest:
        assert name == "agent/state.py" and b"\r\n" in raw
        assert raw.replace(b"\r\n", b"\n") == blob
    else:
        assert raw == blob
    code_checks[name] = {"windows_raw_sha256": raw_sha, "mac_and_git_blob_sha256": digest,
                         "crlf_only_difference": raw_sha != digest}
packet = json.loads((ROOT / "data/human/skill-events/032454-train-diagnostic-v1/examples.json").read_text())
examples = []
for row in packet["rows"]:
    history = tuple(Snapshot(State.from_dict(s["state"]),
        Detection(**{**s["target"], "bbox": tuple(s["target"]["bbox"])}) if s["target"] else None,
        s["available_t"]) for s in row["history"])
    examples.append(EventExample(**{**row, "source": SourceIdentity(**row["source"]), "history": history}))
source, origin = cohort(examples)
assert origin == "reviewed_human" and all(e.split == "train" for e in examples)
assert evidence_digest(examples) == mac["evidence_digest"]
torch = torch_module()
torch.set_num_threads(4)
model = load_checkpoint(OUT / "model.pt", expected_sha256=mac["checkpoint_sha256"],
    expected_identity=source, device="cpu", offline=True)
assert str(next(model.model.parameters()).device) == "cpu"
probs = [model.probabilities(e.history, e.anchor_t) if e.label_known else None for e in examples]
names = [OUTCOMES[max(range(len(p)), key=p.__getitem__)] if p else None for p in probs]
known = [(e, p, n) for e, p, n in zip(examples, probs, names) if e.label_known]
delta = max(abs(a - b) for (_, p, _), prior in zip(known, mac["known_rows"])
            for a, b in zip(p, prior["cpu_probabilities"]))
assert [n for _, _, n in known] == [r["prediction"] for r in mac["known_rows"]]
assert delta < 1e-5
metrics = event_metrics(examples, names, model.spec)
assert metrics == mac["cpu_reload_train_metrics"]
assert "agent.controller" not in sys.modules and "agent.loop" not in sys.modules
report = {
    "scope": "Windows CPU reload of exact admitted-human MPS checkpoint; train only",
    "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "torch": torch.__version__, "device": str(next(model.model.parameters()).device),
    "checkpoint_sha256": mac["checkpoint_sha256"], "source_identity": asdict(source),
    "code_checks": code_checks,
    "evidence_digest": evidence_digest(examples), "metrics_equal_to_mac_cpu": True,
    "max_probability_delta_from_mac_cpu": delta, "train_metrics": metrics,
    "known_rows": [{"grid_index": e.grid_index, "prediction": n, "probabilities": p} for e, p, n in known],
    "validation": None, "deployment_binding": None, "live_io_imported": False,
}
with (OUT / "windows-report.json").open("x") as f:
    json.dump(report, f, indent=2, allow_nan=False)
    f.write("\n")
print(json.dumps(report, indent=2))
