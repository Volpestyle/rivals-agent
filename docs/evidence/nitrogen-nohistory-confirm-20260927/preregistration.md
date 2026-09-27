# NitroGen no-history confirmation — 2026-09-27

**CONFIRM; proposed for lead approval. No confirmation run has launched and no confirmation result exists.**
Owner: explore-policy. Result record: VUH-1346. This document is committed before results;
changes require a new pre-result `preregistration-aN.md`, never an edit to this file.
The lead explicitly approves this preregistration and judge before launch. Under James's
2026-09-27 review rule, the landed judge receives independent review before anybody reads a result;
unchanged-guard launch plumbing receives owner tests, not another review.

## Question and fixed comparison

Does removing previous-action input improve the exact frozen-NitroGen H1 recipe's
absolute self-fed press and camera predictions across three new seeds?

| Arm | Encoder | Previous-action input | Training history dropout | Seeds |
|---|---|---|---|---|
| Candidate | Frozen NitroGen vision | Disabled (`Config.history=False`) | Existing .2 draw retained; input has no action information | 1, 2, 3 |
| Control | Same frozen NitroGen vision | Enabled | .2 | 1, 2, 3 |

Candidate is the recipe in `1a9bcaf`, with operational fixes F1–F3 in `19d0060`.
Control is the history-enabled NitroGen encoder recipe from `9665876`. Seed 0 is
exploration, excluded from confirmation and all seed means. No third arm, extra seed,
epoch selection, threshold selection on dev, or winner chosen among decoders is allowed.
Removing action history makes teacher/self-fed action-history inputs identical by construction;
closing that gap is not a success criterion. The causal visual LSTM remains.
`history=False` zeroes the history vector before its embedding; its constant bias remains.

Implementation/launch source commit: **`5673de101a398fa661be581e3c1dd041391e2a61`**.
Its delta adds seed propagation, confirmation metadata and the chance-floor report; training,
model, preprocessing, losses, cohort admission, thresholds and existing metric semantics are unchanged.
Training and eval utilities retain historical file names and the checkpoint serialization format.
Top-level checkpoint, recipe, evaluation and worker records are tagged `CONFIRM`.

## Matched recipe and authorized data

- Six fresh fits, final **epoch 26**, seed pairs 1/2/3, CUDA **L40S**; no resume or automatic fit retry.
- H1, AdamW lr .0003, weight decay .0001, batch 8, warmup 500, 26-epoch cosine schedule;
  4,697 TRAIN windows, 15,288 updates. Existing 64-stride windows, burn-in and masks unchanged.
  Positive weights are the existing 2 × 15 array of 20.0. Use final epoch, not best dev epoch.
- Both views use the frozen vision tower, with no pixel jitter/DrQ. Global 144×256 and
  crop 128×128 RGB resize to 256×256 by bilinear antialias squash, normalize RGB/127.5−1;
  bf16 tower `last_hidden_state` (256×1024), row-major 4×4 cell means → 16,384 features/view;
  float16 caches, float32 head. Two 256-wide projections, 512-wide LSTM, history embedding 64;
  no HUD or regime bit. Full architecture is fixed in the judge's `CONFIG` constant.
- Only the already admitted TRAIN cohort and its frozen TRAIN holdout. No sealed payload,
  validation/test split, new admission, or CM3 volume is read. Existing roster/header/denylist
  checks remain intact. No data-discovery glob is added.
- Model input manifest SHA256:
  `aec08c08e247e3743ddeb1eec49dd880e1c0f62039c375932cab31dfccb91e22d`.
  Volume upload manifest SHA256:
  `73c8d80c13281e8a8d4d502e10cb82cf35831eb4ffb1897fdc4e9cbe7789c19e`.

| Role | Session | Eligible frames |
|---|---|---:|
| TRAIN | 20260923T051828-422Z-33696-1 | 12550 |
| TRAIN | 20260923T200129-346Z-33696-6 | 47910 |
| TRAIN | 20260924T232304-170Z-12024-1 | 15777 |
| TRAIN | 20260925T021320-371Z-7804-1 | 62126 |
| TRAIN | 20260925T025230-605Z-7804-2 | 6594 |
| TRAIN | 20260925T203745-207Z-49728-2 | 82756 |
| TRAIN | 20260926T035932-508Z-63684-14 | 54270 |
| TRAIN | 20260926T045729-166Z-79780-1 | 18465 |
| Frozen dev | 20260923T171533-187Z-33696-5 | 4630 |
| Frozen dev | 20260923T205528-900Z-45572-3 | 19926 |

Totals: TRAIN 300,448; frozen dev 24,556. The source commit has unchanged corpus registry,
tally, trainer, steps, model, chunk windows/losses and threshold selector relative to `1a9bcaf`.
Per-run feature receipts include source hashes, selected indices, graph and cache hashes;
their elapsed times legitimately differ and are not paired-equality requirements.

NitroGen source revision `584c8dded734d032f07a4bcc0ccb330e703298c4`, `ng.pt` SHA256
`a266f5fb9c7dbdcdf97216558d2d82075a9a994b824cda69afa9fd3280260a81`.
Extracted vision SHA256 `2fceee7b828e737e459b39aa5d11e01362ce38210033f6f885b9974d7a0d6e79`;
stock-compatible configuration SHA256 `172e39dbf0143b8fe22d2f08921730eb8c397967e58cb37d133161e28aa34104`.
Only hash-checked weights are loaded with `weights_only=True`; no NitroGen harness or `game_env.py`.

## Primary metrics and decision rule

**One primary decode is fixed: `train_chosen/median`, evaluated self-fed.**
Per-action cutoffs are recalibrated separately for each trained checkpoint on TRAIN
teacher-forced predictions only. The existing exact binary64 interval search matches
executed press counts (hold rises plus taps), with ties closest to .5, then lower cutoff.
Frozen dev never chooses a cutoff. Control self-feeds its own executed actions, not human history.

1. **Press:** macro tolerant press F1 over the six existing EDGE_ACTIONS:
   spider_power, web_cluster, get_over_here, amazing_combo, web_swing, jump.
   Valid and press-known targets only; one-to-one matching at ±1 frame within each original run;
   undefined per-action F1 counts as zero. Candidate must strictly beat its paired control
   in **every** seed, and its arithmetic seed mean must exceed the control mean and incumbent
   H1 F1 **0.10174581457659797** (displayed as 0.10175). The incumbent is contextual, not a
   new matched control. Equality fails.
2. **Camera:** MAE in degrees for the **median camera decoder**, computed as the mean of
   yaw and pitch mean absolute errors over their known frames. “Median” names the decoder;
   this is not median absolute error. Candidate must strictly beat both its paired control
   and **zero motion, 1.2246451263967797°**, in every seed. Its arithmetic seed mean must
   also beat both the control seed mean and zero. Equality fails. Report yaw and pitch
   separately so a pitch gain cannot conceal worse yaw.

**CONFIRMED requires both primary criteria.** A valid complete six-run set failing either
is NOT_CONFIRMED. Missing/duplicate/wrong-seed, nonfinite, stopped or mismatched inputs
produce no verdict. Report all six values, three paired differences, both seed means and
each primary pass/fail; no subset of seeds may replace this rule. This is an offline
repeatability decision with three seeds, not a significance claim or live clearance.

## Secondary measurements and chance floor

- Fixed-.5 self-fed press F1, press-rate ratio at both fixed and TRAIN cutoffs; per-action
  rates and aggregate predicted/human press counts. The ratio uses the ten TRAIN-supported
  live actions, whereas primary F1 uses six EDGE_ACTIONS.
- Frozen-dev human base rate: **2,458 live-action press events / 24,556 frames =
  0.1000977358 events/frame** (100.0977 per 1,000 frames). Six EDGE_ACTIONS contribute
  **1,437 / 24,556 = 0.0585193028 events/frame**. Multiple actions can press on one frame;
  these are event rates, not binary any-press probabilities. Also report the binary human
  any-live-press frame rate and its all-live-press-known denominator from the chance-floor output.
- **Rate-matched random-presser F1**, separately for `train_chosen/median` and `fixed_0.5/median`:
  preserve each of the six actions' exact predicted press count in each original run;
  choose that many eligible valid, press-known frame positions uniformly without replacement.
  Score with the same ±1 one-to-one matcher and macro rule. Use **256** replicates,
  Python `random.Random(20260927 + replicate_index)`, fixed run/action order. Report mean,
  empirical p05/p95 and matched counts. The percentile interval describes Monte Carlo
  random-presser scores; it is not a confidence interval on model skill. This is a
  rate-matched event-prediction chance floor, not an executable random pad controller.
- Complete six decoder conditions per run: fixed .5 and TRAIN cutoffs crossed with
  median, mode, expectation. Only the prespecified median condition enters the primary rule.
- Same real-vs-zero visual conditioning NLL: yaw, pitch, moving axes, pooled and positive
  press NLL. Report limitations of out-of-distribution zero features and do not gate on these.
- Show zero, persistence **0.4182705674010174°**, and TRAIN-fit AR2 **0.379686931050697°**.
  Persistence and AR2 use **true human history**, which the no-history candidate does not get.
  They are privileged reference baselines, not the primary camera comparator.

The prior persistence stop remains an operational trigger: if any summary beats persistence,
save it, name every skipped decode and notify the lead immediately before further work.
The current evaluator constructs all six rollout streams before summarizing, so skipped
means **skipped metric summaries**, not avoided inference. An interrupted set receives no
confirmation verdict; no outcome-driven replacement or extra arm is authorized. Already-running
paid siblings remain bounded by their guards; the lead decides continuation. No result is read
before the judge review. The monitor must not suppress or mislabel a trigger.

## Judge pins and validation

The judge is `policy/range_bc/confirm_encoder_judge.py`, landed in the source commit above.
SHA256 pins use canonical LF bytes (CRLF → LF); downloaded/result artifact hashes use raw bytes.

| Source | SHA256 |
|---|---|
| Judge | `6f2187dd974befedbaf656470d7b153f3a5ca7be0a62a3954a67670ab726aa32` |
| policy/range_bc/metrics.py | `ff8ec1788700392a2490d39d19ecc623cea85094adbd23873aefb30420e2a2e5` |
| policy/range_bc/vocab.py | `9f57c02a977921cc0f8fef003a19eb647136ff51af34a7913f76fb22ec811f3e` |

Before launch, the independent reviewer checks this judge and its chance-floor/evaluation
integration using synthetic inputs; no confirmation results exist to inspect. The judge CLI
checks these source pins, this preregistration's hash, each evaluation and final receipt hash,
successful exit and terminal teardown, and the collector's evaluation hash. It rejects seed 0,
missing runs, wrong recipe/cohort/frame counts, mode mismatches, changed assets between runs,
incomplete decodes and nonfinite primary values. The final JSON embeds its input manifest.

Synthetic validation: **55 tests passed**, including primary means/per-seed direction, ties,
zero baseline, incumbent context, input rejection, chance-floor masks/counts/run boundaries,
source and artifact authentication, seed/history propagation, six disjoint configs,
unchanged budget function AST and both deadline clocks. Ruff passed the changed source/tests.
Tests: `tests/test_confirm_encoder_judge.py`, `tests/test_confirm_encoder_launch.py`,
`tests/test_range_bc_explore_chunks.py`, `tests/test_explore_encoder_launch_fixes.py`.

Invocation after reviewed results are collected:

```sh
python -m policy.range_bc.confirm_encoder_judge --runs runs.json --out judgement.json
```

`runs.json` contains `judge_sha256`, `dependency_sha256` keyed by
`policy.range_bc.metrics` / `policy.range_bc.vocab`, `preregistration` path, `prereg_sha256`,
and six `runs` entries with `arm`, `seed`, `evaluation`, `evaluation_sha256`, `final`,
`final_sha256`. Every checkpoint/evaluation carries this prereg hash in `encoder_explore`.

## Funded launch and teardown

Hard campaign cap **$20**, six disjoint **$3.33** caps (no redistribution/retry).
Each unchanged reviewed guard reserves .75 setup plus 3,594 s × **$0.00071784/s** =
**$3.32991696**; total **$19.97950176**, with $0.02049824 unallocated headroom.
The rate is L40S .000542 + 8 CPUs × .0000131 + 32 GiB × .00000222 per second.
300 s startup and 120 s teardown are inside each lifetime; function timeout 3,174 s.
Two-clock guard, independent watchdog, worker stop/kill and owned-app teardown are reused.
These are conservative allocations, not invoices. Expected actual allocation is about $12.6
from the completed ~31-minute/~$2.1 runs; no additional speculative fit is funded.

Immutable image **`im-FNjy4v5u4XYF29SBGvT0KD`**:
torch 2.14.0+cu130 / CUDA 13.0, transformers 4.57.1, safetensors 0.6.2,
huggingface-hub 0.35.3; Modal SDK 1.5.5. One L40S, 8 CPUs, 32 GiB, max one container,
single use, retries=0, min/buffer containers=0, scale-down 10 s. Runner manifests pin image,
packages, source archive, config, vendored job-status helper and all launcher files.

Launch copies are committed under this directory's `launch/`. `prepare_confirm.py` only
creates six fresh local directories and manifests; it never calls Modal. It requires this
prereg path, a `git archive` of the pinned implementation commit and that commit SHA.
Proposed Mac campaign parent:
`/Users/james/dev/range-bc-data/explore/nitrogen-nohistory-confirm-20260927/`.
Children `candidate-s1`, `control-s1`, `candidate-s2`, `control-s2`, `candidate-s3`, `control-s3`.
App names `rivals-nitrogen-confirm-{candidate|control}-s{1|2|3}-20260927`, each with its own
`-outputs` volume. No existing app/output volume is mutated. Read-only input volume
`rivals-explore-chunks-20260927` / `vo-K5FeMtunP9vFG2mx8HVn0p`; CM3 volumes remain exclusive.
Profile `rivals`, workspace `volpestyle`, workspace ID `ac-kMLf5bJKqF5CAlSbfNhGh0` verified
by the existing lifecycle client before writes.

Run the six fits concurrently after staggered AppCreates. Coordinate a fresh creation window
with CM3 and IDM; honor **at least 15 s globally between attempts**, announce each actual
app ID/time, and keep the existing reviewed gate: RPC ≤15 s, only typed ResourceExhausted
retry with stable idempotency key inside funded startup, no automatic fit retry.
The six children share a parent lock; other lanes' parents **do not** share it.
Driver, config, guard, teardown and collector paths are each child's `encoder_driver.py`,
`run-config.json`, `encoder_budget.py`, `encoder_lifecycle.py`; collection is in the driver.
After completion verify exact owned apps stopped, tasks zero, no owned containers, and
hash-check streamed artifacts against worker receipts. Unproven teardown blocks retries.
Report a conservative campaign allocation warning at **$18**, before the $20 ceiling.

## Weekend allocation carried to the lead's ledger

| Completed explore work | Conservative allocation USD |
|---|---:|
| Full-cohort H1/H4/H8 and prior failed/stopped/setup allowance | 26.732 (rounded) |
| SigLIP/NitroGen history-enabled pair | 4.2158155374 |
| SigLIP/NitroGen no-history pair | 4.2008284585 |
| **Completed cumulative explore** | **approximately 35.1486439959** |

The original chunk figure is rounded; extra decimals do not imply billing precision.
This excludes CM3/IDM and retained storage. The lead owns the combined **$150 weekend**
ledger. Adding this confirmation's full $20 authorization puts this lane's conservative
completed-plus-authorized ceiling at approximately **$55.1486**. No code here claims to
enforce the cross-lane total; lead approval must fit it within the remaining weekend budget.

## Interpretation limits and next action

This repeats a selected seed-0 candidate on the same frozen dev, not an untouched test set.
Report selection bias, three-seed uncertainty, both camera axes, human rate and chance floor.
The successful offline outcome permits discussion of the next reviewed dispatch only;
it does not authorize live input, an explore-format live adapter or sealed evaluation.
If confirmation fails, report it with all seeds. Do not start another explore round.
