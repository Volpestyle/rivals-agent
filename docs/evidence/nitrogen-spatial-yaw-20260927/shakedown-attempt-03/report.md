# Probe3 — PASS

EXPLORATORY launcher shakedown, 2026-09-27. **All six L40S apps completed,
their collected artifacts verified, and teardown proved terminal state with zero
containers.** Their actual tensor work overlapped for **22.499547 seconds**.
The pass was established before the lead's 23:30 UTC fallback deadline.

| Slot | App | AppCreate UTC | Conservative charge |
|---|---|---|---:|
| 03 | `ap-2ghN2b0Ezuu3NFkSaHPRZV` | 22:27:47.774024 | $0.145401 |
| 04 | `ap-olu863dInuTHWIgWfXsdhG` | 22:28:05.522444 | $0.158658 |
| 06 | `ap-0zrL46OUNnZguHuxCBKViy` | 22:28:23.227871 | $0.170222 |
| 02 | `ap-ahOxSkTySUvVHbTY5QBuvW` | 22:28:41.052704 | $0.187043 |
| 01 | `ap-MAdUCvhfMKP7D1hbuNR3TT` | 22:28:58.878519 | $0.198035 |
| 05 | `ap-iQXDlgScKMkrfP3NuUKaA2` | 22:29:16.385368 | $0.208651 |

Every creation used one RPC. All five gaps exceed 15 seconds (17.5–17.8 s).
The original v1.0.4 driver/watchdog path completed without manual reconciliation
or fit retries. Six fresh output volumes remain separate from all earlier
attempts and other lanes.

Each worker verified four byte-pinned blocks from the already admitted TRAIN
input volume, then exercised both grid heads at batch 8 × window 96 for 110 s.
Each completed 954–985 synthetic updates per grid. Action/pitch outputs stayed
exactly equal to the frozen base; base tensors were unchanged with no gradients.
Both heads saved/reloaded successfully with `weights_only=True`. Each checkpoint
and report was copied from its volume and checked against the committed stage
receipt's hash and byte length. Peak allocated GPU memory was 1,016,154,112 bytes
per worker; maximum reported RSS was 4,608,856 KiB. These are cloud measurements.

This proves the six-app launch, pacing, pinned source import, admitted input
read, Modal Volume stage claims, full-shape tensor updates, retention checks,
checkpoint serialization, collection and teardown. The base was randomly
initialized and the spatial features were synthetic. **It does not establish
full-fit p95, scientific yaw quality, confirmed-checkpoint behavior, or the
dual-grid cache extraction.** The individual batch timings are retained as
diagnostics only, not promoted to a measured full-fit budget.

## Accounting and pins

Probe3's conservative settled charge is **$1.068010**, with **$0 active holds**.
Including failed probe2, the yaw campaign's settled conservative charge is
**$1.302986**. Finite bootstrap reservations consumed **$5.861882** of the
lead-reallocated $6; those slots are not recycled after settlement. The unchanged
campaign cap is $24, warning at $20, with $18 allocated to fits (planned six caps
total $15). Storage and provider actuals are distinct from these conservative
compute charges. The historical explore REPORT plus yaw now totals
**$50.329389877872901**; this is not a verified workspace balance or invoice.

- Guard: commit `80d944bd8732103f2de1ad67dd83c4009b6bb7f2`, release
  `5c0e979227738363bfceaef792d9852d2578fcc149f77d2f9cde61510dc8a8fd`.
- Installed reviewer receipt: `9c87e6f6e397252ae164a5482765d7f9c29ac0c87ca8f4eb9c5dec7e9089bd2d`;
  lead acceptance: `05403dabddb1e425f9546690728d3e98721341db1686d50c563c30cbf3175587`.
- Source inventory: `ee4d6efcfcb2391cc56c39ff2fef3296744d959b8c665875da6301d7213b8858`;
  unchanged workload commit `3902167`, base image `im-FNjy4v5u4XYF29SBGvT0KD`.
- Collector: `52d184283922ad21283bd422f1385ae5926f021baba264132d969a00fcedf5a7`.
- Collected summary: `60eddcf8dea531403aef0b24ffeb7da54d913317309dacb6ecab8349cccc3450`.

`SHA256SUMS.json` pins the copied receipts and reports. Synthetic checkpoints
remain under the Mac campaign's `probe-launch-03/collected/<attempt>/probe-yaw.pt`
and their original volumes; their hashes are in each collected result/report.
No sealed payload or scientific evaluation was opened.

The lead was sent this shakedown result before any fit. The shared guard passed
its time-box, so the conditional fallback is not selected. Next: after IDM's
explicit Mac release, build/verify the dual-grid caches, finish scientific
fit/evaluation integration, and prepare the bounded six-fit packet under the
accepted shared guard. No additional AppCreate window is reserved.
