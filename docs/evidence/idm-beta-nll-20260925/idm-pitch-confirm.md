# Confirmation of pitch fix A on fresh held-out sessions, 2026-09-25 (VUH-1353)

Owner: the inverse-dynamics lane (scoreboard-fix). Reviewer: fit-review. Next consumer: the Gate 2 precondition (replay
pitch labels), then the reviewed predictor change that deploys A.

- **Pre-registration:** `docs/lanes/inverse-dynamics.md` "### Confirmation of pitch fix A on fresh held-out sessions
  (pre-registered 2026-09-25)". Section LF sha256
  `a967962a7c69cb40f02684e633ca566eb13f427e56d562bfa7aba2fdcd2e537c`; the frozen copy is
  `idm-pitch-confirm-prereg-section.md`. The lead approved it as written, and it landed in `61b5b57` before any
  prediction on these sessions was looked at. Nothing in it changed.
- **Frozen parameters, no refit, no arm B.** Seven existing β-NLL checkpoints, no training. Twenty-one inference passes
  on the Mac (MPS, niced), scored on the PC by `confirm_score.py`, stdlib only.
- **No prediction was looked at before the scorer ran over all 21 files.** The job logs were read only for the
  `"missing"` counts and output paths.
- **Not done:** no commits, no Linear, no game input.

## Result: PASS, so A is confirmed (pre-registered reading)

The scorer's verdict line, verbatim:

> (1) coverage met; (2) bounds met; (3) yaw met -> **PASS**
> reading: A is confirmed on fresh held-out sessions; the Gate 2 precondition closes, and the deployment change (A in policy.idm.train._camera) is written for review

**(1) Coverage,** pooled over 232304 + 021320 + 025230 and all seven checkpoints, per true band. The cells are within
1σ′ / within 2σ′ / pitch abstention / answered within bound.

| True band | Before A (k = 1) | After A | (1) needs 0.70 / 0.90 |
|---|---|---|---|
| calibrated | 0.837 / 0.978 / 0.2 % / 0.999 | **0.905 / 0.986** / 1.5 % / 0.999 | meets |
| extrapolated | 0.634 / 0.904 / 0.7 % / 0.957 | **0.750 / 0.960** / 2.6 % / 0.963 | meets |

**(2) The 1° / 3° bounds on every checkpoint,** pooled over the three sessions, as the share of answered rows within the
predicted regime's bound after A:

| Checkpoint | Calibrated | Extrapolated | (2) needs ≥ 0.90 |
|---|---|---|---|
| T (`yaw-t0`) | 0.999 | 0.967 | met |
| T1 (`yaw-t1`) | 0.999 | 0.965 | met |
| T2 (`yaw-t2`) | 1.000 | 0.956 | met |
| s0 (`a1-beta-s0`) | 1.000 | 0.951 | met |
| s1 (`a1-beta-s1`) | 0.999 | 0.971 | met |
| s2 (`a1-beta-s2`) | 0.999 | 0.965 | met |
| a4 (`a4-beta`) | 1.000 | 0.965 | met |

**(3) Yaw is identical row for row** on all 21 files: met.

**The like-for-like guard passed before scoring.** `confirm_cohort.py` found one cohort across the three new target files
and the four training sessions (`confirm_cohort-out.txt`).

**The support floor:** every session's band is above 500 evaluable distinct pitch rows, so no per-session figure is set
aside.

| Session | Calibrated | Extrapolated |
|---|---|---|
| 232304 | 17,626 | 13,928 |
| 021320 | 72,374 | 51,878 |
| 025230 | 8,043 | 5,145 |

## Reported beside (not judged)

**Per session, pooled over the seven checkpoints** (1σ′ / 2σ′ / abstention / in-bound):

| Session | Band | Before A | After A |
|---|---|---|---|
| 232304 | calibrated | 0.831 / 0.975 / 0.4 % / 0.998 | 0.903 / 0.984 / 1.8 % / 0.999 |
| 232304 | extrapolated | 0.578 / 0.869 / 0.9 % / 0.935 | **0.697** / 0.941 / 3.1 % / 0.943 |
| 021320 | calibrated | 0.839 / 0.979 / 0.2 % / 0.999 | 0.905 / 0.986 / 1.4 % / 0.999 |
| 021320 | extrapolated | 0.648 / 0.912 / 0.7 % / 0.963 | 0.763 / 0.964 / 2.5 % / 0.968 |
| 025230 | calibrated | 0.837 / 0.982 / 0.2 % / 0.999 | 0.901 / 0.988 / 1.3 % / 0.999 |
| 025230 | extrapolated | 0.646 / 0.907 / 0.6 % / 0.964 | 0.764 / 0.962 / 2.8 % / 0.971 |

**Per checkpoint, extrapolated band,** pooled over the three sessions:

| Checkpoint | Before A | After A |
|---|---|---|
| T | 0.609 / 0.890 / 0.2 % | 0.737 / 0.955 / 1.2 % |
| T1 | 0.665 / 0.922 / 0.4 % | 0.768 / 0.967 / 1.6 % |
| T2 | 0.637 / 0.902 / 0.8 % | 0.752 / 0.961 / 2.2 % |
| s0 | 0.642 / 0.930 / 2.9 % | 0.758 / 0.974 / **9.3 %** |
| s1 | 0.677 / 0.919 / 0.3 % | 0.785 / 0.965 / 1.8 % |
| s2 | 0.637 / 0.902 / 0.3 % | 0.756 / 0.963 / 1.5 % |
| a4 | 0.572 / 0.859 / 0.0 % | **0.696** / 0.935 / 0.8 % |

The calibrated band after A runs from 0.853 to 0.977 within 1σ′ across the checkpoints. The calibrated rows and all
42 session × checkpoint rows are in `confirm_score-out.md`.

**Yaw raw-μ direction agreement on moving rows (|true| ≥ 0.5°),** a transfer check: 0.936–0.980 across the 21 files.
The lowest is `a1-beta-s0` (0.936–0.949) and the highest `a4-beta` (0.978–0.980). The checkpoints transfer to the new
build (`1.1.3892207`) and sessions.

## Caveats, stated as caveats, not new conditions

- **232304 is the weakest session.** Its extrapolated band is 0.697 / 0.941 pooled over the checkpoints, a hair under
  0.70 on its own. The registered judge is pooled over the three sessions, and 232304 carries 20 % of the pooled
  extrapolated rows.
- **A's own source checkpoint is the lowest per checkpoint:** `a4-beta` reaches 0.696 / 0.935 in the extrapolated
  band, and 0.644 / 0.909 on 232304 alone. Per-checkpoint coverage is reported, not judged; the bounds (2) are the
  per-checkpoint condition, and `a4-beta` meets them (0.965). In round 3 its own fit set sat in-sample at 0.740. So
  A's k values are not overfitted to its source checkpoint's error scale, but on the new sessions they cover that
  checkpoint least.
- **The cost in answered rows:** pooled extrapolated-band pitch abstention rises from 0.7 % to 2.6 %, which is between
  round 3's two folds (2.0 % and 4.5 %). `a1-beta-s0` is again the outlier: 9.3 % pooled, 10.6 % on 232304.
- **These are the only fresh sessions.** Having passed, they are now spent as held-out evidence for A. A future pitch
  change needs its own fresh sessions or a pre-registered fold design.

## The 20 % rule during the passes (process, for the record)

- **Before the passes,** hud-review's `interim94-seed0` ran at 0.841 s/step (the baseline) up to epoch 9 (0.849).
- **Epoch 10,** beside my 025230 store decode and the start of the first 021320 pass: 283.2 s, 0.997 s/step, **+18.6 %**.
- **Epoch 11,** fully beside the MPS inference passes: 375.7 s, 1.323 s/step, **+57.3 %**. That is well past the rule.
- **The pause was denied.** I tried to SIGSTOP my own job tree (pids 86426, 86428, 99016 and 99017) as the brief says,
  and the Claude Code auto-mode classifier denied it ("Interfere With Workloads"). I did not work around the denial. At
  15:38 I sent the lead a decision request with the exact pause command and told James in the pane.
- **Then the queue moved on by itself.** There was one run. At 15:43 `model_nohud` finished epoch 12, and `train.py` then
  trained the second arm, `history_only` (the cheap twin, about 5 s per epoch), in the same process, appending to the
  same `interim94-seed0` log. Its report was written at 15:51 with exit 0 ("dev model_nohud: pilot_worthy False"; the
  facts are from hud-review's `fit-interim-amend-1.md`). At 15:51 the queue ended: `queue.status` reads
  `FAILED interim94-seed1`. That run exited 1 on `train.py`'s argument check, "FitError: seed 0 is the pre-declared
  candidate and must be trained". That is a configuration refusal in their queue, not a resource failure. I only read
  their files.
- **The rest of my job ran unpaused.** The job was never stopped; about 13 minutes of the run (the end of `model_nohud`'s
  epochs and the `history_only` arm) overlapped the passes while the rule was tripped. I sent the lead an update at
  15:52 saying the pause request was moot.
- **Lesson for the next Mac job beside a queue:** the MPS inference passes cost an MPS fit about +57 % per step, far
  more than the CPU decode (+10 %). Wait for the queue, or get the pause authorised in advance.

## Hashes

**Scorer and outputs** (PC: `handoff\idm-pitch-confirm-state\`):

| File | sha256 |
|---|---|
| `confirm_score.py` | `a259ff4748082a9e87f21cf7825178a336d8294ca4bdb7278b24b0afda3e8bd3` |
| `confirm_score-out.md` (every table, all 42 session × checkpoint rows) | `7bc6b42657dfecbe9ed55c88b45d9f5ee4b7d132538b25d527bdc1f0dcdf4a75` |
| `confirm_score-results.json` | `df3c2c7d649b7af7484487b399ddfeb8241b11b9c6508cbda97ffb6a0ff3c129` |
| `pitch_fix3-params.json` (A's frozen edges and k, asserted by the scorer) | `6f8dba7b04336c3fd4ce5dcd2acaa8b5a6e4578678643dedb7d942b1549bcff3` |
| `pitch_fix3.py` (the source of `apply` and `coverage`, copied verbatim) | `6769ad60964b203dbd2198de889c547e08861fbd682eabf23d4ff44f12fe144f` |
| `confirm_cohort.py` / `confirm_cohort-out.txt` | `b82cafc07a58324728094d98b2b0933b46b12b36ccb6982c029f3bedaf9e8bd2` / `7a84becfc5bcd71dc2ed910eac0ef385090143ababbdfe2c12c06469eff99dd9` |
| `idm-pitch-confirm-prereg-section.md` (the frozen section, `handoff\`) | `a967962a7c69cb40f02684e633ca566eb13f427e56d562bfa7aba2fdcd2e537c` |

**The 21 prediction files** are hash-identical on the Mac (`/Users/james/dev/idm-data/diag/`) and the PC
(`handoff\idm-pitch-confirm-state\`), checked by `diff` of the two `shasum` listings. Each 232304 file has 31,554
examples, each 021320 file 124,252 and each 025230 file 13,188, with `"missing": 0` in every pass.

| Checkpoint | 232304 | 021320 | 025230 |
|---|---|---|---|
| `yaw-t0` | `d96ea2df…` | `c5b0fbd31f4cbb505647b2d982eaa2e8f559ea3ffb57fbdfaa602affd2973e47` | `ca5e61dccc9afad62fbb34587d2e10217684126cfce1536575b8ebf4d37dec78` |
| `yaw-t1` | `dd6aab0b…` | `87251b518129f70a84d0d19e9e9ea5ebb6ac068fae47e3a5f6900427f929b296` | `41348aa6ab66d394b9ad91b0d113b397761849976cbf6236b9e1ade6aaf5ffd0` |
| `yaw-t2` | `a83ab254…` | `79d2bde976faf061262467d2be6e4eb7c18bf1330c6523d0826fb79e0e56f855` | `8e783c86b5b58fe9ac4bdb4ca1dd43f7d92356ca4f5f80fa981993c3cb570295` |
| `a1-beta-s0` | `6e8961d5…` | `0dde6f31c798817d42d229db9b91b60f677a9c16627a53fea59b9fbb7643fd8c` | `2dd4e585f97a335abf3d16e9a1c39274a4d36c1b50e0d8c024cbb8e54a8fe37b` |
| `a1-beta-s1` | `6b1babd7…` | `4d43c30dd6e510376495f0ef744bb63a7402018105438e47ee54ac37c322991d` | `5363a6bd93791f4a55eaa0f835750a69f9b9dc0221fbf27c5aa7e2fba03f52cf` |
| `a1-beta-s2` | `7105aed8…` | `456dbc6027fe817f68b245882122ea91b5a379deb1a4a3c98f85c0e3ae815d5f` | `3cde58379ff4f38f321e0c61921ff8e5fe3fe81753368f211ada5187c0c827ae` |
| `a4-beta` | `6f65dd83…` | `f92a9f19acb57a2704459e72a48cb605aef066df07fa43101ae9b6c1062f3582` | `2398d014e0feaf25eab476945e94e809c9b8493d7ac770a20daa13b6fb74a757` |

The full 232304 hashes, unchanged from the earlier passes, are in `idm-pitch-confirm-state.md` and in
`confirm_score-out.md`'s input list, which has all 21.

**Upstream inputs** (all as in `idm-pitch-confirm-state.md`; the Mac job re-verified the code and checkpoints):
- **Targets** (`rivals-idm-targets-v1`):
  - 232304 `8b00217ac5928ffcf7cda6e19004671ca044016b8ad38f90d6843a76ce607bc3`;
  - 021320 `ec36759487f4f5eb0755828808face1c90b5d7767a63c96d8aaa6c7dcc242a0a`;
  - 025230 `5c815469993392eb60d562fe9497706228070748da017262e3e75ba93ed0f02c`.
- **Originals,** verified against `expected_media_sha256` before decoding:
  - `2026-09-24 18-23-04.mkv` `58f8e234…`;
  - `2026-09-24 21-13-20.mkv` `a1a89dd3…`;
  - `2026-09-24 21-52-30.mkv` `c6adfd57b58cd018c04b9787801084c7175a45e6d58dd5ffab9c46e026c42e08`, re-verified by this job.
- **Frame stores** (`/Users/james/dev/idm-data/stores/<id>/`, decoder at `fe5c9ca`):
  - 232304 and 021320 as in the state file;
  - **025230 (new):** 13,220 frames (as expected); `frames.u8`
    `69abea89e26963f92e784e1267a0aa3ea110302799d38b7d5ebbfdfbf3f2aa1d`, `hud.u8`
    `2dde6589b7b58b2772f5f11f67822b6826312b688acc6cd03901f178c75f0aef`, `frames.json`
    `77c879351083eaa68aa72ab185829e46fb1f162d1c1269be4575c88611351a54`.
- **Checkpoints:** T `17e2eee8…`, T1 `bc82a2a4…`, T2 `a85a1530…`, s0 `74727eaa…`, s1 `6ba77383…`, s2 `0e2fd63d…`,
  a4 `90aa4bef…` (full hashes in the state file). `resume-confirm.zsh` asserted each one before running.
- **Inference:** `diag_predict_ckpt.py` `ea8343300c415e1289c07162c4205ffddd530ee59f5051c2785c9a1203eb4d2a`, from
  worktree `/Users/james/dev/rivals-agent-worktrees/idm`, clean at `fe5c9ca`, asserted by the job.
- **The job:** `resume-confirm.zsh` `98193f5efda523722e3739a71542f21cb62a2c6b33978a072b24d99abdafd552` and `run.zsh`
  `c84b2f9d…`. It ran from 15:27:34 to 16:01:06 CDT; `runs/resume-confirm.exit` is `0`.

## The lane doc

- **New LF sha256:** **`e326e2faa90d68a707b8bb3153e925591ad0bd1427362ac228360cb9e3f25ebe`**. It was
  `65f39750…`, as landed in `61b5b57`.
- **What was added:** "**Result (measured 2026-09-25): PASS**" at lines **1373–1390**, after the confirmation section
  and before "### The edge head's input". `git diff --stat` shows 1 file, 19 insertions and no deletions.
- **Pins:** each frozen section occurs verbatim exactly once in the LF doc:
  - the confirmation section `a967962a`;
  - part A `42beb90e`;
  - calibration `e6b5d526`;
  - round 2 `5f94a529`;
  - round 3 `f1385679`.

## For `docs/evidence/idm-beta-nll-20260925/`

- **Files:**
  - this file, as `idm-pitch-confirm.md`;
  - the frozen section, as `idm-pitch-confirm-prereg.md` (the content of `handoff\idm-pitch-confirm-prereg-section.md`,
    `a967962a…`).
  - `confirm_score.py`, `confirm_score-out.md` and `confirm_score-results.json` stay in
    `handoff\idm-pitch-confirm-state\` unless you want them in the packet. The hashes above pin them either way.
- **Draft README row:**

  **Confirmation of pitch fix A on fresh held-out sessions (`idm-pitch-confirm.md`; pre-registered in
  `idm-pitch-confirm-prereg.md`, section a967962a, landed 61b5b57 before any prediction was looked at):** PASS, so A
  is confirmed and the Gate 2 precondition for fast-band replay pitch labels closes. The frozen round-3 parameters
  (k = 1, 1, 1, 1.60, 1.24 at yaw-std edges 0.061 / 0.108 / 0.170 / 0.352°) were applied, not refitted, to all seven
  β-NLL checkpoints on the three newly admitted takes (232304, 021320, 025230; one cohort under the guard; 21 inference
  passes). Pooled, the extrapolated band reaches 0.750 / 0.960 (0.634 / 0.904 before A) and the calibrated band 0.905 /
  0.986; the 1° / 3° bounds hold on all seven checkpoints (0.951–0.971 extrapolated); yaw is identical row for row.
  The cost is extrapolated-band pitch abstention of 0.7 % → 2.6 % pooled (9.3 % on `a1-beta-s0`). Not conditions:
  232304 alone reaches 0.697, and `a4-beta` alone 0.696, in the extrapolated band. Next: the reviewed change that
  deploys A in `policy.idm.train._camera`.
