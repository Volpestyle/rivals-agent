# Reader and frozen full03 support: development result

Owner: idm-owner / VUH-1353. Observation: 2026-09-28 UTC. **EXPLORATORY; qualification remains blocked.** The accepted proposal was implemented and the bounded $0 Mac pass completed. The reader candidate did not repair the demonstrated replay failures or detect the two known shifted arrivals. A genuine live competitive control now demonstrates correct refusal. A fixed yaw-support calibration artifact was produced; it is not evidence of accuracy on a new source and is not wired into labeling.

## Reader result

| Development check | Raw reader | Candidate | Meaning |
|---|---:|---:|---|
| 12 live timer frames | 12 correct, 0 unknown, 0 wrong | same | Existing control preserved |
| 12 replay timer frames | 10 correct, 2 unknown, 0 wrong | same | Both demonstrated refusals remain |
| Two corresponding feed shifts, live/replay | Owner-bracketed native events | 0 detected in either window | Geometry candidate fails onset task |
| 12 live competitive native frames with a team clock | Clock readable | 12 `competitive_unsupported`; no replay decisions | Genuine refusal control passes |

The replay refusals at 137.504/142.504 s remain `None`. The first has an ambiguous leading glyph against a bright background; the second fails the colon score (about 0.679 against 0.70). Broad-background removal did not resolve them, and no glyph/uncertainty threshold was loosened. In the two 60-frame fine windows, both implementations read 30 old/25 new/5 unknown and 13 old/0 new/47 unknown respectively. Timer labels between inspected brackets are continuity-derived, not independent frame-by-frame labels.

Feed geometry finds the intended region in 3/4 live and 2/4 replay feed-bearing uniform frames, but fragments entries and also detects unrelated regions. The previous row moves before the new row has finished appearing; a single-frame added-row check misses both real arrivals. Every layout result remains unknown because positive Quick Match evidence has not been established. A readable team clock never implies replay. No complete-match certificate was constructed from these sparse windows.

Owner inspection, recorded before the fine candidate read, brackets the two paired row movements:

| Entry | Live last unshifted / first shifted (s) | Replay last / first (s) | Replay-minus-live possible offset (s) |
|---|---|---|---|
| S.t4rfir3 → ShadowFox594 | 139.688 / 139.696 | 109.079 / 109.088 | -30.617 to -30.600 |
| cowboyboopbop → Yoitscolin | 140.954 / 140.963 | 110.338 / 110.346 | -30.625 to -30.608 |

The two timer changes are bracketed at (137.529, 137.538] and (142.638, 142.646]. These are encoded PTS brackets, not an alignment fit or physical press-lag measurement. Two events do not meet the registered support floors. No K1–K3 or T1–T3' pass is claimed.

The new competitive sample is native 2560×1440 gameplay at 322.504 s from the already authorized development recording `22-48-05`; its hash-pinned image is [0005.png](reader/competitive-control/0005.png). It shows a team-clock HUD without a spectator roster/prompt. The corresponding test exercises the actual timer and candidate without mocking either. The other eleven fixed samples agree. This closes the missing genuine competitive refusal-control coverage, not competitive layout support or camera calibration. Incidental desktop/media images from the earlier sample are not published here.

## Support calibration

Frozen full03 checkpoint SHA256: `f681da9f3a4b8db6f7d19566172b02db776e4bcfac3381be744786179aa55dde`. MPS inference only. No weights, estimated yaw, existing standard-deviation threshold, pitch treatment or action vocabulary changed.

Exactly full03's eight TRAIN ranges plus -4a1/-5a1/-6 supply 5,632 selected feature rows (512 each) and 654,722 eligible logged rate rows. The two original range-development sources supply 8,192 feature rows (4,096 each). No later-match, SPIDEY, validation or sealed payload was read. [rows.json](support-a3/rows.json) was frozen before pixel extraction, using chronological eligible-index spacing, no padding and valid contexts only. The logged rate population includes eligible target rows without a complete model context; it is deliberately larger than the context-valid fit population.

TRAIN means/population variances of the fixed 128-dimensional motion embedding define sqrt(mean squared standardized residual), with variance floor 1e-6. The fixed linear quantiles produced:

- TRAIN p99.5 absolute yaw rate: **635.0169472996611 degrees/second**.
- Range-DEV p99 standardized feature distance: **3.0088562451457173**.
- DEV feature tail: **82/8,192** (58 from 171533; 24 from 205528).

This distance is not a probability of correctness. Its percentile does not establish future rejection rate, calibrated uncertainty or usable-shard coverage. Withheld yaw is `None`, never zero. Reason counts overlap. Predictions on retained rows are byte-equivalent in value to the original prediction.

Per-source results below report coverage before pooled metrics; errors are degrees per predicted interval. Raw and masked errors use their respective answered rows, so their difference is conditional selection, not improved predictions.

| Source | Role | Answered / sampled | Moving answered / sampled | Raw MAE | Masked MAE |
|---|---|---:|---:|---:|---:|
| 20260923T051828-422Z-33696-1 | train | 508/512 | 200/203 | 0.2785 | 0.2747 |
| 20260923T171533-187Z-33696-5 | dev | 4031/4096 | 1100/1108 | 0.1594 | 0.1592 |
| 20260923T200129-346Z-33696-6 | train | 506/512 | 191/194 | 0.242 | 0.2288 |
| 20260923T205528-900Z-45572-3 | dev | 4067/4096 | 1637/1648 | 0.2642 | 0.2622 |
| 20260924T232304-170Z-12024-1 | train | 509/512 | 211/212 | 0.2579 | 0.2585 |
| 20260925T021320-371Z-7804-1 | train | 510/512 | 203/204 | 0.2311 | 0.2319 |
| 20260925T025230-605Z-7804-2 | train | 510/512 | 186/186 | 0.2162 | 0.2168 |
| 20260926T045729-166Z-79780-1 | train | 511/512 | 208/208 | 0.2823 | 0.2825 |
| 20260926T035932-508Z-63684-14 | train | 511/512 | 228/228 | 0.2833 | 0.2838 |
| 20260925T203745-207Z-49728-2 | train | 511/512 | 183/183 | 0.2738 | 0.2743 |
| 20260927T051206-888Z-150600-4 | train | 505/512 | 234/239 | 0.3953 | 0.3953 |
| 20260927T052001-827Z-150600-5 | train | 506/512 | 208/212 | 0.3547 | 0.3551 |
| 20260927T053118-260Z-150600-6 | train | 509/512 | 203/205 | 0.3652 | 0.3652 |

On DEV 171533, still MAE is 0.0751 raw → 0.0760 masked; moving MAE 0.3871 → 0.3810. On DEV 205528, still MAE is 0.1273 → 0.1277; moving MAE 0.4677 → 0.4618. Moving direction agreement is unchanged (0.9973 and 0.9878). Masked one-standard-deviation coverage remains imperfect: calibrated/extrapolated 0.7693/0.7081 and 0.7539/0.6754 respectively. All strata, per-source rate quantiles and refusal reasons are retained in [report.json](support-a3/report.json).

**No contiguous one-second or quarter-second windows exist in this sparse selection.** The report has zero window counts; distant rows were not joined. No one-second accuracy result follows from this pass. Still-row conditional error is slightly worse, and there is no fresh-source accuracy or range-to-replay transfer test here.

Artifact [support.json](support-a3/support.json) SHA256: `31a8e4a9bbdd55efa04c209b8673b6e8aa8fc4b6ce45cd2b0b226f7a3c4e0fbc`. Result JSON SHA256: `77e50b5b608357e60a5b2207ae2d7c6c47abe56a5b59e2a989b38a9f5399d9bc`. Manifest SHA256: `2e234edc89daacd5c0c79f0087dd71aa5ad9b1051acbe21df753bdcdc6699e49`.

## Execution, fixes and verification

Implementation/proposal commit: `45676591fafcadca9923ddbef516a257c471c770`; provenance corrections: `c2c7899`, `7085fd9`. The old production/archived readers remain unchanged; new modules are separate and unwired. Synthetic controls test glyph ambiguity, entry identity/displacement, incomplete/forged/tampered scan certificates, hidden-clock veto, support pin/shape/finite/rate boundaries, model identity and provenance roles. Final offline suite: **34 passed** (four named test modules; exact command in verification record).

The first isolated support closure was missing transitive range-policy imports; this was caught before invocation and added to a separate pinned source closure. Two support attempts then failed during metadata preflight, before pixels: the first incorrectly expected checkpoint provenance to list only TRAIN; the second incorrectly expected range-DEV target headers to say `val`. The checkpoint records all thirteen sources, and range-development headers remain registry `train`. The final validator binds experimental roles to full03's original immutable manifest SHA256 `42494717650293cc4b77add3721d5168c20781e6b98ca275443824656e055580`, plus every target/store identity. It requires exactly eleven experimental TRAIN and two held-out sources. No development data was promoted into fitting/calibration statistics. Failure logs and correction inventories are preserved; no source was reselected.

Claim: 23:31:37.563Z. Reader decode: 296.174 s; candidate read: 5.373 s, with owner native inspection between them. Original support phase began 23:40:40.129Z; the two failed preflights and corrected run retained its original deadline. Final support execution ended **23:50:19.530Z**, exit 0 (78.374 s scientific script; store verification 42.205 s and inference 18.877 s). Nice/two-thread serial execution stayed within both 30-minute bounds and the 60-minute reservation. No new GPU/peak-memory utilization claim is made.

Collection at 23:51:02Z found no owned live PID. Memory pressure reported 83% free; swap 11,866 MiB versus 11,898 MiB at start. The Mac slot was explicitly released to herdr-lead at approximately 23:52Z; no new compute is queued. **Cost $0.** No training, paid action, source deletion or SPIDEY access occurred.

All **777** collected files were independently byte/hash verified on the PC. Feature means, variances, p99 cutoff and DEV tail counts were independently recomputed exactly from retained arrays; [verification.json](verification.json) records that check. The rate quantile is the runner's pinned result; this collection check did not reread target tables. Full 112,116,172-byte collection archive SHA256 `078a157acc8dfc703dc39a8abbe72be6f8d90ba38e7e56d085f283108b9264db` remains at `data/idm/reader-support-20260928/collected.tar.gz`, with the full collection also retained on Mac. [collection.json](collection.json) pins every frame, feature and prediction file. This Git packet includes bounded native contacts, control, labels, reports, manifests, failures and reproduction scripts; it does not duplicate all media/arrays. `SHA256SUMS.json` pins the delivered packet.

## Remaining acceptance and next action

This completes the accepted development experiment, not source qualification. The reader result is negative; full03 stays the baseline and the later Mac checkpoint stays unpromoted. Before fresh qualification/admission, the changed reader/alignment/support boundary needs its required independent review. No selection based on later-match results is authorized.

Open dependencies remain: positive mode recognition and reliable arrival timing, V-Q's missing replay (lead routes it; V-C cannot substitute), the independent cut-acceptance receipt, a defensible angular scale/FOV argument, and the registered reader/event support bars. James's SPIDEY permission is recorded, but a clip still requires its exact `replaced` log entry and reviewed source-use admission before any result is used. Both sealed Gate 2 pairs remain closed.

Next owner action is to hand this negative reader/readiness result and frozen calibration artifact to herdr-lead for VUH-1353 reconciliation and the bounded next decision. There is no autonomous follow-on run, refit, source labeling or changed Gate 2 bar in this delivery.
