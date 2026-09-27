# Fixed-checkpoint press diagnostic: TRAIN thresholds and visual control

Owner: idm-owner, VUH-1353. **EXPLORATORY**, completed 2026-09-27 20:41 UTC. No Gate 2 pass, action-label export, weight promotion or live use.

TRAIN-only rate calibration substantially improves precision over fixed 0.5, and the real images outperform rate-matched chance. Precision remains only 36–43%, so most predicted events are still false positives. This diagnoses a threshold problem and a visual signal; it does not validate button labels or establish transfer to matches/replays.

The fixed refit checkpoint is `1b9bcc6a6f909d0e5cbd1cb5fb64c71c89a6cc5320c8c8989ac51cb952cbf541`. There was **no fit**. Calibration reused 289,722 rows from the original five TRAIN ranges. Both visual conditions use the exact same 49,080 saved rows from frozen-dev `171533` and `205528`. No new matches, archive footage, validation/test or sealed sources were read. This still uses the original approximately ±133 ms visual context, not the proposed seconds-context head.

| Action | Rule | Precision | Recall | F1 | Rate-matched chance F1 | F1 minus chance |
|---|---|---:|---:|---:|---:|---:|
| Amazing Combo | Fixed 0.5 | .159615 | .864583 | .269481 | .015666 | .253815 |
| Amazing Combo | TRAIN rate | .421875 | .562500 | .482143 | .010115 | .472028 |
| Jump | Fixed 0.5 | .082221 | .942609 | .151249 | .083978 | .067270 |
| Jump | TRAIN rate | .357357 | .413913 | .383562 | .061547 | .322015 |
| Web Cluster | Fixed 0.5 | .272377 | .736979 | .397751 | .054711 | .343040 |
| Web Cluster | TRAIN rate | .426735 | .432292 | .429495 | .037639 | .391856 |

Zero motion **and** zero HUD produced no events under either rule: recall/F1 0, precision undefined, per-session AUC .5. The real-versus-zero F1 differences therefore equal the real F1 values above. This is an out-of-distribution zero-input control, not proof of match/replay generalization. Rate-matched chance uses 20 deterministic Bernoulli draws at each session's emitted rate; these means are not confidence intervals or a formal significance test.

TRAIN thresholds are .9456475973 (Combo), .9475389719 (Jump), .9723330736 (Web). Achieved TRAIN rates equal their target rates: .0023367228, .0126120902, .0078730645. No held-out label selected a threshold. Scoring includes all known eligible rows without the old probability-abstention band, so fixed-0.5 figures are not directly comparable to the earlier abstained-row report. Matching remains one-to-one within ±2 intervals.

Held-out positive counts are Combo 14/82, Jump 88/487, Web 48/336 (`171533`/`205528`). Combo's aggregate `decides` remains **false** because its first session is below the 30-onset support floor. Jump/Web have sufficient support under this diagnostic's rule; `decides: true` is not Gate 2 acceptance. Session-level metrics remain in the report rather than hiding the small session in the pooled result.

## Preserved attempts and recovery

Press01 ended on the shared Modal rescheduling/redelivery incident before a complete TRAIN stage. Its immutable incident record is [idm-press-incident-20260927.md](idm-press-incident-20260927.md).

Press02 (`ap-WZbhoHmsPD62QkTuSpAr91`) completed TRAIN calibration and real inference, then hit its frozen 2,714-second function timeout at **20:26:37 UTC**, during zero inference (last durable progress 35,232/49,080). My duration forecast undercounted verification/preparation and frame I/O. This was a timeout, not another platform-redelivery finding. Exit 1; terminal/zero containers at 20:26:47.275502. Complete stages persisted and verified; partial zero work was not reused. Charge bound $2.715989037845592.

Lead pre-approved a fresh $1.50 recovery. Press03 (`ap-ZwXMMponOGgpGdd1IgiVKa`) created at **20:38:59.917312 UTC**, reused the original completed stages with their identities/hashes, and performed only zero inference plus paired scoring. It constructed identical zero tensors/batch shapes directly, avoiding irrelevant native frame reads. The original scoring code and TRAIN thresholds were unchanged. Synthetic equivalence includes the tail batch. Source `f439ba8`, frozen deployment `778787b`, runner SHA-256 `048454a12533122aab2b88d7c5e6f75363df1db522ad382e0218d4775b8433b1`; 24 tests pass. Guard enforcement/gate unchanged. Worker 110.545 seconds, exit 0; terminal/zero containers at **20:41:09.569878 UTC**. No automatic paid retry or fit occurred.

All collected files match their Mac hashes. Local full arrays and row identities: `data/idm/cloud-20260927/{press02-result,press03-result}/`. Durable report/receipts: [evidence packet](../evidence/idm-press-diagnostic-result-20260927/report.json).

| Artifact | SHA-256 |
|---|---|
| Paired report | dd09f3b33b2a27c458fca580bec8da7753b38584d73950aa35a4fe14efed6a98 |
| Press03 final/teardown | b83896db74caf831c47cb2c43e29a1fba1bde3f51a4669c8a83837f860cd1b16 |
| Press02 final/teardown | 7b5cc6897deb68c71558d3017eaa07aa2e60fea9034e6f02b76fd978857added |
| TRAIN stage receipt | 15c871695b2874ed680e6e89ef22a7346a14ca79fa824ea536f89f976c875202 |
| Real stage receipt | bdb8ffb1a13a931daf57aa2aade01eafeb31ad367aa20db0b0cb25712f5ee45c |
| Zero stage receipt | 33ca2077ac7481792830467e2ec9e9dd0d81ad135b708f3c2fa410904c2cf9da |
| Zero probabilities | f451e02cbef3c4097e60839678400099d2161c2fc96131b2d5c8d337f5bcdca3 |

## Budget and next consumer

Conservative settled allocation bounds (not invoices): SSL **$0.9568266506762123**, press01 **$1.798725950444412**, press02 **$2.715989037845592**, press03 **$0.8643344297040367**. Total **$6.335876068670252 of $25**, alert $20. Every app is terminal with zero containers. **No outstanding paid hold remains.** Exact timestamps, app IDs and receipt hashes are in [cost-report.json](../evidence/idm-press-diagnostic-result-20260927/cost-report.json), SHA-256 `6cb15e491cd6d5a483455edb67187d06e3662e0f23d42282f0dfd48eea26d0b6`.

Next: execute the [complete range refit plan](idm-expanded-corpus-plan-20260927.md): all eight eligible ranges, 166.926104 counted minutes, including the three missing native stores (86.390135 minutes). Decode waits for the camera sitting to close and an explicit decoder/Mac-slot release. Corrected -5 accepted-a1 landed at `951cd9e`, 342.399986311 accepted seconds; use new steps `2c25a3fc…` and demo `f0fa8894…`, never the historical Mac tables. Together with accepted -6, the currently admitted range-plus-match total is **176.926937 minutes** before context trimming. -4 remains held, and the lead's refit trigger includes its accepted-a1. No new source is decoded during the camera sitting. The seconds-context press-head comparison remains necessary; calibration alone leaves inadequate precision.

Linear delivery, via lead because advertised Linear calls returned `Unknown tool` in this session:

> Current result: EXPLORATORY fixed-weight press diagnostic complete. TRAIN thresholds raise precision to Combo 42.2%, Jump 35.7%, Web 42.7%; real F1 .482/.384/.429 exceeds rate-matched chance .010/.062/.038, while zero visuals emit no events. Recall falls; precision is still insufficient. Combo's 14-onset dev session remains support-limited. Paired report SHA dd09f3b3…, all four apps terminal/zero, cumulative bound $6.335876.
>
> Remaining acceptance: no validated button labels or Gate 2 pass; seconds-context evidence and range-to-match/live-to-replay transfer remain open. Full eligible paired corpus has not yet been refit.
>
> Next action, idm-owner: build the three missing range stores after the sitting/slot release, consume only corrected accepted match receipts, and run the expanded refit when -4/-5 accepted-a1 and all stores are ready. Parameterised camera-demo renderer is a separate queued code deliverable. Lead updates VUH-1353 and reads it back; no Linear write is claimed here.
