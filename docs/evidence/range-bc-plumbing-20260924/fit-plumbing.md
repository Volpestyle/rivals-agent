# fit-plumbing (VUH-1359, VUH-1346): the plumbing fit ran; derive refused

**The plumbing queue finished DONE at 14:12:42 CDT.** All 9 runs exited 0. Every report was copied back and matches the
Mac byte for byte.

**`derive` refused, so there is no `preregistration.json`.** The refusal, verbatim:
```
PlanError: --hud-parity is not a hudparity result
```
- **Why:** `hud-parity-1.json` (`158649e6…`) has no `rule` field. derive requires `rule` and `pass`.
- **The real fit would refuse it too.** `train.parity_record` requires
  `PARITY_FIELDS = ("rule", "thresholds", "P1", "P3", "sources", "pass")`, so `--scope fit --hud-parity
  hud-parity-1.json` would stop with "lacks ['rule']".
- **Consequence:** the plan's fallback ("else run 1") cannot work as written.
- **I changed nothing to make it pass.**
- **Correction to my pre-check line this morning.** I told the lead derive would accept the p1 report with
  `hud-parity-1.json`. The report half was right (`check_report` accepts all 9 reports). The parity half was wrong: I
  never opened the parity file's fields.

No gates are claimed. The p1 dev gate block reads `complete: false, pilot_worthy: false` for both model arms; it is
dev only and has no validation. No commit, no Linear write, no game input.

## Decision for the lead: which parity file

| Option | What it takes | Note |
|---|---|---|
| **1. A P2′ parity result** (the pre-registered path) | A `hudparity` run on fresh frames | It carries `rule` |
| **2. Re-run the P2 rule over run 1's frames** | The current `hudparity` | Same frames, a new file with `rule: "P2"` and a new sha256 |
| 3. Accept pre-rule files | A code change to `PARITY_FIELDS` and derive | Needs review |

- **My recommendation: 1 if P2′ is close, else 2.** Either way the no-HUD candidate stands until P2′ passes.
- **Bytes, whichever file is chosen.** derive and the Mac fit must hash the same bytes. The pinned `158649e6…` is the
  CRLF file; git stores it as LF (`f4a23bf4…`). So a copy taken from a `git archive` on the Mac would differ from what
  derive hashed. Send the exact file to the Mac.

## Runs: exit, wall time against budget

The queue started 05:09:06 (lead, by hand). Each run's wall time is from the previous run's `.exit` to its own.

| Run | Exit | Ended | Wall | Budget | Main arm, s (sequence frames/s) | Dev evaluation |
|---|---|---|---|---|---|---|
| p1-curve | 0 | 07:03:34 | 114.5 min | 103.5 | model 3,819 (635), no-HUD 2,609 (930), twin 44 | 112 s |
| p2-repeat | 0 | 07:53:32 | 50.0 | 45.6 | no-HUD 2,601 (933), twin 44 | 71 s |
| p3-wd | 0 | 08:44:25 | 50.9 | 44.1 | no-HUD 2,726 (890) | 46 s |
| p4-lag1 | 0 | 09:35:18 | 50.9 | 44.1 | no-HUD 2,725 (891) | 47 s |
| p4-lag2 | 0 | 10:25:28 | 50.2 | 44.1 | no-HUD 2,681 (905) | 46 s |
| p5-0.25 | 0 | 11:28:51 | 63.4 | 46.9 | no-HUD 1,655 + 1,676 (733, 724), twins 31 + 31 | 133 s |
| p5-0.50 | 0 | 12:25:15 | 56.4 | 46.9 | no-HUD 1,447 + 1,473 (838, 824) | 133 s |
| p5-0.75 | 0 | 13:19:30 | 54.3 | 46.9 | no-HUD 1,378 + 1,418 (881, 856) | 133 s |
| p5-1.00 | 0 | 14:12:42 | 53.2 | 46.9 | no-HUD 1,358 + 1,375 (894, 883) | 135 s |
| **Total** | | | **543.6 min (9.06 h)** | **469 min (7.82 h)** | | |

- **The arm frames/s include every per-epoch dev pass** (511 windows each), so they read below the smoke's 802 / 1,056.
- **The budget ran 16% over,** for two reasons:
  - the dev passes cost more than the estimate's one-third factor;
  - **my estimate was wrong for the scaling runs.** It counted 10 dev passes per scaling run, but the fit runs one per
    epoch of the truncated set. At `--max-steps 1580` that is 40, 20, 14 and 10 passes, which is why ¼ was the slowest.
- **No warning, error or traceback in any log.** MPS, torch 2.14.0, 1,259 train windows, none dropped, 33.59 counted
  train minutes.

## p1: the dev curves (seed 0, weight decay 1e-4, stride 48, lag 0)

Per-epoch dev total loss (teacher-forced, every dev window). E = epoch, 1-based:

| E | model (HUD) | model_nohud | history_only |
|---|---|---|---|
| 1 | 2.3927 | 2.3925 | 2.3929 |
| 2 | 2.3849 | 2.3858 | 2.3802 |
| 3 | 2.4023 | 2.3983 | 2.2010 |
| 4 | 2.1631 | 2.1596 | 2.0185 |
| 5 | 1.9944 | 1.9803 | 1.8487 |
| 6 | 1.7965 | 1.7902 | 1.7235 |
| 7 | 1.6579 | 1.6651 | 1.6186 |
| 8 | 1.5828 | 1.5755 | 1.5545 |
| 9 | 1.5190 | 1.5141 | 1.5053 |
| 10 | 1.4806 | 1.4777 | 1.4684 |
| 11 | 1.4443 | 1.4515 | 1.4383 |
| 12 | 1.4247 | 1.4375 | 1.4173 |
| 13 | 1.4075 | **1.4310** | 1.3994 |
| 14 | 1.4051 | 1.4348 | 1.3945 |
| 15 | 1.3986 | 1.4458 | 1.3821 |
| 16 | **1.3977** | 1.4520 | 1.3775 |
| 17 | 1.3989 | 1.4565 | 1.3744 |
| 18 | 1.4014 | 1.4596 | 1.3727 |
| 19 | 1.4016 | 1.4622 | 1.3718 |
| 20 | 1.4021 | 1.4630 | **1.3717** |
| **argmin E** | **16** | **13** | **20** (still falling) |
| Train loss at E 20 | 1.3089 | 1.2257 | 1.4054 |

**Per head, candidate arm (model_nohud).** The camera head dominates the total.

| E | train | held | press | release | camera | total |
|---|---|---|---|---|---|---|
| 1 | 3.0605 | 0.2347 | 0.3642 | 0.3641 | 2.8591 | 2.3925 |
| 4 | 2.4154 | 0.2249 | 0.3604 | 0.3288 | 2.4911 | 2.1596 |
| 8 | 1.7041 | 0.1113 | 0.3140 | 0.1643 | 1.9718 | 1.5755 |
| 10 | 1.5456 | 0.0922 | 0.2999 | 0.1467 | 1.8778 | 1.4777 |
| 12 | 1.4313 | 0.0857 | **0.2929** | 0.1403 | 1.8372 | 1.4375 |
| **13** | 1.3841 | **0.0839** | 0.2933 | **0.1397** | **1.8283** | **1.4310** |
| 16 | 1.2721 | 0.0848 | 0.3026 | 0.1423 | 1.8447 | 1.4520 |
| 20 | 1.2257 | 0.0852 | 0.3087 | 0.1443 | 1.8495 | 1.4630 |

- **model_nohud:** every head bottoms at E 12-13, then rises while train loss keeps falling.
- **model (HUD), per-head argmin:** held 17, press 15, release 16, camera 16. At E 16: held 0.0807, press 0.2843,
  release 0.1346, camera 1.7963.
- **history_only:** held 19, press 19, release 18, camera 20. At E 20: held 0.0743, press 0.2920, release 0.1301,
  camera 1.7506.
- The full per-epoch, per-head logs are in each report's `epochs_log`.

## p2: MPS determinism, repeated on one configuration

p2 reran p1's no-HUD and twin arms with identical arguments.

| Checkpoint | p1 sha256 | p2 sha256 | Equal |
|---|---|---|---|
| model_nohud-seed0.pt | `127345464b3983c4026f7a3e970f7dc7625361970a0734b84e6522a999d0f81f` | same | **yes** |
| history_only-seed0.pt | `b6c4206249acd42bfcb011a81292e17f328db0ea982dfdf9af7e154cb10503d7` | same | **yes** |

These were also identical:
- every per-epoch train and dev value (all fields except wall `seconds`);
- the no-HUD teacher-forced dev metrics;
- the CPU-reference record.

## p3, p4

| Run | Min dev total (no-HUD) | At E | Against p1's 1.4310 at E 13 |
|---|---|---|---|
| p3, wd 1e-3 | 1.4409 | 12 | Not lower |
| p4, lag 1 | 1.4232 | 14 | Lower by 0.0078 |
| p4, lag 2 | 1.4077 | 17 | Lower by 0.0233 |

- **Lag is reported only, and the fit keeps lag 0** until the frame-to-send latency is measured.
- **Lag 2 scoring best was not expected by the plan.** Teacher-forced macro press-F1 at E 20:

  | Lag | F1 |
  |---|---|
  | 0 | 0.1673 |
  | 1 | 0.1356 |
  | 2 | 0.1550 |

  So the loss ordering does not carry over to presses.

## p5: the scaling curve (no-HUD and twin × seeds 0, 1; `--max-steps 1580` = 10 epochs at full data)

| Fraction | Train min | Windows | Dev total at end, no-HUD s0 / s1 | Twin s0 / s1 | Train loss, no-HUD s0 / s1 | tf macro press-F1, no-HUD / twin | Gap | Camera MAE, no-HUD (°) |
|---|---|---|---|---|---|---|---|---|
| ¼ | 8.40 | 314 | 2.1078 / 2.2068 (min 1.9954 / 2.0344) | 1.6594 / 1.6491 | 1.3311 / 1.2960 | 0.0673 / 0.0790 | **−0.0116** | 1.1726 |
| ½ | 16.79 | 629 | 1.7705 / 1.7397 | 1.6350 / 1.6363 | 1.6444 / 1.6348 | 0.0959 / 0.0758 | +0.0201 | 0.9754 |
| ¾ | 25.19 | 944 | 1.6814 / 1.6585 | 1.6338 / 1.6267 | 1.7002 / 1.7049 | 0.0920 / 0.0719 | +0.0201 | 0.9119 |
| all | 33.59 | 1,259 | 1.6719 / 1.6426 | 1.6314 / 1.6224 | 1.7461 / 1.7024 | 0.0799 / 0.0751 | +0.0049 | 0.8945 |

- **Rule (a), as derive would compute it:** the gap is positive from ½ (true) but not rising (false: flat, then it
  falls at all). **By the pre-registered wording, rule (a)'s condition holds:** the frames-minus-twin gap is not
  positive *and* rising from ½ to all. Caution: these are F1s near 0.08 from 2 seeds, and the gap is much smaller than
  the seed spread of the dev totals.
- **Rule (b), the rows it needs:** the no-HUD dev total (mean of 2 seeds) goes 2.157 → 1.755 → 1.670 → 1.657 at 8.4 →
  16.8 → 25.2 → 33.6 min. It flattens rather than falling linearly in log(minutes). The twin is flat, 1.654 → 1.627.
- **Rule (c), the rows it needs:** at ¼ the no-HUD arm memorises. After 40 epochs its train loss is 1.31 against dev
  2.11, and its dev total rose from a minimum of 1.9954. From ½ up, train and dev stay close.
- **The p5 curve is not comparable in absolute terms with p1.** At the same 1,580 steps, p5-all's no-HUD dev total is
  1.6719, while p1's at E 10 was 1.4777. The likely cause is the schedule: it is cosine over `total_steps`, so p5
  decays to zero by step 1,580, while p1 was still mid-schedule there. I have not verified this.

## The derived real-fit pre-registration: not written

`derive` refused before writing (above); there is no `preregistration.json` and no hash for it. These are the
pre-registered rules applied by hand to these reports, **not the driver's output**:

| Field | Value | From |
|---|---|---|
| weight_decay | 1e-4 | p3's minimum 1.4409 is not lower than 1.4310 |
| epochs | 13 | Argmin of p1's no-HUD curve |
| stride | 64 | E* 13 > 10 |
| lag | 0 | |
| seeds | 0, 1, 2 | |
| hud_parity_sha256 | none yet | Pending the decision above |
| source | these 9 reports, plan `850aeded…`, pre-registration `b0ce04df…`, commit `afff279` | |

## What the reports say that the plan did not expect

1. **The history-only twin has the lowest dev total loss:** 1.3717 against model 1.3977 and no-HUD 1.4310. The frame
   arms beat it only on teacher-forced macro press-F1 at E 20 (HUD 0.1593, no-HUD 0.1673, twin 0.1389).
2. **Teacher-forced camera MAE is worse than simple baselines** on dev (p1, E 20):

   | Predictor | Camera MAE (°) |
   |---|---|
   | ar2 | 0.376 |
   | persistence and echo | 0.418 |
   | twin | 0.632 |
   | HUD | 0.663 |
   | no-HUD | 0.690 |

   The degree caveat also applies: 92% of yaw motion is above the calibrated band (`d1201f2`).
3. **`simple_swing` has 3 train presses, not the 13 counted in 200129.** The fit counts only accepted, `normal`-regime
   rows of eligible runs.
   - Other train press counts: ultimate 5, melee 17, goh_targeting 42, team_up 118.
   - The live mask is on for 10 actions: the 4 movements, jump, web_swing, get_over_here, amazing_combo, spider_power
     and web_cluster. It is off for ultimate, melee, team_up, goh_targeting and simple_swing.
4. **Recorded by the fit, as expected for an archive run:**
   - `cache_hashes_verified: false`;
   - `git_commit.head: null`;
   - `hud_parity: null`;
   - candidate `model_nohud`, "no passing P2' parity".
5. **`collect.ps1` hung on its first `ssh`,** the same failure class as `launch.ps1`: Windows OpenSSH under PowerShell.
   - Nothing was left running.
   - I ran its three steps from Git Bash instead: the status check, the 9 `scp` copies, then `derive` with the same
     arguments.
   - I did not edit the driver. The generated `.ps1` scripts should become bash scripts, or run ssh with a fix I have
     not yet identified.

## Bytes (sha256)

| File | sha256 |
|---|---|
| `preregistration.json` | **not written** (derive refused) |
| `…\scratchpad\plumb-afff279\runs\plumb-p1-curve\report.json` | `dfa7a31704b17529638c8ea524a97109774ccbd8487975f41bc87d49d72cd032` |
| `…\runs\plumb-p2-repeat\report.json` | `68b4f046cb45bc1261488f36016dd7091cea1695bf3748c4c7f7c1e1e3a2efde` |
| `…\runs\plumb-p3-wd\report.json` | `4717291514219e9f4777b8049c300b743ef4f144b55c73b93b3dad818a639d9f` |
| `…\runs\plumb-p4-lag1\report.json` | `e39d65ac32a4d5e51f5458da706eb7e42df6c067be18e7c8f8f22bbddf85244c` |
| `…\runs\plumb-p4-lag2\report.json` | `38b6fff1d1bb4a29941a2d08e355ce21f4fcc2fc4a066c7dd2e0d2998557a5db` |
| `…\runs\plumb-p5-scale-0.25\report.json` | `8c6ae56f929e11b8d0c68963512070cf70a85fd0cf9303dadb432cfd896910ea` |
| `…\runs\plumb-p5-scale-0.50\report.json` | `f3dd378526da5fe42b07d79103fe9564db3c3a6af9ae05b8a8899e5bb630de20` |
| `…\runs\plumb-p5-scale-0.75\report.json` | `e1f14ab36952943ed94b12db7bf265c59a6b5747eac414baf064befa39b7d9ae` |
| `…\runs\plumb-p5-scale-1.00\report.json` | `7d07ae9ed288c80fbd345a11edd2a607abd3afd7101df000495eea2023f583c3` |
| `…\scratchpad\plumb-afff279\plan.json` | `850aeded7c099ebcea55c4ae96ef251377528b6194d7226b4fa4577863b2c868` |
| `docs/evidence/fit-readiness-20260923/range_bc_plumbing.py` (clean at `1df31e7`; working-tree bytes) | `eb75f66fbc5e18301209e1498563cfc589030e2b6a64bf43050d0713e2a9f760` |
| `tests/test_range_bc_plumbing.py` (clean at `1df31e7`; working-tree bytes) | `1874a9023a11f409c5b04467a84d8e5ee8b0a96ccb51414795719cabb13a1bf7` |

- `…` = `C:\Users\volpe\AppData\Local\Temp\claude\C--Users-volpe-repos-rivals-agent\ab8f5f2d-5ae0-4946-90a2-07ae87dfb27c\scratchpad\plumb-afff279`.
- **The 9 reports equal the Mac's** (`shasum -a 256` compared).
- **Also in the scratchpad:**
  - `poll.log`, one entry per 10 min, 05:14 to 14:14;
  - `analysis.json`, a read-only summary written by `analyse.py`;
  - `precheck\plumb-p1-curve\report.json`, the same bytes as the p1 report above.
- **The Mac keeps everything** under `/Users/james/dev/range-bc-data/runs/plumb-*`: checkpoints, logs, `.exit` files.
