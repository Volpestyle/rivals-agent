# IDM beta-NLL camera loss: toward default-on, 2026-09-25 (VUH-1353)

The pre-registered tests that decide whether the beta-NLL camera loss (landed behind `--beta-nll` in `d10f583`)
becomes the IDM's default: a second fold with three seeds per loss, a pitch non-inferiority margin, per-regime
calibration and abstention bounds, and the gate-1 re-run at scope. Pre-registered in `docs/lanes/inverse-dynamics.md`
(sections frozen here as `idm-partA-prereg.md` 42beb90e… and `idm-partB-prereg.md` 4247102d…, committed in `e31b595`
before any run). Owner: the inverse-dynamics lane (scoreboard-fix). Code `fe5c9ca`; Mac, MPS, 3 epochs per run.

**A1-A3 result (`idm-beta-nll-2.md`):** on fold 205528 held out, beta-NLL learns yaw direction on 3 of 3 seeds
(0.937-0.971 held out); across both folds beta is 6 of 6 and the plain loss 2 of 6. Pitch is non-inferior on the
pooled mean (beta 0.776 vs plain 0.793, within the 0.05 margin) but paired differences span -0.157 to +0.209: pitch is
seed-fragile on 205528 under both losses. Calibration: extrapolated-band coverage distance from nominal 0.219 -> 0.073,
calibrated 0.109 -> 0.075; the 1/3 degree abstention bounds hold on 6 of 6 beta runs against 2 of 6 plain. The plain
seed-0 weights at `fe5c9ca` are bit-identical to `loso-205528` at `1df31e7`. All 24 run and prediction hashes verified.

| File | sha256 |
|---|---|
| `*idm-beta-nll-2.md` | `20b6283f236b4b4f3cce1cea1f0782b4c4b171e95c70954f33321b8c9605d01c` |
| `*idm-partA-prereg.md` | `42beb90e34d321e9391e2ad90f80b239e5b3a66d21f3cca2315cc8763280f098` |
| `*idm-partB-prereg.md` | `4247102d1e328b134a51be6d526c18b831c7c4d5daee15abe60944a6230baeb2` |

**B result (`idm-edge-input.md`, sha256 `0dba8450239d6835c1e7c820e1c235cc5d025ba721539e5f2d9393ec250988b7`):** HUD crops at t1+8 and t1+16 added to the input (fold 051828, plain loss, seed 0, branch `idm/edge-hud-lag-20260925` @ `b3112fc`): amazing_combo clears chance-at-rate by +0.089 F1 (today +0.030; AUC 0.797 -> 0.877), movement keys unchanged, jump F1 0.104 -> 0.069 (within the 0.05 tolerance; its margin over chance nearly gone), web_swing loses its margin. One seed, one fold: the pre-registered replication (seeds 1-2 on 051828, seeds 0-2 on 205528) follows the gate-1 re-run.

**A4 result (`idm-beta-nll-2-a4.md`, sha256 `0faf5556cc45aa808208fdbbd2047ae965e44a384b3707cfd1f96c8428a576a4`):** gate 1 on 171533, beta-NLL against the plain loso-171533 re-scored by the same fe5c9ca harness. Yaw better on every figure (moving median 0.352 -> 0.263 deg, direction 0.964 -> 0.995, 1 s sum 3.35 -> 2.84 deg, abstention 3.7% -> 0.3%, extrapolated coverage held). Pitch is the cost: moving median 0.508 -> 0.568 deg, extrapolated 1-sigma coverage 0.734 -> 0.604 (the stated std is too tight). Edges at the 0.5 threshold incidentally better (one seed, reported not claimed). Lead's decision: not default-on with the pitch regression; the next pre-registered test is beta on yaw only, plain NLL on pitch.

Pending in this folder: the edge-input replication (`idm-edge-input-2.md`) and the yaw-only test (`idm-beta-yaw-only.md`).
