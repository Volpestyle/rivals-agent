"""One explicitly admitted train-only fit. No source media or live controller IO."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from agent.state import State, Detection
from policy.range_skill_policy import (SourceIdentity, Snapshot, EventExample, Spec,
    cohort, coverage_report, evidence_digest, train, save_checkpoint, load_checkpoint,
    OUTCOMES, event_metrics)
from policy.execution import torch_module

EXPECTED = {
    "data/human/skill-events/032454-train-diagnostic-v1/examples.json":
        "582440d076a952773b0872b2b58451751308f4830f2aeeaa30c2a305482952ab",
    "data/human/reviews/20260922T032454-642Z-24328-1.skill-event-train-diagnostic-decision.json":
        "ccb54491ca44359aa9491f839252cd9e478acdc31baa91317469c052876a6e74",
    "data/human/reviews/20260922T032454-642Z-24328-1.skill-event-independent-review.json":
        "1e8e4d9f3af7ea405f0998afbc9761f9ee2aeca5a23a395fd6e0c77977c3e076",
}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

for name, expected in EXPECTED.items():
    assert sha(ROOT / name) == expected, name
packet = json.loads((ROOT / next(iter(EXPECTED))).read_text())
assert packet["status"] == "accepted_train_only_numerical_fit_reload_plumbing"
examples = []
for row in packet["rows"]:
    history = tuple(Snapshot(State.from_dict(s["state"]),
        Detection(**{**s["target"], "bbox": tuple(s["target"]["bbox"])}) if s["target"] else None,
        s["available_t"]) for s in row["history"])
    examples.append(EventExample(**{**row, "source": SourceIdentity(**row["source"]), "history": history}))
source, origin = cohort(examples)
assert origin == "reviewed_human" and all(e.split == "train" for e in examples)
assert evidence_digest(examples) == "5e540cd76b10e56b1742e8f9dbf7065b2a339a09b56be00836e215f933ef709a"
assert [(e.grid_index, e.label) for e in examples if e.label_known] == [(199, "start"), (200, "no_new_start")]
assert all(e.review_sha256 == packet["review_sha256"] for e in examples)

torch = torch_module()
assert torch.backends.mps.is_available(), "MPS required; no silent CPU fallback"
torch.set_num_threads(4)
config = dict(epochs=100, batch_size=2, lr=.01, device="mps", seed=7)
spec = Spec(hidden=8)
out = Path(__file__).resolve().parent / "run-1"
out.mkdir(exist_ok=False)
t0 = time.perf_counter()
policy = train(examples, spec=spec, **config)
torch.mps.synchronize()
seconds = time.perf_counter() - t0
assert str(next(policy.model.parameters()).device).startswith("mps")

def predictions(model):
    probs = [model.probabilities(e.history, e.anchor_t) if e.label_known else None for e in examples]
    names = [OUTCOMES[max(range(len(p)), key=p.__getitem__)] if p else None for p in probs]
    return probs, names

probs, names = predictions(policy)
code = {name: sha(ROOT / name) for name in ("policy/range_skill_policy.py", "policy/range_policy.py", "agent/state.py")}
checkpoint = out / "model.pt"
checkpoint_sha = save_checkpoint(checkpoint, policy, examples, code_sha256=code["policy/range_skill_policy.py"],
                                  training_config={**config, "spec": asdict(spec), "train_only": True})
loaded = load_checkpoint(checkpoint, expected_sha256=checkpoint_sha, expected_identity=source, device="cpu", offline=True)
cpu_probs, cpu_names = predictions(loaded)
delta = max(abs(a - b) for p, q in zip(probs, cpu_probs) if p for a, b in zip(p, q))
assert names == cpu_names and delta < 1e-5
ammo = [None if not e.history or e.history[-1].state.webs is None else
        ("start" if e.history[-1].state.webs > 0 else "no_new_start") for e in examples]
report = {
    "scope": "admitted_human_train_only_numerical_fit_reload", "not_generalization_or_live_clearance": True,
    "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "torch": torch.__version__, "training_device": str(next(policy.model.parameters()).device),
    "fit_seconds": seconds, "config": config, "spec": asdict(spec), "code_sha256": code,
    "input_artifacts": EXPECTED, "source_identity": asdict(source), "evidence_digest": policy.data_sha256,
    "checkpoint_sha256": checkpoint_sha, "coverage": coverage_report(examples),
    "model_train_metrics": event_metrics(examples, names, spec),
    "cpu_reload_train_metrics": event_metrics(examples, cpu_names, spec),
    "cpu_reload_max_probability_delta": delta, "ammo_baseline_train_metrics": event_metrics(examples, ammo, spec),
    "never_start_train_metrics": event_metrics(examples, ["no_new_start"] * len(examples), spec),
    "known_rows": [{"grid_index": e.grid_index, "label": e.label, "ammo": e.history[-1].state.webs,
                    "probabilities": p, "cpu_probabilities": q, "prediction": n}
                   for e, p, q, n in zip(examples, probs, cpu_probs, names) if e.label_known],
    "validation": None, "deployment_binding": None,
    "limits": packet["use_limit"] + ["Fit is on two overlapping rows; ammunition alone separates them.",
                                      "No native media opened by this training job."],
}
(out / "mac-report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
print(json.dumps({"checkpoint_sha256": checkpoint_sha, "device": report["training_device"],
                  "fit_seconds": seconds, "coverage": report["coverage"], "known_rows": report["known_rows"],
                  "cpu_reload_max_probability_delta": delta}, indent=2))
