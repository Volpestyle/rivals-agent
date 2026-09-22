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
from policy.range_skill_policy import (SourceIdentity, Snapshot, RequestExample, Spec,
    cohort, coverage_report, evidence_digest, train, save_checkpoint, load_checkpoint,
    OUTCOMES, event_metrics)
from policy.execution import torch_module

EXPECTED = {
    "data/human/skill-events/032454-request-diagnostic-v1/examples.json": "bd6cf4cb298379ac1a63fd226652e517ad6773ed6b4cead92dfb790abca91570",
    "data/human/reviews/20260922T032454-642Z-24328-1.request-diagnostic-train-decision.json": "52423a3c96504b446d825da6fce9511b1e6572f7d42b0ef4057a46a3959333a1",
    "data/human/reviews/20260922T032454-642Z-24328-1.request-diagnostic-independent-review-receipt.json": "c4a95505b3f0d217ace001cfe9b4838433cd1c3c745e883fe8737f4a42763d07",
    "data/human/reviews/20260922T032454-642Z-24328-1.request-timing-independent-review.md": "12ad3514dc99bce8c4686cd029e495776eaceb02ab3bdc6e17916e694f9272b3",
    "data/human/skill-events/032454-request-diagnostic-v1/source-profile.json": "9f413b81dabc71518359c28a6e506b1a1accbae5654bbf006967652332e3208f",
    "data/human/skill-events/032454-request-diagnostic-v1/dependencies.json": "064004558aee7556fe5548117d968efcc61340bb4f8667ef2b9ba8b9b88cbe72",
    "data/human/skill-events/032454-request-diagnostic-v1/validation-receipt.json": "c83c75ae50c15ab7f39891e7c5177b4cb2bc6331e17a0fb2b7c7b2c9f5676f08",
    "policy/range_skill_policy.py": "d6b62274434cd0b960da817e3d072f933bf6baa6e03055305c120a1e1baa760c",
}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

for name, expected in EXPECTED.items():
    assert sha(ROOT / name) == expected, name
packet = json.loads((ROOT / next(iter(EXPECTED))).read_text())
assert packet["status"] == "accepted_train_only_numerical_diagnostic"
examples = []
for row in packet["rows"]:
    history = tuple(Snapshot(State.from_dict(s["state"]),
        Detection(**{**s["target"], "bbox": tuple(s["target"]["bbox"])}) if s["target"] else None,
        s["available_t"]) for s in row["history"])
    examples.append(RequestExample(**{**row, "source": SourceIdentity(**row["source"]), "history": history}))
source, origin = cohort(examples)
assert source.semantic_revision == "web-cluster-request-v1"
assert origin == "reviewed_human" and all(e.split == "train" for e in examples)
assert evidence_digest(examples) == "736496a3ecdff0db286bec51c6c9da9b27076e41f8b64608de51d3cf5b6a9968"
assert [(e.grid_index, e.label) for e in examples if e.label_known] == [(137, "no_new_start"), (141, "start"), (144, "no_new_start"), (200, "no_new_start"), (206, "no_new_start")]
assert all(e.review_sha256 == packet["review_receipt"]["sha256"] for e in examples)
assert len(examples) == 108 and sum(e.label_known for e in examples) == 5
by_index = {e.grid_index: e for e in examples}
assert [s.state.webs for s in by_index[137].history] == [s.state.webs for s in by_index[141].history] == [3] * 5
assert "agent.controller" not in sys.modules and "agent.loop" not in sys.modules

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
    "scope": "admitted_human_received_request_train_only_numerical_fit_reload", "not_generalization_or_live_clearance": True,
    "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "torch": torch.__version__, "training_device": str(next(policy.model.parameters()).device),
    "fit_seconds": seconds, "config": config, "spec": asdict(spec), "code_sha256": code,
    "input_artifacts": EXPECTED, "source_identity": asdict(source), "evidence_digest": policy.data_sha256,
    "checkpoint_sha256": checkpoint_sha, "coverage": coverage_report(examples),
    "model_train_metrics": event_metrics(examples, names, spec, semantic_revision=source.semantic_revision),
    "cpu_reload_train_metrics": event_metrics(examples, cpu_names, spec, semantic_revision=source.semantic_revision),
    "cpu_reload_max_probability_delta": delta, "ammo_baseline_train_metrics": event_metrics(examples, ammo, spec, semantic_revision=source.semantic_revision),
    "never_start_train_metrics": event_metrics(examples, ["no_new_start"] * len(examples), spec, semantic_revision=source.semantic_revision),
    "known_rows": [{"grid_index": e.grid_index, "label": e.label, "ammo": e.history[-1].state.webs,
                    "probabilities": p, "cpu_probabilities": q, "prediction": n}
                   for e, p, q, n in zip(examples, probs, cpu_probs, names) if e.label_known],
    "validation": None, "deployment_binding": None, "live_io_imported": False,
    "same_ammo_contrast_bins": [137, 141],
    "limits": packet["limitations"] + ["Five training bins contain one unique received request from one same-evening source group; this is not validation.",
                                      "Bins 137 and 141 have identical five-step ammo histories but opposite labels.",
                                      "Window-reset tracking is not proven equivalent to continuous live selection.",
                                      "No native media opened by this training job."],
}
(out / "mac-report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
print(json.dumps({"checkpoint_sha256": checkpoint_sha, "device": report["training_device"],
                  "fit_seconds": seconds, "coverage": report["coverage"], "known_rows": report["known_rows"],
                  "cpu_reload_max_probability_delta": delta}, indent=2))
