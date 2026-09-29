# Existing-evidence focal check, 2026-09-29

Evaluator, VUH-1384. **Focal remains unknown. Keep the 60-90 second logged-mouse sweep in the next sitting.** The accepted +0.45 yaw count provides an angular clock, but a bounded attempt on the same recording did not isolate a reliable projection scale. This is an unsuccessful exploratory diagnostic, not proof that every possible reconstruction from this video must fail. No calibration value, rate-map change or live input results from this work.

## What existing records establish

- [September 26 independent review](../../../data/calibration/alt-20260926/FOCAL-OFFLINE-review-20260926.md): 640 px at 1280 width was accepted for planning only. Count-based image fits clustered near 600, with substantial scene/depth dependence; neither number was accepted for degree conversion. The third-person camera's orbit confounds a rotation-only fit.
- [September 27 alt calibration attempt](../focal-calibration-20260927/RESULT.md): 52 continuous tracks, all 20 delay/smoothing fits refused. The best 625 px diagnostic had 3.64 px horizontal and 3.84 px vertical RMS. Its narrow optimization profile did not include model/gain uncertainty.
- [September 27 TRAIN attempt](../focal-train-20260927/RESULT.md): three widely spaced moving-combat frames had no complete tracks. No new TRAIN or sealed source was opened in this check.
- [September 29 native full turns](../camera-native-turn-20260929/README.md): 153.893 deg/s, endpoint bounds 151.397-156.473, independent of focal. That average does not establish constant angular speed within each turn, camera pitch, orbit geometry or dynamic FOV. The existing two-frame homography probe was already inconsistent.

## New bounded attempt

All image output and executable probes are in `D:/rivals-agent-evidence/focal-orbit-20260929/`; [artifact-index.json](artifact-index.json) pins them. The unchanged closed OBS source is `C:/Users/volpe/Videos/2026-09-29 00-45-47.mkv`, SHA256 `eafb247e1a1d025c0aad795384a5c188078b13d52f0e8924409b0de534c0306a`. Source hash was verified by streaming 1 MiB chunks.

The new diagnostic allows a circular camera orbit, a shared shoulder offset and fixed pitch, rather than assuming pure rotation about the camera center. For yaw angle `a`, a static point's coordinates before pitch are `(A*cos(a)-B*sin(a)+s, H, A*sin(a)+B*cos(a)+1)`. Orbit radius sets an arbitrary length unit. At each focal/pitch grid point, linear least squares eliminates each point's position and the shared offset; the reported error is actual pixel reprojection RMS per coordinate. This is a conditional model, not full bundle adjustment or a certified camera model. The focal grid was 400-850 px in 5 px steps, pitch -15 to +15 degrees in 1 degree steps, with centered square pixels and constant yaw speed assumed.

1. `probe.py` tested twelve fixed 0.5-second windows in the existing 8 Hz PNGs. Mutual SIFT ratio matches yielded only 0-5 full tracks per window; none met the six-track minimum. No focal was fitted from these windows.
2. With game, OBS and other ffmpeg processes absent, one 2.5-second native CPU decode retained 75 unscaled 2560x1440 PNGs at 30 Hz, PTS 176.004-178.471. Four fixed 0.4-second windows used 13 frames each. `dense.py` obtained 1, 1, 0 and 10 full SIFT tracks. The only fitted window preferred the search boundary, 850 px, with **21.89 px RMS**. Inspection shows its support on foliage, not certified static landmarks.
3. `lk.py` reused those same PNGs with the existing forward/backward LK tracker from `scripts/fit_focal_train.py`. The same windows retained 3, 0, 3 and 38 tracks. The only fitted window preferred 780 px with **7.95 px RMS**; its best-plus-0.5-pixel profile spanned **690-850 px**, still touching the grid boundary. The inspected overlay contains some architecture but predominantly foliage/plant-bed features. Forward/backward consistency does not certify stationarity. No residual-based point deletion was used to rescue the fit.

Neither 780 nor 850 is a focal candidate. Those profiles are not confidence intervals or valid bounds on the true focal. The errors and scene support fail to establish the model before adding the accepted yaw-rate uncertainty; widening for that uncertainty would not repair the missing validation. The short sample has only one yaw sign and cannot establish transfer to pitch, swing, sprint or other camera states.

Eight noiseless synthetic cases recovered focal 465/600/640/760 in both yaw signs with sub-1e-7-pixel RMS (`synthetic.json`). This checks the diagnostic algebra only. All four SIFT first/middle/last overlays and the fitted LK window's overlay were visually inspected. They remain alongside the native frames for audit.

The initial dense driver stopped after a successful decode because showinfo logged two buffered frames beyond ffmpeg's output cutoff (77 log entries, 75 PNGs). `dense-v1.py` preserves that driver. The corrected driver selects only PTS before 178.5 and resumed with `--reuse-decoded`; no second decode was run. Exact commands, showinfo, input hashes, tracks, result profiles and code hashes are retained. The original 8 Hz inputs were checked against their accepted artifact index.

## Disposition and next consumer

The next sitting [README](../../../data/calibration/alt-cam-20260929b/README.md) retains six slow, far-landmark edge-to-edge mouse sweeps, three per sign, with native video and the input ledger. Use settled endpoints and verified current mouse-count gain; do not substitute the historical gain's quoted precision for a current uncertainty assessment. The existing `focal_from_counts` contract records endpoint count uncertainty and requires consistent repeats. This costs an estimated 60-90 seconds; the full sitting target remains 9-11 minutes with it. It is a future human action for the lead to arrange, not authorization to send game input now.

No further focal compute is queued. All three diagnostic status receipts are done. Work used BelowNormal CPU processes, one decoder with two threads, OpenCV/BLAS single-threaded and at most thirteen native frames loaded together for tracking; no GPU or paid compute. Decoded output stayed on D:. Runtime, frozen review packets, analyzer and calibration map are unchanged. The lead owns publication to VUH-1384.
