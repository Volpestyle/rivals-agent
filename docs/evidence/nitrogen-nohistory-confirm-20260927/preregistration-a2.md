# A2: evaluation-only recovery on the Mac

2026-09-27. Pre-result amendment to the base preregistration (`825c3852d82ac0eb3e994bb64bf995e3babb7b14017da9d86cb8f564a9294295`)
and A1 (`7950bd9fce5cd57cde3bc218275999afec1cbfdb40f5ae47c142c5d03472f8a1`).
The lead approved this recovery in principle, conditional on committing these pins
before evaluation. No primary confirmation decode result has been read. Five
recovered snapshots contain zero completed decode summaries. Training progress,
checkpoint metadata and the existence of TRAIN cutoff receipts were inspected.

## Incident and preserved evidence

Five original invocations completed epoch 26 and then were interrupted during
evaluation. A subsequent worker entry refused the existing `/outputs/run` at
`encoder_worker.py:48`. Candidate-s1 and control-s1 system logs show new L40S
capacity waits at 19:15:29 and 19:15:27 UTC respectively, aligned with IDM's
19:15:28 wait on a separate app. This supports shared rescheduling/redelivery;
the initiating infrastructure cause is unknown. No operator fit retry occurred.
The refusal prevented a second fit. Original failed `final.json`, partial evaluations,
logs and teardown receipts remain unchanged. Control-s3 is allowed to finish untouched.

All five recovered checkpoint files are 128,236,405 bytes. Two independent reads
of each terminal output volume agreed byte-for-byte by SHA256. `weights_only=True`
loading succeeds; the final model tensors are finite and exactly equal to
`latest.pt`; status records complete epoch 26 and 15,288 updates. There is **no
pre-failure worker checkpoint digest**, so these checks establish stable persisted
bytes and consistent completion evidence, not comparison to an unavailable old hash.

| Arm | Epoch-26 checkpoint SHA256 | Original evaluation receipt SHA256 (contains complete CUDA TRAIN cutoffs) |
|---|---|---|
| candidate-s1 | `9f3dfd1a9a2edb1c280f0a2a86a18cb34cfe2a7ce172931823ababca41eebf24` | `1399b086450478335e9c9b63bb4d99d8cc028f0705ebaab6ba90211a5f9b783c` |
| control-s1 | `46988821f363902b3c285db39e299db6da9af4d925cbba7f03f09b8c2efc4b17` | `d7e496bed6c6cf706ae50977cb1418e63922171101a13ee310c81bd9c9bb6a30` |
| candidate-s2 | `99f17cd5e105a96dc1b89face1145ec037606c329cc7a2710c081f4dc7c495b7` | `cacc25bbadf15e146cfef36a485d1c69783af36be639914ebfc8fa755b1e59a1` |
| control-s2 | `532e22db162976eda9baccd5ac2c6a9f3ac5f198839c90a155843e51e80f57d0` | `b08d60edfdd2f946d9a25d3e1399b7a1875c921b0983815dd49c0c353604c395` |
| candidate-s3 | `b52c3aef493118b8275bc8f291719b54efaae16d9e4d45caea0313aea6aa6c51` | `89e0f132bcac4052301381e907410d87045b0f7c066c66252c057cffb5a320fb` |

Control-s3's checkpoint and original TRAIN receipt must receive the same verification
and be pinned in a committed `recovery-inputs-control-s3.json` **before its evaluation**.
If its original Modal evaluation completes, retain it unread and still evaluate its
unchanged epoch-26 checkpoint on the same Mac stack as the other five. If it fails,
recover only a verifiably complete checkpoint. A missing/partial fit invalidates the
six-run confirmation; no refit, replacement seed or selected checkpoint is permitted.

## One evaluation stack, no new training

All six evaluate on the **Mac MPS device**, PyTorch **2.14.0**, transformers **4.57.1**,
safetensors **0.6.2**. Frozen vision uses **bfloat16**, pooling float32, stored features
float16, and policy heads/recurrent state float32, as in the original numerical graph.
Require MPS and this precision path; do not silently substitute another precision or
device. Record OS, package versions, source hashes and feature hashes. The original
training and exploratory seed-0 evaluation were **CUDA L40S**, so Mac results may
differ numerically; compare all six on this one stack rather than mixing devices.

Reuse each checkpoint's exact, authenticated, original CUDA **TRAIN-only** calibration
receipt. Do not reselect thresholds on Mac or dev. The evaluator's sole functional
extension skips TRAIN prediction/calibration when supplied this authenticated receipt;
it retains the full receipt in the output. Recompute cohort references from the same
admitted tables. Rebuild frozen-dev visual features once using the pinned local NitroGen
vision weights and unchanged graph, and share those features across all six heads.
No TRAIN feature extraction is needed. All original roster/header/denylist checks remain.
No new admission, sealed payload, cloud app or cloud volume mutation is authorized.

The wrapper verifies checkpoint/receipt hashes, seed/history/epoch/update identity,
the original A1 training identity, complete-fit status and finite tensors before evaluation.
It contains no fit call. Partial training is refused. Each new evaluation uses a fresh
directory; a completed stage can be reused only after its identity and artifact hashes
verify. An interrupted evaluation is not a successful result and requires explicit
recovery authorization; it never triggers training.

## Frozen judgement and reporting

Judge remains **`6f2187dd974befedbaf656470d7b153f3a5ca7be0a62a3954a67670ab726aa32`**,
metrics `ff8ec1788700392a2490d39d19ecc623cea85094adbd23873aefb30420e2a2e5`, vocab
`9f57c02a977921cc0f8fef003a19eb647136ff51af34a7913f76fb22ec811f3e`.
All primary/secondary metrics, strict paired-seed decision rules, six decodes, random
floor, real-vs-zero NLL and persistence stop rule are unchanged. Nothing is read for
comparison before **all six Mac evaluations exist**. A persistence stop remains an
immediate lead notification; incomplete decodes never receive a confirmation verdict.

Training checkpoint metadata retains its original A1 pin; do not rewrite checkpoints
to insert A2. `runs.json`/the judgement source manifest keeps A1 as the original
`prereg_sha256` and additionally pins A2, the sixth-input receipt, recovery source,
checkpoint identities and original failed-final hashes. A new, explicitly labelled
**evaluation-only** success receipt supplies evaluation exit/hash and terminal local
process evidence to the unchanged judge. It links the original failed training-app
receipt without claiming that original invocation exited successfully. Report this
receipt interpretation and the MPS device change prominently.

Independent judge clearance already received (`cf8724b53bb29dc2829fbf844a1c53ea3e3f37e5123fe43dc10c4519f1f6b34a`)
remains attached; the judge is not edited. Publishing still explicitly verifies all
source pins and reports yaw, pitch and each paired-seed difference.

## Cost and queue

**$0 additional cloud spend. Mac only, `nice -n 10`, one heavy job at a time** in the
lead-assigned slot. Finish collection and terminal accounting of the original Modal
apps under their existing guards; do not touch the still-running control-s3 input.
The original $20 campaign cap remains; this amendment authorizes no further cloud run.
The offline replay follows only after confirmation evaluation and the lead's decision;
release the Mac slot to the lead and IDM when this work is complete.
