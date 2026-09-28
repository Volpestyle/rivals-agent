# Expanded IDM full02 stopped during training

EXPLORATORY, idm-owner / VUH-1353, 2026-09-28. **INCOMPLETE; no accuracy result.** The accepted v1.0.5 guard stopped the run when an asynchronous billing-summary command timed out after 10 seconds. This preceded the funded work deadline by over seven hours. The cause of the billing CLI latency is unknown. The driver's `RemoteError('')` does not establish a model failure.

## Run and terminal evidence

App `ap-euLgri5kwbkjuNBUaB7Nng`, attempt `idm-expanded-20260928-full-02`; collected spec SHA256 `4d566c85e5447282e2d77757b10d27f5ce4f14ccb9b45b23195e09211fcf16e3` matches the launch packet. Runtime remains adda577 and guard remains accepted v1.0.5 fix1. Exact eight TRAIN ranges plus current -4a1/-5a1/-6, three epochs, same frozen scientific recipe. No additional payload or sealed source was opened.

| Event | UTC, 2026-09-28 |
| --- | --- |
| RUNNING event | 04:12:22.176883 |
| Fence / stop initiation | 07:08:28.538456 |
| Provider stopped_at | 07:08:43 |
| Terminal tasks=0, containers=[] proof | 07:08:48.935139 |
| Original work deadline | 14:19:29.611157 |

`result.json` preserves the initiating `billing refresh failed` refusal and 10-second summary timeout in `accounting.proof.trigger_error`. `app-system.log` records repeated CLI stop requests beginning at 07:08:28Z and runner termination at 07:08:43Z. The collected stderr and host run logs are empty. These logs do not explain the billing query's latency.

The result's raw SHA256 is `5e4400ccdc9ad8f62299af7be0ec5e8ea399b03d826b8c67288038489af1067f`, identical to the canonical Mac result and independently checked by modal-port. Its read-only verification passed v1.0.5 `validate_proof`, matched the live journal's TERMINAL bound, and recomputed the bound from 10,589.330626 seconds. No guard or ledger mutation was performed for collection.

## What survived

The collector authenticated output volume `vo-of4DuLu1EBJH1t8IqOMmva` / `rivals-idm-expanded-20260928-full-02-outputs`, read each of its seven persisted files twice with matching bytes, and used the unchanged guard stage loader to validate the completed local stage's identity and artifact hashes. The archive SHA256 is `2e719257cd84daf4a49437e167c0b078fc926a30370e4b056c09143c2f8b5608`. All 21 collected files matched `hashes.json` after transfer to the PC. The collector is retained as `collector.py`; `hashes.json` pins the original collection, not this report or the collector copy.

Local staging copied and source-hashed 113,401,840,789 bytes in 206.130256 seconds, then independently destination-hashed them in 109.950521 seconds. Its `volume/local/completed.json` authenticates `copy.json` (SHA256 `0e70410b8ebf114b72bc2d4bc7afc33ac2d8b9b93ce337e51d30ed4f059d98cf`) and `local.json`.

Training's last persisted progress was 1,089,042 / 1,961,526 scheduled row presentations (55.52%, during epoch two). The inner status still says `running`; it is historical and stale after the guard's terminal stop. There is no completed fit receipt, checkpoint, camera report, TRAIN calibration, real/zero inference, or paired report. No partial-fit resume is available or authorized.

The local-stage receipt proves staging in the terminated container. Its `/tmp` bytes are not a durable reusable artifact. A future worker must stage and hash-verify the retained inputs again. Source pointers are `policy/idm/local_store.py`, `local_run.py`, and `native_entry.py` at adda577; the frozen Mac tree is `/Users/james/dev/idm-data/expanded-refit-d4f05e0/runtime-local-timing-adda577`.

## Accounting and retained resources

| Item | USD |
| --- | ---: |
| Prior terminal lane bounds | 10.375030068670252 |
| Full02 terminal bound | 7.651963 |
| Total terminal lane bounds | 18.026993068670252 |
| Separately allocated input storage | 1.65 |
| Lane bounds plus storage allocation | 19.676993068670252 |
| Remaining under the authorized $40 lane cap | 20.323006931329748 |

These are conservative guard bounds and a storage allocation, not an invoice. Full02 is TERMINAL with no active hold, tasks or containers. A fresh identical $26.288839 reservation would raise lane exposure to $45.965832068670252, exceeding the current cap. No retry is authorized or launched.

Input volume `vo-PnBxKAp9G4Y8nNwfBOgrdU` / `rivals-idm-expanded-20260928-01-inputs` remains intact pending the lead's decision. The post-completion deletion condition has not been met. The output metadata volume is retained for audit.

## Remaining acceptance and next action

The requested camera comparison against baseline `bce156fc` and press precision/recall/coverage comparison against `dd09f3b3` cannot be computed without a completed model and matched scores. MPS-versus-CUDA and matched-development-row caveats remain in the launch packet. No accuracy, Gate 2, or larger-corpus labeling claim follows from this attempt.

Modal-port now owns the lead-directed guard v2 work. IDM will adapt its bridge only after that interface is frozen, preserving explicit input hashes, verified local staging and refusal of partial fits. Before any paid retry, the lead must resolve the guard path and a full-run allocation that fits the lane cap. IDM then owns the unchanged three-epoch fit, matched baseline/real-zero report, and authorized input cleanup after a complete report. This failure packet is ready for the lead's VUH-1353 current-result / remaining-acceptance / next-action update and readback.
