# r3-impl F1-F4 follow-up — VUH-1346

Candidate fixes ready for independent fit-review. Not LAND, probe approval, a device
decision, or launch approval. No staging/commits, real 128-frame proof, smoke,
extraction, fit, dev scores, accelerator, Mac/cloud or game job was run.
The prior reviewed HANDBACK.md and review remain byte-identical; this is a new packet.

Review addressed: `review-impl-20260926.md`, SHA256
`7a8dca1d08343cab0167e32efdd8d21c978da5d761accfdbbf597a51bf840ae8`.
Pinned original pre-registration remains 9d61d59 / d15a9254; Amendment 2 remains
`93fc8ecaba9668b53bc3c0da4a4fdea211a9339535b0a06e050c46fa9cd50928`.
H/I/W only; no N configuration, alias, ablation or score-based selection was added.

## Changes and boundaries

- F1/F2: `cm3_run.py` is the sole production CLI (`proof128`, `smoke`, `extract`,
  `fit`, `verify`). It authenticates the externally supplied lead receipt SHA256,
  exact stage/subset/source list, predecessor chain, independent review, code,
  software/lock hashes, hardware class/driver/runtime, budget and cache freeze
  before source payload/model work or output creation. The lead pin is the trust
  root; claiming `approved_by` inside a self-authored file is not authentication.
- Production inputs come only through the pinned registry/denylist and exact
  five-train/two-dev allowlist. Proof/smoke open train payloads only. The strict
  reviewed `idle_sidecar.load_weights` is mandatory, with the reviewed manifest,
  per-session file pins and canonical float32 vector digests. Original unweighted
  statistics are derived from the five training sessions and bound across the
  extraction/fit freeze. Every original RGB cache is rehashed, including I's;
  H/W feature bytes and identities are additionally rehashed. Independent H/I/W
  batch objects must have identical orders for all three seeds and 13 epochs.
- Lead's Modal addition: one `fit --arm {A,H,I,W} --seed {0,1,2}` per invocation.
  No implicit queue or retry. Separate attempt IDs/output directories; the repeat
  is H/0 with purpose `repeat`. Three authenticated A outputs and the independently
  recomputed S control gate precede H0. H0 repeat precedes H1/H2/I/W. MPS A is a
  historical reread; CUDA A uses unchanged legacy training for 13 epochs. Hardware
  class/driver/torch/CUDA/software match across workers; hostname/UUID are excluded.
  `verify` requires all 13 outputs and checks common closure/class, predecessor
  attempt identity, checkpoint hashes, complete epochs and H0 repeat before judging.
- A bounded supervisor enforces each approved time allocation; only it promotes
  completed child output to PASS. Preempted/failed/partial attempts are incomplete,
  retained, and cannot satisfy gates. Matrix verification checks accumulated
  successful compute plus preflight against the lead's budget ledger. The lead and
  modal-port must charge failed attempts, container overhead and outstanding
  allocations; this is not permission to multiply the 16-hour cap per worker.
- F3: repeat features and unchanged backbone parameters now compare canonical
  contiguous little-endian float32 SHA256s, with shapes. Actual numerical_features
  tests mutate +0 to -0 in both outputs and parameters and correctly fail. CPU/backend
  finite/tolerance and executed-decision checks retain their registered thresholds.
- F4: complete wheel-hashed dependency closures for macOS arm64 (14+ floor) and
  Linux x86_64 (manylinux_2_28), constrained by the repository uv.lock execution
  pins. Both include hf-xet 1.6.0. Both resolved again with --offline, with exactly
  the same package/hash content. `fixes-software.json` lists every exact version.

`FIT-RECEIPT.md` was published early and relayed to modal-port and the lead; it is
the per-attempt transport contract. Its SHA256 is `68a8d6d5e4f224f4e3f535da4ec0925d932475cf7c9495bc76a4f2c2fb9155a0`.
The independent judge owns selection/report acceptance; this runner emits measured
per-fit detail blocks and matrix-verification evidence, not a selection decision.
Mapping these blocks into the frozen judge's existing report/launch schema belongs
to the outer harness. No judge code or acceptance rule was changed.

## Verification

- Final CPU synthetic command: `uv run --isolated --locked --group execution
  --with-requirements policy/range_bc/cm3-requirements.txt pytest
  tests/test_range_bc_cm3_run.py tests/test_range_bc_cm3.py tests/test_idle_sidecar.py
  -q -p no:cacheprovider` — **136 passed**.
  Includes missing/wrong receipts, stage/order/device/code/software/source/sidecar
  refusals before model/output; budget and freeze refusal; swapped/unit vectors
  and substituted stats; mandatory reader/cache path; signed-zero mutations;
  per-fit argument/gate/attempt checks; all four one-fit dispatch paths; synthetic
  complete matrix, byte-different H0 repeat and preemption refusal; independent
  window-order mutation; exact legacy stored evaluation blocks; both dependency locks.
- Current-main stdlib regression: `uv run --isolated --locked pytest -q
  -p no:cacheprovider` — **2227 passed,
  76 skipped**. Started from
  `5c3f74eb2d3d1df24e5db014f81e0b4297c836b1`; receipt HEAD `5c3f74eb2d3d1df24e5db014f81e0b4297c836b1`.
  The earlier main run also passed 2227/76; main advanced during that run, so this
  later run confirms the landed state. No --corpus or real-data access.
- Ruff fatal checks E9/F63/F7/F82 pass. Legacy model/train/cache/metrics/executor
  diff against 9d61d59 is empty. The accepted model/feature/training primitives and
  original 24-test file retain their reviewed byte hashes; proof.py alone changes
  for F3 and synthetic timing support for the legacy CUDA A path.
- XML and hashes: `cm3-fixes-tests.xml`, `regression-current-main-fixes.xml`,
  `fixes-validation.json`, `fixes-files.json`, `fixes-software.json` beside this note.

## Lead-filled launch fields and pending measurements

Preserved lead decisions: sample **128 unique cached frames**, 26/26/26/25/25 in
pre-registration session order using one sequential random.Random(20260928)
stream; both global/crosshair views; eligible normal train runs only, never dev.
Smoke uses the first full 96-step train window per session, cycles batches of 8,
and executes the first 32 updates of the full `13*ceil(full_window_count/8)` schedule.
It reports seconds/update and synthetic TF/SF/per-epoch evaluation timing at the
frozen dev workload shapes. No schedule compression.

Device choice, actual Python patch/runtime/driver/hardware class, downloaded-weight
receipt, complete source manifests, review PASS attestation, measured proofs,
smoke/peak-memory evidence, budget/spend allocations and final launch approvals
remain lead-filled prerequisites. The CPU package proposal is CPython 3.11.9,
torch 2.14.0, torchvision 0.29.0, transformers 4.57.1, safetensors 0.6.2, hub 0.36.2,
plus the exact full target closures in this packet. It is not MPS/CUDA compatibility
evidence. In particular the existing MPS primitive reports end allocation, not an
observed high-water mark; an actual MPS choice still needs independently measured
peak-memory evidence for budget approval. No synthetic evidence fills that field.

Gate order remains code/synthetic tests → handback → fit-review → lead probe
approval → 128-frame proof → smoke → measured budget approval → extraction/freeze
→ separately authorized per-fit attempts → matrix verification → independent judge.

## Candidate file hashes

| File | Raw SHA256 |
|---|---|
| `policy/range_bc/cm3.py` | `c93d3c5125f03ef1c0b9183371a4200087a88031f675c3232a078cbaf86d8d3d` |
| `policy/range_bc/cm3_features.py` | `45d40ff6045da313db3ae1b7fb0b3520ec6d08da0a7dea7210c56db1193272e7` |
| `policy/range_bc/cm3_train.py` | `05047796fe67b6cb58d2bde820e39f0500104fb0e90d6bda23af6150a6ded2ef` |
| `policy/range_bc/cm3_proof.py` | `e59a06e4bd349b7e3480f8dc9423ae4eeecb5c8b5c7b984c0b0ff75496e79fc6` |
| `policy/range_bc/cm3_run.py` | `0fe02e2ebbdc50f6fb648d566ac6b9b6cdef28ce101a4ea8d1ecf7b7286e30e8` |
| `policy/range_bc/cm3-requirements.txt` | `a309da99faab36cfc41f4b493a6f7baaca33c218e8809c5852436dab3af8aa35` |
| `policy/range_bc/cm3-environment.in` | `b82abb363e713e1a7078ad7a08fb660f280372088acffb2a199aa18c5c86e7a7` |
| `policy/range_bc/cm3-execution-constraints.txt` | `aaac776e0d03ae16453f0c8d4bddba80285f57a85ef0a9ea62f9ffd8c86c230c` |
| `policy/range_bc/cm3-macos-arm64.lock` | `433eec794dbf0c73f2433e7d5d067baf62a6fe8d23e769717c2c8e8a9a076892` |
| `policy/range_bc/cm3-linux-x86_64.lock` | `7a2634d6a4bcbee0e335ed5412b7e30ed0be088158a2f9d60eb4b8ed2b18571f` |
| `tests/test_range_bc_cm3.py` | `eaec60f6767ba34234694cc5e786e0b8eab3b4332605be03b732ce2dc66cfba5` |
| `tests/test_range_bc_cm3_run.py` | `a331be0fed616d8ac3ceb466a9dd43f94eb5b2e4a0b98c395233134f72c6194f` |
