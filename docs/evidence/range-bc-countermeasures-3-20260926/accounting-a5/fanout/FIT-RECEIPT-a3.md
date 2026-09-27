# Amendment 3 per-fit receipt contract

This supersedes the stage ordering and fit dependencies in FIT-RECEIPT.md
(68a8d6d5e4f224f4e3f535da4ec0925d932475cf7c9495bc76a4f2c2fb9155a0).
All other fields, external lead SHA trust root, immutable attempt/output semantics,
hardware-class/software/code checks, and budget accounting remain required.
It is an interface, not launch approval. Implementation review is pending fixes2.

Use `context.amendment: 3` and pin the A3 judge from 595753d:
`judge_cm3-a3.py` SHA256 e23b3212a0eadc98bc590e5081a92c9fab6740e93808aba2d245d6020b3f8eb0;
contract SHA256 7dd39493b754d61df85dc02bc6362f1a53fb1d46f9f9de370b98af03a3b24d54.

## Preflight stages

The production CLI now orders `inputs`, `proof128`, `smoke`, `extract`, `fit`.
Every stage approval's `predecessors` must contain exactly all earlier stages,
each a pinned PASS result with the same common context. `inputs` has no predecessors,
subset `train-inputs-assets-pairing`, and exactly the five train allowed sources.
It authenticates source caches, sidecars, statistics and assets; constructs the
three independent arm window schedules; verifies paired tensors for all seeds,
reordered construction and all 13 window-order manifests; writes `artifacts.pairing`
and `artifacts.inputs` before any numerical frame proof. No features are extracted.

Every later approval additionally requires `pairing`, exactly the pinned reference
from the inputs result's `artifacts.pairing`. The worker recomputes the manifest and
train input binding before any numerical/extraction work. Its own pairing artifact
has the same document bytes; a new output path is expected. Extraction and fit also
recheck the schedules from actual feature adapters. All new-arm train/dev batches
use window 96, stride 64, batch 8; legacy A retains its original schedule.

## Two phases

Exactly one fit per invocation:
`python -m policy.range_bc.cm3_run fit --arm H --seed 0 --receipt <approval.json> --receipt-sha256 <lead SHA>`.

| Invocation | Exact `fit_predecessors` keys |
|---|---|
| A0, A1, A2, registered H0, repeat H0 | none |
| H1, H2, I0, I1, I2, W0, W1, W2 | `phase1_gate` |

The five phase-1 calls may overlap. H0 does not depend on A; repeat H0 does not
depend on H0. Both H calls emit their own checkpoint and stable content digest.
All five must finish before the lead pins a phase-1 gate. All eight phase-2
calls require that gate and may overlap. No receipt authorizes retries or resume.

The pinned `phase1_gate` JSON contains the A3 judge fields plus runner provenance:

```json
{
  "format": "cm3-phase1-gate-v1", "status": "PASS", "approved_by": "herdr-lead",
  "context_sha256": "common context digest", "completed": "ISO8601 completion time",
  "launch_pins_sha256": "judge launch pins digest",
  "outputs": {"A0": {"path": "absolute result path", "sha256": "digest"},
              "A1": {"path": "absolute result path", "sha256": "digest"},
              "A2": {"path": "absolute result path", "sha256": "digest"},
              "H0": {"path": "absolute result path", "sha256": "digest"},
              "H0_repeat": {"path": "absolute result path", "sha256": "digest"}},
  "A_control_gate": {"status": "PASS", "controls": {
    "0": {"checkpoint_sha256": "digest", "content_sha256": "digest"},
    "1": {"checkpoint_sha256": "digest", "content_sha256": "digest"},
    "2": {"checkpoint_sha256": "digest", "content_sha256": "digest"}}},
  "H0_repeat": {"status": "PASS", "repeat_identical": true,
    "H0": {"checkpoint_sha256": "digest", "content_sha256": "digest"},
    "repeat": {"checkpoint_sha256": "digest", "content_sha256": "digest"}}
}
```

`content_sha256` is the per-fit details' `stable_sha256`. The runner authenticates
all five outputs, recomputes A's S gate with the pinned judge, and compares H0 and
repeat checkpoint/loss/evaluation/diagnostics content. Times and memory costs are
excluded from stable identity. The judge separately checks phase completion/start
timestamps. The harness must preserve those actual timestamps and run `verify`
on all 13 outputs before the judge. Verification binds the selected attempts to
the phase-1 gate and checks one hardware CLASS and code/software closure.
Runner hardware remains `cuda:L40S`/`cuda:L4` plus driver/CUDA/cuDNN, never host UUID;
the judge's Modal model/instance fields use its `modal:<GPU>` convention.

## Output diagnostics and incomplete attempts

Every fit's `artifacts.details` includes `context`: measured wall time, held-change
F1, raw teacher-forced metrics and executed counts from evaluation. CUDA includes
`peak_memory_bytes` from reset `torch.cuda.max_memory_allocated`,
`peak_memory_source: torch.cuda.max_memory_allocated`, `peak_memory_reset: true`.
H/I/W additionally emit `unweighted_train_loss`, `normalized_feature_diagnostics`,
`gate_diagnostics` and the exact `train_diagnostic_subset`: first complete 96-row
window in each train session, original masks/positive weights, no idle weights,
augmentation or history dropout. These are report-only diagnostics.

MPS is admitted only with an externally pinned amendment-3 judge explicitly
accepting the matching memory capability. It emits `peak_memory_bytes: null`,
`peak_memory_status: unmeasurable_mps`, `sampled_driver_high_water_bytes`,
`memory_sample_count`, `memory_sample_interval_ms: 10`, and
`memory_sample_source: torch.mps.driver_allocated_memory`. Sampling starts before
model/fit work, polls every 10 ms, and samples again after synchronization at the
end of evaluation/diagnostics. This sampled driver high-water value is not an
allocator peak. A polling error refuses completion. Original judge pins refuse MPS.

Each attempt requires a unique lead-approved `attempt_id` and fresh immutable output.
Only supervised `result.json` PASS counts; `completed.json`, partial files or absence
of a result after preemption are incomplete. Retain failed artifacts and charge their
compute. A retry needs a new receipt/attempt/output; never continue a partial fit.
