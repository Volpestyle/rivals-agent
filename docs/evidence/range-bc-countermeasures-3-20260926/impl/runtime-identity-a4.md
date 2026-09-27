# Pre-result addendum to Amendment 3: managed-host runtime identity

2026-09-27. VUH-1346. Lead authorization: Swarm
01bacc14-48e0-4561-b89f-c40bc31296ad, with James's approval confirmed in
626bbb40-fd4b-4941-8b80-91757693ca31. Independent review and new launch pins are
required before use. This note does not authorize a launch or expenditure.

The inputs-02 software mismatch remains unexplained. Three diagnostic containers
matched the frozen software; probe-03's fresh subprocess also matched. Those
observations do not establish a host-variance cause or exclude variance on another
managed host. This is an explicit pre-result change to the environment identity
required by section 11, motivated by permitting managed-host variation while
retaining one reviewed software image and GPU class. It is not a retrospective
claim about the failed attempt.

For the Modal CUDA branch, required software identity retains exact Python,
machine architecture, every locked package version, all six lock-file hashes,
and the complete torch build text except its single CPU-capability usage line.
That line must have the recognized anchored layout and occur exactly once;
missing, duplicate or malformed lines refuse. Only that line is removed.
The OS identity retains the exact platform string with its kernel-release
component removed. For example, Linux-4.19.0-gvisor-x86_64-with-glibc2.36 becomes
Linux-x86_64-with-glibc2.36. The string contains system/architecture/libc, not a
distribution ID; this note does not claim otherwise. Unknown layouts refuse.

Required hardware identity retains exact GPU class, CUDA runtime and cuDNN, and
the exact NVIDIA driver major branch (580 for the approved L40S image). Driver
minor/patch components are observed rather than compared. The entire observed
driver version must have the recognized numeric layout before a branch is used.
MPS runtime comparison is unchanged.

The raw platform string, kernel release, exact CPU-capability line and full driver
version are recorded in runtime_observation, outside the common context digest
and stable fit-content digest. Fresh capture produces both the required identity
and its raw observation. Stage completion/result records retain the worker's
observation. No old snapshot or approval is rewritten to look like a new capture.

The software identity schema changes; existing full-version contexts are not
silently normalized on read. Code/review/context/catalog and launch receipts must
be frozen again against newly captured metadata. The pinned A3 judge and its
tests remain unchanged: its software pin is an opaque hash and all report/launch
pin equality remains required. Actual software/context hash values are refreshed;
the judge's check and pin schema are not relaxed.

The paired initialization and window hashes, CPU/CUDA feature/logit proof, smoke
repeat and full H0 byte repeat remain unchanged. These checks remain the gates for
numerical effects within their registered coverage; this identity split does not
prove universal bitwise equality across hosts. No tolerance, model, dataset,
schedule, decode, score gate or selection rule changes. All failure artifacts and
spent reservations remain part of the campaign record.

## Capture and control-file contract

The reviewed owner exposes `cm3_run.runtime_snapshot("cuda")`, returning exactly
`software`, `hardware`, and `runtime_observation`. It collects each snapshot once.
The required software object has `format: cm3-software-v2`, `python`, `os`,
`machine`, `packages`, `torch_build`, and `locks`. The hardware object's existing
keys remain `class`, `driver`, `cuda_runtime`, and `cudnn`; CUDA `driver` now means
the canonical major-branch string. The observation object has
`format: cm3-runtime-observation-v1`, `platform`, `kernel`,
`torch_cpu_capability_line` (including its newline), and full `driver`.

The capture consumer stores the returned software/hardware unchanged in a fresh
context, never rewriting an old context. Its approved derivation must constrain
the authorized runtime, including cuda:L40S, driver branch 580, CUDA 13.0 and
cuDNN 92400. The helper reports facts; it grants no capture or launch authority.
Canonical context hashes use the owner's sorted compact UTF-8 JSON with
`ensure_ascii=False`. Raw observations are stored separately.

New common-context, runtime-observation, independent-review and stage-receipt
files may reside under `/outputs/.modal-control/<chain-id>/`. The owner stage
receipt embeds the unchanged required context. Its external lead SHA remains
the trust anchor; writing a derived file is not approval. Existing logical mount
and child-symlink checks apply to control references, and every referenced
document retains its exact SHA. Sources, caches, code and assets stay on the
reviewed `/inputs` volume. Fresh scientific outputs remain outside both
`.modal-control` and `.modal-journal`, as enforced by the launch binding/wrapper.
Control-directory existence never licenses precreation of the owner output.

Per lead scope lock 77ff6991-5e39-4817-8fab-570e06b69ba5, there is no owner
volume-attestation consumption or hash bypass. Table, source-cache, sidecar,
asset, pairing and extracted-output hashing remains unchanged. Per-stage
receipts and subcommands remain; any wrapper orchestration or approved receipt
derivation is separately reviewed and authorized. No receipt-writer or chain
implementation changes are included here.
