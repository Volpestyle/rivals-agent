# Round-3 per-fit receipt contract (review candidate)

Published early for modal-port and now implemented in `policy/range_bc/cm3_run.py`.
This specifies the revised interface requested by the lead; it is not probe, spend,
launch or parallel-run approval. No real job has run. `HANDBACK-fixes.md` pins the
candidate implementation and synthetic tests for independent review.

Invocation:

```text
python -m policy.range_bc.cm3_run fit --arm H --seed 0 --receipt /receipts/H0.json --receipt-sha256 <externally communicated lead SHA256>
```

Exactly ONE fit runs per invocation. `--arm` is A/H/I/W, `--seed` is 0/1/2.
H0's repeat is another invocation with the same CLI arm/seed and receipt purpose
`repeat`; the ordinary receipt purpose is `registered`. No implicit queue/retry.
MPS A invocations reread authenticated historical checkpoints, never retrain A.
CUDA A invocations train the unchanged legacy A recipe for all 13 epochs.

Approval JSON uses `format: cm3-stage-approval-v1`, `approved_by: herdr-lead`,
`stage: fit`, and these fields (all required):

| Field | Contract |
|---|---|
| `context` | Frozen common context below, identical for all calls in the matrix. |
| `context_sha256` | SHA256 of UTF-8 JSON of context with sorted keys, compact separators and ensure_ascii=false; no NaN. |
| `arm`, `seed`, `purpose` | Must match CLI. Purpose `registered` or `repeat`; repeat is legal only for H/0. |
| `attempt_id` | Unique nonempty letters/digits/dot/underscore/hyphen identifier, repeated in result. A retry is a new lead approval, new ID and new output directory, with failed compute charged. |
| `subset` | Literal `one-registered-fit`. |
| `allowed_sources` | Exact five train then two frozen-dev IDs in pre-registration order. Registry split of all seven is train; experiment roles remain five train/two dev. |
| `predecessors` | Object with exactly `proof128`, `smoke`, `extract`, each a pinned PASS result reference. Each result binds its approval and common context. |
| `fit_predecessors` | Object of pinned receipts defined below. No unspecified dependencies. |
| `freeze` | Exact `artifacts` object from the authenticated extract result; includes inputs, scored audit, pairing, seven feature manifests, details. |
| `budget` | `approved_by: herdr-lead`, `cap_seconds` <=57600, `spent_seconds`, positive `stage_seconds` <=remaining cap, `forecast_total_seconds` <=cap. CUDA also requires `cloud_instance` (instance class/product, not unique host), `hourly_usd`, `cloud_cap_usd`. Each invocation has an explicit time allocation; modal-port/lead must account for all allocations and actual compute, including failures/repeats/proofs. This API does not grant a second 16-hour budget per fit. |
| `output` | New immutable output directory. Existing directories refuse. |

A pinned reference is exactly `{"path":"/absolute/path","sha256":"64 lowercase hex"}`.
The external lead pin is the trust root; a receipt does not authenticate itself by
claiming `approved_by`. The runner never authors approvals or discovers source paths.

`context` contains `amendment: 2`, `device: cuda|mps`, `hardware`, `software`,
`code`, `implementation_review`, `judge`, `judge_tests`, `registry`, `denylist`,
`patch_equivalence`, `sidecar_manifest`, `sidecar_reader_sha256`, `assets`,
`dev_workload`, and `sources`. MPS additionally has `mps_A` with seeds 0/1/2,
each containing pinned `checkpoint` and `evaluation` references.

- `hardware` is `{class, driver, cuda_runtime, cudnn}`. CUDA examples:
  `class: cuda:L40S` or `cuda:L4`. Driver, torch, CUDA and cuDNN must match exactly.
  Host name and GPU UUID are deliberately excluded. MPS uses `mps:<chip name>`,
  its OS version as driver and null CUDA/cuDNN. Runtime software separately pins
  Python, OS, machine architecture, every installed package version selected by
  the platform lock, `torch_build`, and the six lock/input file hashes.
- `code`: exact repository-relative raw SHA256 closure returned by `code_hashes()`.
  `software`: exact object returned by `software_snapshot(device)`.
  Lead captures both on the chosen class and reviewer verifies them before probes.
- `implementation_review`: pinned JSON with `status: PASS`, independent `reviewer`
  and the exact `code` map. `judge` and `judge_tests` pin the independent judge code.
- `sources`: exactly seven frozen IDs; each entry is `{role, table, cache,
  cache_manifest_sha256, sidecar}`. Table and sidecar are pinned references;
  sidecar is null only for the two dev sessions. `cache` names original RGB cache
  directory. Every path (including I) rehashes source caches before use.
- `assets`: `{directory, config_sha256, receipt}`; receipt is the verified DINO
  asset/implementation object emitted by FrozenDino. No download fallback.
- `dev_workload`: `{run_lengths:[...], window_count:N}` is frozen dimensions only
  for synthetic smoke timing; proof/smoke never open dev payloads.

Required per-fit predecessors:

| Invocation | Exact keys in `fit_predecessors` |
|---|---|
| A seed 0/1/2 | empty object |
| registered H0 | `A_control_gate` |
| repeat H0 | `A_control_gate`, `H0` |
| H1/H2/I0/I1/I2/W0/W1/W2 | `A_control_gate`, `H0_repeat` |

`H0` and `H0_repeat` reference PASS per-fit results. The repeat must contain
`repeat_identical: true` and name the original H0 result. The runner verifies
checkpoint byte hashes, non-timing loss/metric blocks and executed-decision digest.
An `A_control_gate` is a separate lead-written pinned JSON:

```json
{"format":"cm3-control-gate-v1","approved_by":"herdr-lead","status":"PASS",
 "context_sha256":"...","controls":{"0":{"path":"...","sha256":"..."},
 "1":{"path":"...","sha256":"..."},"2":{"path":"...","sha256":"..."}}}
```

The runner authenticates all three A outputs and recomputes the independent
judge's arm-level S control gate; A passing S refuses core fits. The lead's JSON
cannot substitute for the three authenticated controls.

Successful per-fit result at `output/result.json`:
`format: cm3-stage-result-v1`, `stage: fit`, `status: PASS`, `approval` pinned ref,
`context_sha256`, `arm`, `seed`, `purpose`, `attempt_id`, `hardware`, `code_sha256`,
`software_sha256`, `artifacts`, `elapsed_total_seconds`, `elapsed_stage_seconds`.
`artifacts.details` pins the result's logs/evaluation/checkpoint reference;
`artifacts.inputs`, `audit` bind the source/sidecar/statistics provenance.
No PASS on timeout, failed repeat, failed provenance or partial fit. Preserve
partial artifacts with `INCOMPLETE.json`; they cannot satisfy predecessors.
Only the supervisor promotes a finished child's `completed.json` to `result.json`
after checking the time allocation. A preempted container may be unable to write
INCOMPLETE; absence of a valid PASS `result.json` is sufficient to classify that
attempt as incomplete. `completed.json`, partial checkpoints and logs never pass
a gate. There is no automatic resume/retry or checkpoint continuation. The outer
harness retains every attempt and requests/uses a new explicit lead receipt for
any fresh attempt; attempt/output/compute accounting cannot be silently reused.

Before handing results to the judge:

```text
python -m policy.range_bc.cm3_run verify --receipt /receipts/verify.json --receipt-sha256 <lead pin>
```

The verification approval is `format: cm3-verify-approval-v1`,
`approved_by: herdr-lead`, `context_sha256`, `outputs` (a list of pinned result
references), `budget`, and `output` (new JSON path). Verification budget has
`approved_by`, `cap_seconds`, `spent_seconds`, `stage_seconds`; spent must cover
the preflight plus the sum of completed fit-attempt seconds, and the lead must
also charge failed attempts. It must enumerate exactly A/H/I/W seeds
0/1/2 plus the H0 repeat (13 outputs). Verification checks one context, hardware
class, code/software closure, all per-fit approvals/predecessors, all checkpoint
hashes and the repeat before emitting `cm3-matrix-verification-v1` PASS. It does
not choose a policy. Selected outputs must be the same attempts named by the
control and repeat predecessor gates. The independent judge remains the selection authority.
