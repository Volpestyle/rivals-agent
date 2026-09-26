# fit-interim (VUH-1346, VUH-1359): the 94-minute interim fit, read by the pre-registered rules

**This is an interim scaling-curve point, not the real fit. Nothing from it is a policy acceptance or a live-pilot
candidate.**

Pre-registration `fit-interim-prereg.md` (`8094bdd1…`), amendment `fit-interim-amend-1.md` (`d17c483e…`), launches
`fit-interim-launch.md` and `fit-interim-launch-2.md` (`29b50213…`). Queue 2 ran 16:44:16 to 20:50:14 CDT; both runs
exited 0. The reading is `interim94/reading.json` (`54094590…`), made by `interim94/judge.py` (`bfab9d36…`), exit 0.

## Outcome

**Opens.** By the pre-registered rules, the no-HUD arm's teacher-forced press-F1 lead over the twin grows with data by
more than the seed spread:
- `ΔF1` goes from +0.0072 at 33.6 train min to +0.0361 at 80.5, a rise of 0.0289;
- the two groups' seed ranges add up to 0.0236.

| Rule | Condition | Result |
|---|---|---|
| **Opens** | `ΔF1`(80.5) − `ΔF1`(33.6) > both ranges combined: 0.0289 > 0.0083 + 0.0153 = 0.0236 | **yes** |
| Closes | `Δloss`(33.6) − `Δloss`(80.5) > both ranges combined: 0.0508 > 0.0136 + 0.0491 = 0.0627 | no, short by 0.012 |
| Reverses | every seed's `Δloss`(80.5) < 0 | no: −0.0082 on seed 2 only |
| Not resolved | none of the above | no, because Opens holds |

**On loss, the rule is not met.** The gap did shrink:
- at 33.6 min, every seed's no-HUD dev loss is above the twin's (+0.025 to +0.074);
- at 80.5 min, the three seeds sit either side of zero (+0.0006, +0.0054, −0.0082; mean −0.0007).

The control's own seed spread (0.049) is what keeps it below the pre-registered bar. Stated as it is: "the loss gap
closes" is not established by this rule at three seeds.

## Per arm and seed (dev = 171533 + 205528, 13 epochs, teacher-forced "all" stratum)

**80.5 train min (`interim94-s012`, 2,266 windows, 3,692 optimiser steps)**

| Seed | Arm | Dev total, epoch 13 | Argmin epoch (min) | TF macro press-F1 | TF camera MAE (°) |
|---|---|---|---|---|---|
| 0 | no-HUD | 1.3144 | 13 (1.3144) | 0.1783 | 0.5953 |
| 0 | twin | 1.3138 | 13 (1.3138) | 0.1431 | 0.5737 |
| 1 | no-HUD | 1.3152 | 13 (1.3152) | 0.1723 | 0.5858 |
| 1 | twin | 1.3098 | 13 (1.3098) | 0.1399 | 0.5664 |
| 2 | no-HUD | 1.3101 | 12 (1.3096) | 0.1799 | 0.5832 |
| 2 | twin | 1.3182 | 13 (1.3182) | 0.1392 | 0.5773 |

**33.6 train min, the same-recipe control (`interim94-control47-s012`, 945 windows, 1,547 steps)**

| Seed | Arm | Dev total, epoch 13 | Argmin epoch (min) | TF macro press-F1 | TF camera MAE (°) |
|---|---|---|---|---|---|
| 0 | no-HUD | 1.6871 | 13 (1.6871) | 0.0746 | 0.9318 |
| 0 | twin | 1.6353 | 13 (1.6353) | 0.0695 | 0.8795 |
| 1 | no-HUD | 1.6683 | 13 (1.6683) | 0.0846 | 0.9364 |
| 1 | twin | 1.6436 | 13 (1.6436) | 0.0687 | 0.8818 |
| 2 | no-HUD | 1.7141 | 13 (1.7141) | 0.0769 | 1.0317 |
| 2 | twin | 1.6404 | 13 (1.6404) | 0.0762 | 0.9049 |

**The gaps** (no-HUD − twin, seeds 0, 1, 2):

| Group | `Δloss` per seed | mean | range | `ΔF1` per seed | mean | range |
|---|---|---|---|---|---|---|
| 80.5 min | +0.0006, +0.0054, −0.0082 | −0.0007 | 0.0136 | +0.0352, +0.0324, +0.0407 | +0.0361 | 0.0083 |
| 33.6 min | +0.0519, +0.0246, +0.0737 | +0.0501 | 0.0491 | +0.0051, +0.0159, +0.0007 | +0.0072 | 0.0153 |

**Arm means (range):**

| Arm | Group | Dev total | Press-F1 | Camera MAE (°) |
|---|---|---|---|---|
| no-HUD | 80.5 | 1.3132 (0.0052) | 0.1768 (0.0076) | 0.5881 (0.0121) |
| twin | 80.5 | 1.3140 (0.0084) | 0.1407 (0.0039) | 0.5725 (0.0109) |
| no-HUD | 33.6 | 1.6898 (0.0458) | 0.0787 (0.0100) | 0.9666 (0.0999) |
| twin | 33.6 | 1.6398 (0.0084) | 0.0715 (0.0075) | 0.8887 (0.0254) |

**Heads at epoch 13, 80.5 min:**
- the no-HUD arm's press loss is lower than the twin's on every seed (0.266-0.276 against 0.286-0.287);
- its camera, held and release losses are slightly higher;
- so the loss totals net out near zero while press-F1 separates.

## Camera against the baselines

**Neither arm beats persistence (0.418°) or ar2 (0.376°) on camera MAE, in either group.** Both arms fell a lot with
data (no-HUD 0.967° to 0.588°, twin 0.889° to 0.573°) but are still about 0.2° worse than ar2.

The baselines are as pre-registered:
- persistence 0.41827°, F1 0, in both reports;
- ar2 0.37620° in the control (the same train as plumbing, equal to the plumbing record) and 0.37623° in the 80.5 group.
  ar2 is fitted on train, so it moves slightly with five sessions; it rounds to 0.376° either way.

## Recipe health (reported, not acted on)

**The no-HUD argmin epoch per seed: 80.5 min [13, 13, 12], control [13, 13, 13].** No overfitting at 13 epochs. The
curves are flattening:
- 80.5 min: the last two epochs move the dev total by ≤ 0.0005;
- seed 2's minimum at epoch 12 is 0.0005 below epoch 13;
- control: still falling by about 0.001-0.002 per epoch at the end.

At 80.5 minutes the recipe is near its floor, not past it.

## Determinism check: equal

`interim94-seed0` (queue 1, `--seeds 0`) against `interim94-s012`'s seed 0:
- both seed-0 checkpoints are byte-identical: `model_nohud-seed0.pt` `2d5183cb…` and `history_only-seed0.pt` `c939ce0f…`,
  the same on both runs' report entries and on the Mac's `shasum`;
- the seed-0 epoch logs (without wall time), teacher-forced, self-fed and sanity blocks, and all five baselines are
  exactly equal.

So the MPS fit on this code and machine reproduced bit for bit across processes. The seed-0 figures above are that
shared result.

## Checks: none fail

For all three reports (`interim94-s012` and `interim94-control47-s012` with seeds [0, 1, 2], `interim94-seed0` with
[0]), each of these matches the pre-registration:
- scope `plumbing`;
- config: epochs 13, wd 1e-4, stride 64, lag 0, arms [model_nohud, history_only], train_fraction 1, max_steps null;
- `hud_parity.sha256` `e9efe999…`;
- patch equivalence: default, "Season 10, Version 20260911", both builds for 80.5 and the old build only for the control;
- the cohort's session ids, roles and step-table sha256;
- `test_opened` false;
- per-seed epoch logs and teacher-forced blocks for every arm and seed.

Candidate `model_nohud-seed0.pt` in both, as expected (the parity file fails).

## Hashes (Mac `shasum -a 256` = local `sha256sum` for every copied file)

| File | sha256 |
|---|---|
| `interim94-s012/report.json` | `e8d955c0faa59937456ed91485d731781850e316a1892a9544d24c93f47938d5` |
| `interim94-control47-s012/report.json` | `f1a6a0b7f8d3c2f0fdece301685dd92684021b4bdfdc5e38a441166f3f9da43d` |
| `interim94-seed0/report.json` | `a18e1f8e5149ac631bf6740867229ebfd485591c769336ad7d236fc1f9bab5a8` |
| `interim94-s012.log`, `.exit` (0) | `cd0dca0f2c71960dc32462b78189a9b14a1ef7eb04d13e5175dfc05c0dbffc64`, `9a271f2a…` |
| `interim94-control47-s012.log`, `.exit` (0) | `4a516a7a3566ddd09aa604e3c7d2e07e29cb225950e37cf4c62835629a59d0bc`, `9a271f2a…` |
| `interim94-seed1.log`, `.exit` (1, the refusal) | `6d3cc1388698377e3643b48b51bcbb8da7d5a965d2eb5b2d544b0e34246d7d70`, `4355a46b…` |

**The twelve checkpoints of queue 2, plus `interim94-seed0`'s two.** Each Mac file's sha256 equals its report's
`checkpoints` entry (`interim94/mac-sha256.txt`). They stay on the Mac; none was copied.

| Checkpoint | `interim94-s012` | `interim94-control47-s012` |
|---|---|---|
| `model_nohud-seed0.pt` | `2d5183cba12913a36327e0a459ec0c0b2a1238d26a7df98f7823929af3129f18` | `5cb5a1887483a63ce4c67f3647b36b063a6998fd3cc905e65b6a01d60d2ba6b1` |
| `model_nohud-seed1.pt` | `be371ed2f9ea84760847d5ad7b712a5490bb75baa9d5b5001889aec5e52d2839` | `b1aa7dc197fd36c6ab75be83d5e90738e54a27d4358bfb24df323a2c9478cf0e` |
| `model_nohud-seed2.pt` | `ed4b2269e709eb861060b21d38d5527848c1e962bb573c7665bc3cadc3b237f0` | `7b5bd6a2e34a3b309532c9e33d5e61382d2d691f21280984266516825b30f7aa` |
| `history_only-seed0.pt` | `c939ce0fb96730959619a4449a1ee7725e298199e13b12db3f50d5e91c37a132` | `6a0cce0ade7b5c74d2517bb2126062dc76fa7f7ff7dde7e09afeeb1e087dbe11` |
| `history_only-seed1.pt` | `9bfc31f63b8fd7568b20bc55bb363a54392637611166fe3582ee90188199fbde` | `56f5c6167425828212e24405f853013078201a6ce45fb44cc9bb79472e7c4b5a` |
| `history_only-seed2.pt` | `13e6e6792948a7325032637efad8489a8db00072ccd0067c07de8ca28fca8e3e` | `d6b235d3ff6bb7a2fc011fa3bd1fecb8bc69f2c3040bfafc1e9a2a8247615d3f` |

`interim94-seed0`: `model_nohud-seed0.pt` `2d5183cb…`, `history_only-seed0.pt` `c939ce0f…` (equal to `interim94-s012`'s).

**Wall time (queue 2):**
- 80.5 group: no-HUD 3,067-3,137 s per seed, twin 47-56 s, evaluation 251 s;
- control: no-HUD 1,374-1,405 s, twin 21-22 s, evaluation 197 s.

## Plumbing context (a different recipe; not the comparison)

- **p1** seed 0 `Δloss` +0.032 at epoch 13. **p5-all** `ΔF1` +0.005.
- The same-recipe control agrees in sign and size: `Δloss` +0.050, `ΔF1` +0.007.

## Proposed `docs/evidence/range-bc-interim-20260925/`

| Item | sha256 |
|---|---|
| `fit-interim-prereg.md` | `8094bdd1…` |
| `fit-interim-amend-1.md` | `d17c483e…` |
| `fit-interim-launch.md` | `7a69f787…` |
| `fit-interim-launch-2.md` | `29b50213…` |
| `fit-interim.md` | this file |
| `runs/interim94-s012/report.json`, `runs/interim94-control47-s012/report.json` | the reading's two reports |
| `runs/interim94-seed0/report.json` | the determinism reference |
| the `.log`/`.exit` of `interim94-s012`, `interim94-control47-s012`, `interim94-seed0`, and the failed `interim94-seed1` | |
| `queue.zsh` | `a79e06b9…` |
| `queue2.zsh` | `460ebb48…` |
| `judge.py` | `bfab9d36…` |
| `judge-v1.py` | `628c432e…`, the pre-amendment judge, never run on results |
| `test_judge.py` | `c6523c64…` |
| `reading.json` | `54094590…` |
| `mac-sha256.txt` | `47c032d2…`, the Mac's hashes of reports, checkpoints, logs and exits |
| `verify-7.json` | `d23b8b9e…` |

All are in the handoff folder: `interim94/` and `interim94/runs/`.

**Checkpoints:** not proposed; 14 files, about 27 MB per seed's arm pair (about 190 MB in all). Their hashes are above and in `mac-sha256.txt`.
Say if you want them copied.

## Limitations

- **Plumbing scope.** The reports do not bind `preregistration.json`, and `cache_hashes_verified` is false.
  - Mitigated: all seven caches were re-hashed before launch (`verify-7.json`).
  - Mitigated: every report's config, parity hash, patch equivalence and cohort step-table hashes are checked (none fail).
- **Three seeds per group.** "Opens" clears its bar by 0.005 on a range sum of 0.024; the loss rule misses by 0.012.
  Both are close to the line; a fourth seed could move either.
- **Data and optimiser steps co-vary.** The recipe is fixed in epochs, so the 80.5 group took 3,692 steps and the
  control 1,547. The comparison is "the same recipe on more data", as pre-registered, not "more data at equal compute".
- **Dev is two old-build sessions.** Three of the five 80.5-minute train sessions are the new build (build25501035), and
  none of dev is. So the reading says nothing about generalising to the new build.
- **Teacher-forced only.** Self-fed rollouts are degenerate in every model of both groups, as in plumbing:
  - macro press-F1 is 0;
  - camera MAE is 1.2246-1.2290°, equal to the zero-motion baseline's 1.2246°.
  So nothing here says the policy acts on its own outputs. Outside the pre-registered reading; noted because the next
  consumer should not read "Opens" as live competence.
- **Absolute press-F1 is low** (0.18 at best), and **camera** carries the slow-turn degree caveat (92 % of yaw motion is
  above the calibrated band).
- **Contention.** The IDM lane's MPS passes ran beside queue 1's seed 0 only; that affected wall time, not results. The
  determinism check shows seed 0's result was unaffected. Queue 2 launched with no IDM or other fit process running,
and its no-HUD epochs (about 240 s at 2,266 windows) match queue 1's uncontended pace. Whatever else ran on the Mac
during queue 2 was not checked.
- **Monitoring gap.** My background poll was stopped twice by Claude Code for low PC memory (about 18:45 and 19:20). The
  lead's own check found DONE; the queue itself was never interrupted.
