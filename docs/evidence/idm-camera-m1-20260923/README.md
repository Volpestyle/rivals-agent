# Camera estimator: M1 live/replay windows, regression and audit (VUH-1353)

Numbers and scripts only; no frames. The measured bytes are `perception/camera_motion.py` sha256 `4b5714b8…`:
option (i), review re-check B2 and B3, and lead decision (a), which refits the centre outliers and withholds
repeated frames. The landed file (`5c4e1fb2…`) differs from them only in comments (final check C1/C2).
Everything ran offline, below normal priority, and only while no other decoder was running and at least 4 GB was
free. The design and the reading of these numbers are in `docs/lanes/inverse-dynamics.md`, "Measured".

| File | What it is | Bytes measured |
|---|---|---|
| `measure.py`, `measure2.py`, `plan.json` | 8 replay windows (DayMR replay, file t 597–1955 s) and 4 live windows (051828 t 39, 117, 245, 347), 3 s each at 120 fps, streamed at 1280×720 grey. One spectator-UI mask for both domains, a per-window overlay, and the pair and window rules. `M1_ONLY=live` runs the live windows only | — |
| `analyse2.py` → `m1-live-results.json` | Live: the pair rule against logged mouse counts, and centre-sourced (B3) yaw against mouse-derived yaw | `4b5714b8` (landing) |
| `m1-replay-results-option-i.json` | Replay: validity, rates, kink autocorrelation, pitch lattice with the random-period control. Per the lead, the replay windows were not rerun for (a) | `3220a4db` (option (i) plus B2 and B3) |
| `regress_i.py` → `regress-landing-results.json` | The reviewer's method on the l2 proxies (baseline1/3): HEAD `2920ceb` against the landing bytes on the same pairs. It covers the full no-command stratum plus 60 sampled pairs per other stratum, and lists every withheld pair (`REG_OUT` names the output) | `4b5714b8` |
| `audit_sheets.py`, `audit_baseline{1,3}.json` | Review re-check B1, pre-registered in the script's docstring: every withheld no-command zero (10 and 9, the whole population), labelled by eye still or moved, with frame sha256. Labels on pairs unchanged from option (i) are carried over and marked | `4b5714b8` |
| `live-moved-zero-kept.json` | The 7 live pairs where the mouse moved ≥ 60 counts and the landing bytes still report a zero | `4b5714b8` |

The scripts expect the local frame and video paths named inside them. `regress_i.py` also needs HEAD's file as
`cm_head.py`. They are the record of how the numbers were made, not a reusable tool.
