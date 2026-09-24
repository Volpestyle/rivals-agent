"""Verify a Mac-trained cohort checkpoint on Windows CPU (2026-09-23), with no live IO.

    uv run --offline --no-project --with torch==2.14.0 python -B <this file> --run data/diagnostics/<RUN>/run-1 \
        --mac-report-sha256 <sha256>

Run from a checkout whose policy/*.py are LF. Every gate is an explicit raise, and -O is refused. The fit driver
beside this file must be the bytes the Mac ran, and exactly those bytes are executed. Its stage 1 re-checks every
input, the admission and the code closure before any policy code is imported. The exact checkpoint then reloads on
CPU under the Mac's torch version, and its predictions and metrics must equal the Mac CPU reload.
"""
import sys

if sys.flags.optimize:
    raise SystemExit("refused: run without -O or PYTHONOPTIMIZE")

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import types

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def gate(ok, message):
    if not ok:
        raise SystemExit(f"refused: {message}")


ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("--run", required=True, help="directory holding the returned model.pt and mac-report.json")
ap.add_argument("--mac-report-sha256", required=True)
args = ap.parse_args()

run = ROOT / args.run
raw = (run / "mac-report.json").read_bytes()
gate(hashlib.sha256(raw).hexdigest() == args.mac_report_sha256, "mac-report.json differs from --mac-report-sha256")
mac = json.loads(raw)
driver = HERE / "fit_cohort_20260923.py"
source = driver.read_bytes()
gate(hashlib.sha256(source.replace(b"\r\n", b"\n")).hexdigest() == mac["driver"]["sha256"], "fit driver differs from the one the Mac ran")
fit = types.ModuleType("fit_cohort_20260923")
fit.__file__ = str(driver)
exec(compile(source, str(driver), "exec"), fit.__dict__)  # the verified bytes, never a cached .pyc

for name, digest in mac["input_artifacts"].items():
    gate((ROOT / name).is_file() and fit.sha(ROOT / name) == digest, f"hash mismatch or missing: {name}")
bundle = fit.preflight(mac["cohort_manifest"]["path"], mac["cohort_manifest"]["sha256"], mac["dry_run_member"])
gate(dict(bundle["inputs"]) == mac["input_artifacts"], "verified inputs differ from the Mac's")
examples, source_identity = fit.build(bundle)
P = fit.P
code_checks = {}
for name, digest in mac["code_sha256"].items():
    data = (ROOT / name).read_bytes()
    raw_sha = hashlib.sha256(data).hexdigest()
    blob = subprocess.check_output(["git", "show", f"{mac['git_commit']}:{name}"], cwd=ROOT)
    gate(hashlib.sha256(blob).hexdigest() == digest, f"{name}: the Mac's bytes are not the git blob at {mac['git_commit']}")
    # Only the State file is known to carry CRLF checkout conversion here; policy files must be LF.
    gate(raw_sha == digest or (name == "agent/state.py" and b"\r\n" in data and data.replace(b"\r\n", b"\n") == blob),
         f"{name}: Windows bytes differ from the Mac's beyond the allowed State CRLF conversion")
    code_checks[name] = {"windows_raw_sha256": raw_sha, "mac_and_git_blob_sha256": digest,
                         "crlf_only_difference": raw_sha != digest}

gate(asdict(source_identity) == mac["source_identity"] and P.evidence_digest(examples) == mac["evidence_digest"],
     "rebuilt cohort differs from the Mac's")
torch = P.torch_module()
gate(torch.__version__.split("+")[0] == mac["torch"].split("+")[0], f"torch {torch.__version__} is not the Mac's {mac['torch']}")
torch.set_num_threads(4)
model = P.load_checkpoint(run / "model.pt", expected_sha256=mac["checkpoint_sha256"], expected_identity=source_identity,
                          device="cpu", offline=True)
gate(str(next(model.model.parameters()).device) == "cpu", "model is not on CPU")
probs, names = fit.predictions(model, examples)
known = [(e, p, n) for e, p, n in zip(examples, probs, names) if e.label_known]
prior = {(r["session"], r["grid_index"]): r for r in mac["known_rows"]}
gate(len(prior) == len(known) == mac["label_reproduction"]["known"], "known rows differ from the Mac's")
gate(all(n == prior[(e.session, e.grid_index)]["prediction"] for e, _, n in known), "predictions differ from the Mac's")
delta = max(abs(a - b) for e, p, _ in known for a, b in zip(p, prior[(e.session, e.grid_index)]["cpu_probabilities"]))
gate(delta < 1e-5, f"probabilities differ from the Mac CPU reload by {delta}")
metrics = P.event_metrics(examples, names, model.spec, semantic_revision=source_identity.semantic_revision)
gate(metrics == mac["cpu_reload_train_metrics"], "metrics differ from the Mac CPU reload")
fit.check_loaded(bundle["blobs"])
gate("agent.controller" not in sys.modules and "agent.loop" not in sys.modules, "live IO modules imported")
report = {
    "scope": "Windows CPU reload of the exact Mac MPS cohort checkpoint; train only",
    "mac_scope": mac["scope"], "dry_run_member": mac["dry_run_member"],
    "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "torch": torch.__version__, "device": str(next(model.model.parameters()).device),
    "checkpoint_sha256": mac["checkpoint_sha256"], "mac_report_sha256": args.mac_report_sha256,
    "cohort_manifest": mac["cohort_manifest"], "source_identity": asdict(source_identity), "code_checks": code_checks,
    "admission": [c["admission"] for c in bundle["members"]],
    "evidence_digest": P.evidence_digest(examples), "metrics_equal_to_mac_cpu": True,
    "max_probability_delta_from_mac_cpu": delta, "train_metrics": metrics,
    "known_rows": [{"session": e.session, "grid_index": e.grid_index, "prediction": n, "probabilities": p} for e, p, n in known],
    "validation": None, "deployment_binding": None, "live_io_imported": False,
}
with (run / "windows-report.json").open("x") as f:
    json.dump(report, f, indent=2, allow_nan=False)
    f.write("\n")
print(json.dumps({k: report[k] for k in ("git_commit", "torch", "device", "checkpoint_sha256", "evidence_digest",
                                         "max_probability_delta_from_mac_cpu", "train_metrics")}, indent=2))
