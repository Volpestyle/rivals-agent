# EXPLORATORY Mac match-expanded refit ? pre-launch freeze

Lead decision: 8 TRAIN ranges plus current -4a1/-5a1/-6 and -7/-8/-10. Entire -11/-12 families are excluded, including their previously read rows. Global registry roles stay unchanged. No sealed/test/archive/DayMR source, new admission, decoding, cloud action or input-volume deletion.

## Exact data and envelope

**200.976241528 counted minutes**, including 166.926104 range minutes. Accepted-span accounting differs slightly from target discretization: **200.967220213 usable target minutes**. Context filtering yields **722,074 TRAIN examples**, 45,130 updates/epoch, **135,390 updates in three epochs**. Frozen range dev remains 49,080 rows.

| Session | Run role | Complete contexts |
|---|---|---:|
| 20260923T051828-422Z-33696-1 | train | 25084 |
| 20260923T171533-187Z-33696-5 | heldout | 9244 |
| 20260923T200129-346Z-33696-6 | train | 95788 |
| 20260923T205528-900Z-45572-3 | heldout | 39836 |
| 20260924T232304-170Z-12024-1 | train | 31522 |
| 20260925T021320-371Z-7804-1 | train | 124172 |
| 20260925T025230-605Z-7804-2 | train | 13156 |
| 20260926T045729-166Z-79780-1 | train | 36882 |
| 20260926T035932-508Z-63684-14 | train | 108412 |
| 20260925T203745-207Z-49728-2 | train | 165416 |
| 20260927T051206-888Z-150600-4 | train | 17686 |
| 20260927T052001-827Z-150600-5 | train | 20422 |
| 20260927T053118-260Z-150600-6 | train | 15302 |
| 20260927T053838-153Z-150600-7 | train | 24922 |
| 20260927T055006-068Z-150600-8 | train | 18336 |
| 20260927T060021-195Z-150600-10 | train | 24974 |

Whole-session transfer holdout: -11 (`20260927T061107-953Z-150600-11`) and -12 (`20260927T061900-143Z-150600-12`). `heldout.json` copies their **15,960 + 22,020 = 37,980** unread row IDs and complete selection metadata unchanged from committed complement **5a04fa8**, before predictions. Earlier read blocks, embargo/context overlaps and inspected sample contexts stay excluded. Neither holdout family enters fit, support counts, threshold selection or model selection.

Recipe: fresh seed0 initialization, same full03 architecture, beta-NLL0.5, AdamW0.001/weight-decay0.0001, clip1, batch16, three epochs, unchanged vocabulary, uncertainty/abstention and pitch calibration. No deadband (the TRAIN experiment selected identity). Per-epoch data order remains `random.Random(seed*1000003+epoch)`.

**$0 Mac MPS; nice10; two Torch intra/inter-op threads.** Plan ~2.3h fit from the earlier 54m06s/80.53min Mac observation, and **six hours total** including prepare/hash checks, TRAIN press calibration and evaluation, with ~30% margin. This is a projection, not a throughput guarantee or forced stop. Report first-epoch rate and any overrun; do not switch to paid compute.

Memory: demand-mapped immutable uint8 stores; no whole-array float conversion/preload. Batches16 for fit/32 for inference, one heavy process. Fit, press and camera phases are separate processes to release mappings. Log RSS/MPS allocator bytes/swap every100 training updates and epoch. Prior MPS footprint3.78GiB/RSS53.30GiB is evidence, not a bound for the larger corpus on128GiB unified RAM; physical page-cache pressure is a risk.

## Checkpoints, scope and readout

Each epoch writes/fsyncs model, optimizer, scheduler(None), Python/NumPy/CPU/MPS RNG, exact shuffled-row contract, step count, data cursor and history. Publish its unique payload before a hash-recorded completion receipt, fsyncing the directory after each. Keep earlier verified epochs. Epoch1 is independently scoreable. Re-entry restores the last complete epoch and replays an interrupted epoch in identical order; missing, corrupt or incompatible complete state refuses. Fresh initialization applies to the initial launch; there is no automatic retry.

Native CPU/MPS synthetic tests: **29 passed**, including exact uninterrupted-versus-epoch1-resumed model/optimizer/RNG equality and mid-epoch replay. PC20pass/13native-MPSskip. MPS RNG uses Torch's native get/set state API; prior CPU/CUDA behavior retains compatibility. One initial metadata-preparation invocation refused a missing `pitch_deadband` module before data loading; closure completed and final preparation passed. No training had launched at freeze.

Post-fit: TRAIN-only press rate calibration on the14 training sources, frozen range-dev fixed0.5/train-rate precision/recall/chance with real versus zero visual tensors. Camera readout: **new raw, full03 (immediate baseline), older prior, zero motion**, all on MPS and unchanged target rows. Report -11 then -12, own/common coverage and still/moving/one-second slices before pooled MAE. The old prior is retained to match the earlier report; no threshold/model choice uses either holdout. No Gate2, replay-transfer or corpus-labeling claim follows from this exploratory result.

Status name `idm-match-refit-mac-20260928`, native root `/Users/james/dev/idm-data/match-refit-mac-20260928`, per-phase logs/status/.exit and terminal run.exit. Completion watcher reports each independently hash-verified epoch and final state, survives transient SSH errors, never launches, retries, deletes or releases the slot itself. Owner reports launch, each epoch and final result to herdr-lead for VUH-1353; release the slot explicitly when finished.

ManifestSHA: d0872c6353a93789a69d73a3c42f7d45e3d533301dba3d47e8bcfacb880f0a79. Runtime inventorySHA: e608cf0a57e56191d5b6f5f619134f80c56c4c6205d22825f8243fa1938fb825. All native source bytes are pinned by runtime-inventory.json; this new snapshot does not modify previous freezes. Admission authority12 and current receipts are reused unchanged. No independent review is required for this exploratory workload under docs/compute.md; admission/sealed boundaries are unchanged.
