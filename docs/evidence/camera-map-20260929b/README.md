# Alt camera map evidence, sitting alt-cam-20260929b

Evaluator, VUH-1384, 2026-09-29. **The candidate now contains all 14 signed yaw knots. Focal, all pitch rates in degrees, latency and interpolation remain explicit holes. It is not a complete usable controller map and is not accepted for live input.** The [candidate data](../../../agent/camera_maps/alt-247-124.json) uses the landed `rivals-camera-map-v1` format. No acceptance registry entry was added.

The [sitting record](../../../data/calibration/alt-cam-20260929b/SITTING.md) is the authority for what ran. All eight successful schedules were analyzed; yaw-04 produced no input and its replacement yaw-04b supplies the low yaw measurements. No new game input, training, GPU or paid compute was used. James closed game and OBS; process absence was checked before every native decode.

## Yaw: native full turns, separately by sign

Values below are magnitudes in degrees/second; the column names carry the command sign. Brackets are conservative endpoint sampling/annotation bounds, **not confidence intervals**. The number after the semicolon is the number of complete turns between the measured endpoints.

| Absolute RX | Positive: rate [bounds]; turns | Negative: rate [bounds]; turns |
|---|---|---|
| 0.1 | 19.84 [19.46, 20.14]; 1 | 19.84 [19.46, 20.14]; 1 |
| 0.2 | 59.03 [57.60, 61.28]; 2 | 59.94 [58.18, 61.94]; 2 |
| 0.3 | 99.30 [96.81, 101.95]; 4 | 99.19 [96.00, 101.05]; 4 |
| 0.45 | 154.00 [151.40, 156.47]; 7 (prior sitting) | 159.10 [155.08, 162.58]; 7 |
| 0.6 | 218.17 [214.05, 223.10]; 11 | 218.33 [214.05, 223.10]; 11 |
| 0.8 | 298.11 [291.89, 304.23]; 15 | 298.35 [291.89, 304.23]; 15 |
| 1 | 357.73 [350.77, 364.80]; 19 | 358.14 [350.77, 364.80]; 19 |

`yaw-results-final.json` is the final machine-readable count record. +0.45 is retained unchanged from the [earlier seven-turn result](../camera-native-turn-20260929/README.md); it was not remeasured in this sitting. Do not symmetrize it with -0.45. Settings/scene/day-to-day response and the different source remain part of that comparison.

Native 2560x1440 images were retained at 8 Hz. In this indoor scene the adjacent green portals, central cylinder/table, columns and black three-panel banner form a unique ordered world traversal. Green-portal centroid crossings nominate returns, and the retained return galleries identify that same complete view at every counted recurrence. General feature matching alone produced false matches on repeated wall textures; those unqualified matches were not counted. Full-background alignment and the portal sequence reject that alias. The mean is `360 * turns / elapsed`. Bounds use the complete 0.125-second sampling brackets and an additional 0.125-second allowance at each endpoint for animated portal-centroid/registration placement. Interpolated times are point estimates, not a claim of sub-frame accuracy. The values describe the observed average steady turn, not instantaneous acceleration or behavior in every camera state.

**Low-strength correction:** the initial portal-only shortlist had one crossing at each of +/-0.1, which is insufficient to count a turn between two portal crossings. Matching a post-transient initial view to its later return recovers one full turn in each direction: reference PTS 977.546 -> return bracket [995.671,995.796], and 998.046 -> [1016.171,1016.296]. Both traverse the complete room sequence. Each averages about 19.84 deg/s. Thus the earlier provisional "no complete turn" report was wrong and is superseded here. Neither value is zero or an interpolation. One turn gives no between-turn repeatability estimate; +/-0.2 have only two turns each. If a future low-value run has no complete return, this record supplies no authority to substitute zero or a guessed fraction of a turn.

Inspection covered all return-gallery frames, both complete low-yaw contact sequences, representative full room traversals from the other runs, and the low-yaw reference/return pairs. All extracted native samples remain available; this is not a claim that every retained image was individually inspected. On D:, `low-yaw-return-pairs.jpg`, `count-yaw-*.jpg`, the run `contact-*.jpg` files and their native indices are pinned by `artifact-index.json`.

## Pitch: sign and clamp evidence; angular rates still unknown

Every declared signed RY value shows the expected camera direction: positive looks up (static scenery moves down), negative looks down. The paired pulses return close to their earlier view. None shows an observed clamp stop. For every pulse, all four analyzed 60 Hz frame pairs near the end of the commanded interval retain motion in the commanded sign; the 0.1-second contact sheets also show continued movement and the subsequent neutral plateau. This establishes no clamp encounter in these pulses, **not** a measured clamp angle or guarantee from an arbitrary starting pitch. Never divide a clamped total displacement by the full command duration to estimate its unclamped speed.

`pitch-results.json` retains command times, frame-motion thresholds, onset brackets and late-motion counts. Forward/backward checked LK tracks measure the following *scene pixel velocities*, at 1280-pixel width. They are useful diagnostics and explicitly **not degrees/second**:

| Absolute RY | Positive scene dy px/s | Negative scene dy px/s |
|---|---|---|
| 0.1 | 65.3 | -66.4 |
| 0.2 | 202.4 | -213.7 |
| 0.3 | 381.1 | -382.2 |
| 0.45 | 610.1 | -612.1 |
| 0.6 | 834.7 | -847.1 |
| 0.8 | 1144.3 | -1149.1 |
| 1 | 1407.9 | -1408.3 |

The script masks HUD and hero regions, samples native frames at 60 Hz, excludes the initial 80 ms and final 20 ms for the motion summary, and retains track coordinates and frame pins. The recorded 10th-90th percentiles describe frame variation, not uncertainty bounds on an angular rate. Perspective, depth and the third-person camera orbit prevent substituting `pixel_velocity / guessed_focal`. Historical mouse pitch gain is also explicitly unknown; equal sensitivity numbers do not establish it. Accordingly all 14 pitch degree knots are null/missing in the candidate; their notes retain the measured sign and scene-motion result.

## Focal and the current mouse gain

**James's verbal attestation:** at **15:45 CDT on 2026-09-29**, the lead relayed his direct answer, **"yes all is the same"**, to the question whether the alt account still uses mouse sensitivity **1.89/1.89**, with smoothing and acceleration unchanged from the accepted alt gain calibration. This is a sitting-specific verbal settings attestation, not a new measurement. The accepted historical record says smoothing **on**, acceleration **on**, factor 1.00 and threshold 1; "unchanged" does not mean off. [gain-provenance.json](gain-provenance.json) pins that record and the independent left-turn check.

The historical horizontal gain is 0.0330738 deg/count. Its original full-turn closure reported about 0.02% precision; the later signed/speed check was within its 0.08% criterion. The diagnostic call here uses a conservative 0.08% relative allowance, which is not a statistical interval or proof of current hardware/geometry error. The attestation closes the settings-provenance gap as far as an attestation can; it cannot establish landmark depth, image-edge placement, level pitch or endpoint counts.

Both new ledgers are complete, cleanly stopped, with zero queue drops and raw-input errors. There are repeated roughly 2,800-count swings in the second recording and the first recording's tail. They are valuable retained data, but the native audit did not establish six level, far-point edge-to-edge passes with bounded count endpoints. The alternating views show a broad rock outcrop and different foreground panels; whole mouse-burst endpoints are not verified crossings of one specified point at the two image edges. Vertical mouse activity and endpoint-view changes also need qualification. The first recording's earlier tail includes navigation/jumping and is not a stationary substitute. Some end views retain portions of the same outcrop; sparse endpoint feature matches do not establish a far point or a valid geometric bound.

The unchanged `focal_from_counts` was invoked for the first six substantial alternating bursts in each recording's sweep section, with the missing far/level/endpoint qualifications kept explicit. **Both calls refused**, with `inspected far landmark and level camera required; near control stays separate`. [focal-counts-attempts.json](focal-counts-attempts.json) preserves those raw totals and refusals. No booleans or endpoint error bars were invented to pass the helper. Therefore no count-based focal candidate is installed.

A bounded cross-check reused the earlier circular-orbit model on the richer indoor yaw footage. Six fixed 0.5-second sparse SIFT windows retained only 0-4 full tracks and were refused. Four new 0.6-second native windows, tracked at 60 Hz, yielded 17/26/16/3 tracks. The first three conditional fits preferred 685/630/640 px, with actual pixel RMS 7.14/1.07/0.62 respectively; the fourth had too few tracks. Their best-plus-0.5-pixel focal profiles were [580,850], [595,725] and [570,720]. These are **conditional optimization profiles, not true-error bounds**. The model assumes constant yaw rate, square centered pixels, fixed pitch and rigid circular orbit; inspected support includes architecture and repeating lit wall texture. The failures and broad profiles remain. Neither 630 nor 640 is promoted into the map, nor used to fill pitch degrees. `orbit-dense-results.json` and the pinned native overlays preserve the diagnostic.

## Timing, candidate checks and next consumer

The input-ledger composition timestamps and actual returned pad-report times locate each schedule in the original video. The provisional muxer anchor is +0.021 s. Native return intervals do not depend on that constant offset. Both ledgers say `capture_latency_calibrated=false`; the pitch onset brackets straddle the report timestamp under this mapping. That does not establish zero latency or an independently measured pad-to-game/display delay. Latency stays missing. Interpolation also stays missing: only declared knots have measurements, and no off-knot model has been validated.

[verify_candidate.py](verify_candidate.py) is a separate read-only check of all new values, turn arithmetic, bounds, retained +0.45 value, live refusal of every candidate yaw knot, missing pitch/scalars, and refusal of interpolation/inverse/controller construction. It passes. The existing camera-map and focal-analysis tests pass **77 tests with one deliberately deselected stale placeholder test**. Running that test separately confirms its known failure: `test_alt_candidate_is_only_usable_offline_and_never_mirrored` still expects -0.45 and +0.3 to be missing and only one present knot. `tests/test_camera_map.py` is pinned by `live-loop-rebind-20260929/receipt.json` and remains untouched, as the lead explicitly instructed. **Live-loop owns the test update when its integration patch is applied against an accepted map, with its own exact-byte review.** This delivery does not claim an entirely green unchanged suite. `validation.json` and the external failure log retain the checks.

The lead owns VUH-1384 publication, acceptance and the next consumer decision. The whole map cannot be registered as complete on these measurements: focal, pitch degrees, calibrated latency and an interpolation model are still absent. Do not silently replace those fields with the diagnostic fits or planning defaults. Any proposed live fallback is a separate lead-owned, reviewed scope; this candidate authorizes none. No repeat of the already measured yaw schedules is requested here.

## Source and artifact retention

- `C:\Users\volpe\Videos\2026-09-29 15-03-44.mkv`: SHA256 `5708ee73056eb1f206326f7c82e8ce742c3dcdf84ef965354ffa719294e8fdfe`, 8,301,640,227 bytes; runs plus sweep tail. Ledger `20260929T200344-560Z-137068-1`.
- `C:\Users\volpe\Videos\2026-09-29 15-27-08.mkv`: SHA256 `72e8b401d6a7cc4183b692eb55d33b9470d980323c597022a0971d638a02d514`, 379,805,535 bytes; dedicated sweep. Ledger `20260929T202708-927Z-137068-2`.

All decoded images, contacts, logs and executable probes stay under `D:/rivals-agent-evidence/camera-map-20260929b/`. Native images retain 2560x1440 spatial resolution as JPEG q2; they are compressed evidence, not lossless pixel copies. `artifact-index.json` pins the retained artifacts, including source/command metadata and unsuccessful diagnostics. `timeline.json` pins the sitting manifests/actuator reports and ledger files. Native source hashes were streamed in 1 MiB chunks. One decoder ran at a time, BelowNormal, two codec threads and one filter thread, with a 3 GiB working-set stop; maximum observed decoder peak was under 263 MB. OpenCV/BLAS analysis was single-threaded, with bounded frame batches.

The initial pitch-02 extraction stopped on a 419-file/420-timestamp mismatch. It is retained as an unused failed diagnostic. All four authoritative pitch extractions were redone in `pitch-*-pts/` with a 1 ms encoder timebase and timestamp filenames checked directly against showinfo: 540/420/240/540 frames. No uncertain sequence-number pairing from the failed extraction enters the pitch analysis. The separate dense orbit windows use the same timestamp-filename route. All owned decoding/analysis jobs are finished.
