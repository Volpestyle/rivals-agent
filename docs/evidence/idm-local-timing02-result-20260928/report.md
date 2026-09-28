# IDM local-disk timing: completed, full recipe exceeds current lane budget

Owner: idm-owner, VUH-1353. EXPLORATORY timing only, 2026-09-28 UTC.

The local-disk timing probe completed on one L40S / 8 CPU / 32 GiB worker. All 39 native store files (113,401,840,789 bytes) were copied with source hashes and independently destination-hashed. The production loader then performed its normal verification. The 1,000-update probe measured **6.777766 updates/s** using the slower of two steady halves. The unchanged three-epoch pipeline projects to **36,310 work seconds with 30% margin**, requiring a **$26.29 full-run cap**. That does not fit the remaining IDM lane budget. **No full run launched.**

| Phase | Measured time or rate |
|---|---:|
| Admission/metadata preflight | 35.195 s |
| Copy and source hash | 192.386 s |
| Independent destination hash | 116.710 s |
| Complete local preparation | 309.229 s |
| Production loading, verification and example construction | 341.031 s |
| Steady shuffled training, first half | 6.927923 updates/s |
| Steady shuffled training, second half (projection rate) | 6.777766 updates/s |
| TRAIN inference, 4,096 rows | 112.373607 rows/s |
| Existing range-dev inference, 4,096 rows | 144.241507 rows/s |

The production trainer ran 1,000 actual updates, batch 16, seed 0, with the same three-epoch configuration. The first 32 updates were excluded from steady timing. An independent collection check reconstructed the exact full-cohort shuffle and verified all 16,000 sampled row IDs without repetition, covering all eleven TRAIN sessions. Diagnostic weights were discarded. Inference used fresh, untrained weights of the same architecture; all predictions and camera metrics were discarded. This establishes timing, not input-inference accuracy or a visual-ablation result.

The corpus remains eight admitted TRAIN ranges plus current -4a1/-5a1/-6 (181.89 counted minutes), and the two existing range-dev sessions. There are 653,842 eligible TRAIN contexts and 49,080 dev contexts. No newly accepted night payload, sealed/test footage, archive clips or DayMR footage was added. No new decoding occurred.

## Full-run projection

| Component | Projected seconds |
|---|---:|
| Three training epochs | 18,088.260 |
| TRAIN calibration plus real/zero inference | 6,691.981 |
| Five example loads | 1,705.157 |
| Four local cache re-verifications | 466.839 |
| Local preparation | 309.229 |
| Camera evaluation, extrapolated from fixed dev samples | 302.729 |
| Seven metadata preflights | 246.364 |
| Checkpoint/report allowance | 120.000 |
| Total before margin | 27,930.559 |
| Work envelope after 30% margin | **36,310** |

Adding 120 s startup, 120 s cleanup and $0.05 overhead at the pinned all-resource rate of $0.0007178888888888888888888888889/s gives **$26.288839 reserved**, rounded to a proposed $26.29 cap. This is one-app timing, not an empirical p95. Camera timing is extrapolated; repeated-load allowances are conservative; checkpoint/report overhead is an explicit allowance. A new launch must bind its final recipe and finite envelope separately.

Local staging removes the direct Volume-read path, but the current workload still needs about five hours of training before evaluation and margin. A 7,800-second full attempt would remain undersized. The owner recommends resolving throughput or scope before spending on this unchanged full recipe; any larger budget is the lead's decision.

## Accounting and provenance

App `ap-pJjKWZEP0XIjnBeWRa1E9K`, attempt `idm-local-timing-20260928-02`, made one AppCreate and ended COMPLETE / TERMINAL. Guard teardown proves the app stopped and zero containers. Its terminal bound is **$0.732304**; both timing attempts total **$0.821810**, within the approved aggregate $1.09.

IDM terminal bounds now total **$10.375030068670252**, plus the separately allocated **$1.65** input storage. Remaining lane allowance is **$12.974969931329748** under $25. The projected full run would bring that accounting exposure to **$38.313869068670252**. Bounds and allocations are not a reconciled provider invoice. No IDM holds remain. The input volume is retained for the next authorized attempt.

Source `adda577052a3919fe154c8e649f6fb4cb8d9f40f`; accepted unchanged guard `7ead52f0845fb83b4db0ebf9fc274c6a5adb760b`, release `4a4d57d5ec2b97566b5bc59f212c8f4b9357198fe0eb7270874902079bdd8af6`; launch specification SHA-256 `56799704d63b087b2154e69e4e457e1a5f57ff2769cdb17ac06a3f345b860a4f`. The prior failed callback and fix are recorded separately in `../idm-local-timing01-failed-20260928/`; no historical bytes were changed.

Collected output files were read twice from the exact output volume and verified against the completed stage receipt and its run identity, then hash-checked after transfer to the PC. Independent row-order, rate and cost checks are in `projection-check.json`. Raw receipts and artifact pins are in `hashes.json`.

- `timing/timing.json`: `5bb89717d187816e8710b97213cbd2ee7f26ada57cf80fe1321f66c6d91b82bd`
- `timing/copy.json`: `3332268476354b57c734764ea7b6c4894e1dbfe4a8c4f2da08ec519463791dae`
- Transferred archive: `0935bb05d496592fe9145d862133ce3b336cca231d94002f74cac4ec29d55f86`

Remaining: complete the expanded fit and its real/zero report under a feasible approved envelope, then assess the unresolved Gate 2 transfer requirements. Next action belongs to idm-owner after the lead's throughput/scope/budget decision. This timing result makes no accuracy, policy-training readiness or Gate 2 claim.

Subsequent lead decision: lane cap raised to $40; the unchanged three-epoch full attempt at the measured ~$26.29 envelope is authorized after the brief $0 bottleneck analysis if no concrete fix is established. See `docs/lanes/idm-timing02-bottleneck-20260928.md`. The collection-time $25 comparison and raw receipts remain historical evidence, not the updated cap. Range-dev improvement cannot authorize wider corpus labeling.
