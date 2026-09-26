# fit-interim-prereg (VUH-1346, VUH-1359): the 94-minute interim fit, pre-registered before any training

**This is an interim scaling-curve point, not the real fit. Nothing from it is a policy acceptance or a live-pilot
candidate.** No training has run. Waiting for the lead's OK.

## Recipe (fixed, unchanged for the larger corpus)

**The derived pre-registration as-is:** `docs/evidence/range-bc-plumbing-20260924/preregistration.json` (`e1b2cefb…`).

| Setting | Value |
|---|---|
| epochs | 13 |
| weight decay | 1e-4 |
| stride | 64 |
| lag | 0 |
| seeds | 0, 1, 2 |
| batch | 8 |
| lr | 3e-4 |
| regimes | normal |
| device | MPS |

**HUD parity:** `docs/evidence/range-bc-plumbing-20260924/hud-parity-1-p2.json`, exact CRLF bytes `e9efe999…`,
passed with `--hud-parity`. It fails, so the no-HUD arm stays the candidate.

**Arms:** `model_nohud` (the candidate) and `history_only` (the twin), the p5 pair.

**Scope: `--scope plumbing`**, as the p5 runs: dev only, validation unread. `--scope fit` cannot run this:
- it requires validation recordings, all three arms, and committed code in a git checkout (`require_committed`);
- the Mac runs from a `git archive` outside every checkout.

**Consequences of that scope:**
- the report does not bind `preregistration.json` (its `preregistration` is null at plumbing scope);
- `cache_hashes_verified` is false.

**How I make up for both:**
1. Every cache is re-hashed (`open_cache(verify_hashes=True)`) before launch, and the hashes are recorded.
2. After the run, each report's config is checked to equal the pre-registration's epochs, weight decay, stride, lag
   and seed, and its `hud_parity.sha256` to equal `e9efe999…`.

**Code:** a `git archive` of `5d2ec29` on the Mac, in `/Users/james/dev/range-bc-data/code-5d2ec29`, with its own
`uv sync --locked --group execution`. `policy/range_bc`, the step tables, the denylist and
`data/human/patch-equivalence.json` (tracked, pin `4df869f3…`) are unchanged from `5d2ec29` to today's `baf651c`. The
cohort is read through the patch-equivalence file: both game builds, one kit version, "Season 10, Version 20260911".

## Dev: the plumbing fit's dev, unchanged

**Dev = 171533 + 205528.** These are exactly the plumbing fit's dev recordings: 13.64 counted min, 24,735 rows, 383
windows at stride 64. The plumbing pre-registration froze this dev list through the real fit, so the interim
reports on the same dev.

**Train = the other five,** 80.53 counted min. So "the seven-session cohort" (94.17 counted min, 169,513 accepted
rows) splits as 80.53 train plus 13.64 dev.

**Please confirm this dev.** Your brief calls all seven the train cohort. With dev held out, as in every plumbing
curve, train is five.

## Exact cohort (step tables on `5d2ec29`, all split "train", loaded with the pinned denylist and patch-equivalence file)

| Session | Role | Step-table sha256 | Rows | Accepted | Counted min | Build | Media sha256 (= `expected_media_sha256`) |
|---|---|---|---|---|---|---|---|
| 20260923T051828-422Z-33696-1 | train | `d49224e3c4382a62ebb4c4252bcc5800138782688e1d0f60e03e46ce4b6e7edb` | 12,558 | 12,550 | 6.97 | 1.1.3870120/build25364676 | `ad14e5bc…` |
| 20260923T200129-346Z-33696-6 | train | `fcc9b0443e720648b899453ea3f04f82c0a6dd1735f30a420a36b3675549ba8e` | 48,195 | 47,910 | 26.62 | 1.1.3870120/build25364676 | `b06621fe…` |
| 20260924T232304-170Z-12024-1 | train | `8a6c63d4024b13d5b73ab0154f434782e6cfc853d6eaa8291bd9fa8ca8f3b1b1` | 15,841 | 15,777 | 8.76 | 1.1.3892207/build25501035 | `58f8e234…` |
| 20260925T021320-371Z-7804-1 | train | `841fe6953cf473e55c6becfe24143259fa48dca639bb9387bc04615edf6ea537` | 65,702 | 62,126 | 34.51 | 1.1.3892207/build25501035 | `a1a89dd3…` |
| 20260925T025230-605Z-7804-2 | train | `84cef39b81ce8a40637bb5cf9766cdfc6f4054b32cda5d94ac1082329434c288` | 6,667 | 6,594 | 3.66 | 1.1.3892207/build25501035 | `c6adfd57…` |
| 20260923T171533-187Z-33696-5 | **dev** | `dc28b0c1511f7847c8dde08c3e04addce8b57bc6c32cc2873405962d3235559e` | 4,800 | 4,630 | 2.57 | 1.1.3870120/build25364676 | `3f8e4087…` |
| 20260923T205528-900Z-45572-3 | **dev** | `941950f16edef6a88b14d6bc536e33a66a0e779867fa145c78e7142164e1fd98` | 19,935 | 19,926 | 11.07 | 1.1.3870120/build25364676 | `bf32202a…` |
| **Total** | | | 173,698 | **169,513** | **94.17** | | |

- The four earlier step tables are byte-identical to the plumbing fit's, on the Mac too.
- The three new ones are sent with their media.

## Run plan

**Invocations.** One `train.main` per seed, each with both arms, as the p5 runs were. So there are **three reports
holding six checkpoints**, not six reports: `train.main` refuses a twin-only run ("train at least one model arm"), so
a twin cannot have its own report.

```
uv run --offline --locked --group execution python -m policy.range_bc.train --scope plumbing --device mps \
  --cache-root $D/caches15 --batch 8 --lr 0.0003 --regimes normal \
  --train $S/<051828> $S/<200129> $S/<232304> $S/<021320> $S/<025230> --dev $S/<171533> $S/<205528> \
  --arms model_nohud history_only --seeds <k> --epochs 13 --weight-decay 0.0001 --stride 64 --lag 0 \
  --hud-parity $P/hud-parity-1-p2.json --out $R/interim94-seed<k>          # k = 0, 1, 2
```

**How it runs:** one durable queue (`nohup nice -n 10 zsh …`), launched from Git Bash ssh with
`ServerAliveInterval=15`, with a `.log` and `.exit` per run and a status file. It first checks that no other
rivals-agent job is running.

**Option B (recommended, needs your OK): a same-recipe 47-minute control.** The same three invocations, but with
`--train` 051828 + 200129 only (33.59 min, 945 windows, 1,547 steps), the same dev, and out `interim94-control47-seed<k>`.
- **Why:** no plumbing run used this recipe. p1 is stride 48 on a 20-epoch schedule. p5 is 1,580 fixed steps at stride
  48 with the cosine schedule ending at step 1,580, 2 seeds. So the doubling comparison is confounded by the recipe
  unless the 47-minute point is re-run with it.
- **Cost:** about 1.2-1.4 h. The control is what makes "closes as data doubles" a like-for-like reading.

## The reading (pre-registered; descriptive, no gate)

**Per arm, per seed, and the mean with range over the 3 seeds, all on dev from each report:**
1. **Dev total loss:** at the end (epoch 13), plus the per-epoch curve's argmin epoch and minimum. Per head at the end.
2. **Teacher-forced macro press-F1** (`macro_press_f1_tol`, the `all` stratum).
3. **Teacher-forced camera MAE** (`camera_mae_mean`, degrees; the slow-turn degree caveat applies).
4. **The baselines from the same reports:** ar2 and persistence camera MAE and F1. Dev is unchanged, so these should
   equal the plumbing record (ar2 0.376°, persistence 0.418°, F1 0).

**The question: does the picture arm close on the twin as data doubles?** It is read from two gaps:
- `Δloss` = no-HUD − twin dev total loss at epoch 13;
- `ΔF1` = no-HUD − twin teacher-forced macro press-F1.

Each is a mean over seeds, with the per-seed values.

**Rules:**

| Outcome | Condition |
|---|---|
| **Closes** | `Δloss` at 80.5 train min is lower than at 33.6 by more than the two points' combined seed ranges |
| **Reverses** | `Δloss` < 0 at 80.5, with every seed below 0 |
| **Opens** (F1) | `ΔF1` at 80.5 exceeds `ΔF1` at 33.6 by more than the combined seed ranges |
| **Not resolved** | anything within the seed ranges, stated as such |

- **Which 33.6-minute point:** with Option B, the same-recipe control. Without it, the plumbing points, with the recipe
  confound stated in the result: p1 seed 0 `Δloss` +0.032 at epoch 13 (1.4310 − 1.3994); p5-all `ΔF1` +0.005.
- **Camera:** whether either arm's camera MAE beats persistence (0.418°) or ar2 (0.376°). At 47 min neither did.
- **Recipe health, reported and not acted on:** the no-HUD dev curve's argmin epoch. If it is well before 13
  (overfitting), or still falling at 13, the recipe may be wrong at this size, and I say so.

## Expected wall time (Mac, MPS, niced; estimates from the plumbing record, which ran 16% over its own estimate)

| Step | Time |
|---|---|
| Media transfer (the three new videos, 42.9 GB), in progress now | about 25-30 min |
| Code archive, `uv sync`, re-hashing the four reused caches (about 18 GB), building the three new caches (about 49 recorded min) | about 15-20 min |
| **The six runs:** per seed about 47 min no-HUD (3,692 steps at about 0.72 s + 13 dev passes) + 1 min twin + about 1.5 min evaluation | **about 2.5 h, about 2.9 h with the plumbing margin** |
| Option B control | + about 1.2-1.4 h |

## Already running (allowed in parallel with step 1)

**Media transfer:** Git Bash `sha256sum` and `scp`, copies only.
- Each video must equal its `expected_media_sha256` before it is sent.
- The logger files and the three step tables go with it, to `/Users/james/dev/range-bc-data/{originals,steps15}`.

**Next, still before any training:**
1. Verify on the Mac.
2. Build the three caches with the landed `policy.range_bc.cache` (Homebrew ffmpeg 8.1.2_1).
3. Re-verify the four existing caches' hashes against today's step tables.
4. Record all seven cache hashes.

No run starts before your OK.
