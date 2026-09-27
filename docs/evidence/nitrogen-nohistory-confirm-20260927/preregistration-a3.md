# Pre-registration A3: input-manifest hash transcription correction

2026-09-27, after all six A2b evaluations completed but before the owner or reviewer inspected any numerical metric or decision. The lead explicitly approved this correction. The evaluator/collector generated and parsed artifacts for completion and identity checks; the frozen judge refused at its input-identity check before computing a decision. No metric values have been exposed to the owner, reported or used to select this change.

## One corrected pin

The actual model input manifest `/Users/james/dev/range-bc-data/explore/modal15/manifest-modal.json` is 1,487 bytes. Recomputed SHA-256:

`aec08c08e247e3743ddeb1eec49dd880e1c0f62039c375932cab31dfccb91e22`

This exactly equals the first 64 characters of every candidate/control seed 1/2/3 checkpoint's run_identity and the manifest row in the original upload manifest. The upload manifest itself recomputes to the already pinned `73c8d80c13281e8a8d4d502e10cb82cf35831eb4ffb1897fdc4e9cbe7789c19e`.

The original preregistration line 49 and frozen judge constant mistakenly appended one `d`, making a 65-character string:

`aec08c08e247e3743ddeb1eec49dd880e1c0f62039c375932cab31dfccb91e22d`

Only that transcription is corrected. The original pre-registration and judge remain byte-intact. Identity verification has not been waived, and no input, checkpoint, cutoff, metric, rule, seed, condition, source dependency or evaluation artifact changes.

## New judge version and required review

New file: `policy/range_bc/confirm_encoder_judge_a3.py`.
SHA-256 (canonical LF): `66830ce6eb302f4b9052b99f0f6ee31836121dd524e7eb1ddabd5a32915ef6c8`.

Historical judge: `policy/range_bc/confirm_encoder_judge.py`, SHA-256 `6f2187dd974befedbaf656470d7b153f3a5ca7be0a62a3954a67670ab726aa32`.

The new file differs by exactly the INPUT_SHA constant dropping its final `d`. Decision logic, metrics, chance-floor implementation and all other bytes are unchanged. Metrics pin remains `ff8ec1788700392a2490d39d19ecc623cea85094adbd23873aefb30420e2a2e5`; vocab remains `9f57c02a977921cc0f8fef003a19eb647136ff51af34a7913f76fb22ec811f3e`.

Frame-review must verify this exact one-constant delta before anyone reads any numerical result or runs the corrected judge. A new synthetic test checks that every hash constant in the active judge is exactly 64 lowercase hex characters; another pins this exact delta and the historical judge hash.

## Evidence and unchanged contract

`judge-refusal.json` raw SHA-256 `72b33e27e4b252df62d03fb8e3c0f0e5c1194f9bcd4fe761c8737903927929ee` records the actual manifest/upload hashes, all six evaluation hashes and checkpoint identities, terminal proof and the refused judge hash. `judge-refusal.stderr.log` preserves the refusal. The original manifest bytes are retained as `verified-model-input-manifest.json`.

A1 remains the original training-recipe pin; A2 remains the evaluation-only MPS recovery authorization; A3 is added to the judgement source manifest. Same six recovered epoch-26 checkpoints, original CUDA TRAIN cutoffs, completed feature caches, MPS stack, all six completed evaluations and original failed Modal receipts. No refit, re-extraction, inference rerun or additional cloud spend is needed. The corrected judge will consume the exact evaluation files pinned before this amendment.
