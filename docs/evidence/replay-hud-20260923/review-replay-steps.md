# Review: the first replay-source step table builder (DayMR)

Reviewer `admission-review` (Claude Opus 5.5), 2026-09-23. The review is read-only: nothing edited or committed,
no game input sent. Decoding and tests ran at below-normal priority, with ffmpeg on 4 threads.

## Bytes

**The bytes moved during the review.** At about 20:05 the builder, its test and the table were all rewritten.

| File | Brief | Now (reviewed) |
|---|---|---|
| `scripts/replay_steps.py` | `363eb624` | **`174ea3cb`** |
| `tests/test_replay_steps.py` | `bd834922` | **`45b3caf4`** |
| table | `4180dd6d` | **`b7b7a1a4`** (+1 byte: `"split": "replay"`) |
| `docs/lanes/replay-hud.md` | `9bb0c1e5` | `9bb0c1e5` (unchanged) |
| `build.json` | `4c43027a` | `00c84ddd` |

I diffed the functions by reading them, not with a file diff:

- **Unchanged labelling functions:** `frame_reasons`, `forgive_blips`, `included`, `build_runs`, `press_windows` and
  `label_rows`.
- **What changed:**
  - the split now comes from `steps.REPLAY_SPLIT`;
  - `fill_camera` gained `check_camera_run` and a pair-source filter;
  - the test gained the `load_cohort` refusal and the camera-hook tests.
- **The findings below were re-run on `b7b7a1a4`, with identical results.** Row and label counts equal the hand-back's:
  29,561 rows, 74 runs, and the same per-action 1/0 counts.

**Other inputs:**

- `perception/replay_hud.py` `30921c0c` (= HEAD, = the hud manifest's reader pin);
- `hud/events.json` `266f6de2`;
- `policy/range_bc/steps.py` working tree `82cca65d` (uncommitted, another lane's replay-split change);
- `policy/range_bc/train.py`.

**Tests:** `uv run --no-sync pytest tests/test_replay_steps.py` gave **17 passed** on the current bytes.

## Verdict: the builder is not ready to land. The split, the gradient and `expert_context` hold. The 0 labels and the withheld spans do not

The lead's heads-up confirms my first finding independently: the 112 ult zeros. I treat the builder's logic as the
thing under review. The numbers below say what the logic does to this input, and the rebuild must not repeat it.

| Question | Answer |
|---|---|
| 1. A false 0 outside max-count coverage or inside an exclusion window? | **Yes: 112 ult rows** (R1), plus the 0s on in-death rows (R2) |
| 2. Are 0s only where the mask says known? | **Yes, mechanically:** `press_known` is exactly `press is not None` on every row, for all 5 casts |
| 3. Do withheld spans never produce rows? | **No: dead spans do.** Up to 306 rows, **at least 284 confirmed on decoded frames** (R2) |
| 4. Zero gradient for movement and camera on a real slice? | **Yes** |
| 5. Is `expert_context` honest? | **Yes** |
| 6. Can the rows get into the human train split? | **No, at the current bytes** (with one landing-order condition) |

## R1 (required): a transition cast's press window ignores `t_lo`, so the steps before its first evidence get false 0s

**The flaw is in `press_windows`, for transition events:**
`lo, hi, est = t_hi - hi_lag, t_hi - lo_lag, t_hi - med`.

- **Why it is wrong:** `t_hi` is the first frame *read* after the change. When the reads in between are missing, the
  first evidence could lie anywhere in `(t_lo, t_hi]`. The press then lies in `[t_lo − Lmax, t_hi − Lmin]`.
- **Why it produces 0s:** `label_rows` blocks only `[t_hi − Lmax, t_hi − Lmin]`. The earlier steps are left to
  coverage. Ult coverage pairs any two reads under 60 s apart, whatever their state, so the ready→charging pair is
  itself "coverage".
- **The docs disagree with the code.** The docstring and §7 describe "the HUD interval widened by the lag's
  min..max"; only the countdown branch does that.

**On this table, with the true window per basis:**

| Ult cast (HUD interval) | Why the reads are missing | False 0s | Where the 1 is placed |
|---|---|---|---|
| 617.063-619.629 s | 307 frames of "viewer not following", forgiven as a bar blip | **76**, rows `pts` 617071-619571 | 619604 |
| 755.463-756.688 s | 146 frames of "viewer not following", forgiven as a bar blip | **36**, rows 755471-756638 | 756671 |

- The 0s sit exactly where the press probably happened; the 1 lands up to 2.5 s late.
- **No other ability has a 0 inside its true window.** GOH and team-up are countdown casts, handled correctly. Charges
  and ammo coverage needs max count at both ends, so a drop pair is never covered.
- **The positives are still misplaced** wherever the interval is wide. This affects 12 of 76 Amazing Combo, 47 of 263
  Web Cluster and 3 of 9 ult transition events wider than one step. Of those, 7 AC, 21 WC and 3 ult are wider than
  0.25 s, and 4 AC, 4 WC and 3 ult wider than 1 s.

**Required:**

- For transitions, use `lo = t_lo − Lmax` and `hi = t_hi − Lmin`.
- Place a 1 only when that window fits within about one step; otherwise null the whole window, with no 1.
- Add a test with a wide `t_lo..t_hi` whose earlier steps sit in coverage.

## R2 (required): "reader abstained" counts as a clean, alive frame, so rows run through deaths

**The mechanism has two halves:**

- **Abstained frames pass as clean.** `WITHHELD` omits "reader abstained", so `frame_reasons` gives those frames
  `None`: in the span.
- **Abstained frames also count as alive.** `forgive_blips` treats `None` neighbours as "alive reads", so an hp-0
  stretch of 0.25 s or less between *abstained* frames is forgiven as a misread.

During a death cam the reader alternates between hp-0 and abstained, so a whole death becomes rows.

**Found by clustering hp-0 frames:** gaps of at most 1 s, at least 30 frames, widened over the adjacent
abstained/no-HUD frames. **306 rows fall in 9 death regions.** Decoded frames confirm four of them:

| Death | Rows | Frames checked | Seen on screen |
|---|---|---|---|
| 529.96-539.95 s | **235**, runs b5-001..004 | 530.2, 533.5, 536.0, 539.0 | KO banner, then the death cam at the death spot; 0/250 HP; respawn timer 7→5→2 on the scoreboard |
| 1213.6-1214.85 s | 36 | 1213.9 | 0/250, respawn timer 9 |
| 1335.25-1335.75 s | 3 | 1335.5 | 0/250, respawn timer 8, spectator view |
| 1477.54-1477.87 s | 10 | 1477.6 | Spider-Man KO'd on the floor, 0/250 |

The other five regions give 22 rows at death edges (759.2-761.9 s, 866.5, 1089.8, 1212.2-1212.5 and 1932.8 s).
Some of the 759-762 s rows may be alive: the frame I checked at 760.5 s shows play.

- **Labels on these rows:** 0 for team-up (**205 of the table's 344 team-up 0s**), ult (43), GOH (7), AC (17) and
  WC (2). "No cast while dead" is literally true, but these rows are exactly the withheld span the table promises to
  exclude, and they would teach "death cam → no action".
- **The test is circular, so it cannot catch this.** `test_withheld_spans_are_absent` re-derives its expectation
  through the builder's own `frame_reasons` and `forgive_blips`.

**Required:**

- Neither an alive neighbour nor a span may rest on "reader abstained". A blip is forgiven only between frames
  actually read alive (HP > 0).
- Treat an hp-0 cluster, widened over contiguous abstained frames, as dead.
- Add a test independent of the builder's code:
  - no row falls inside an hp-0 cluster built as above;
  - pinned death intervals, e.g. 529.96-539.95 s, have no rows.

**Rows I would refuse** in any table built from this logic:

- every row in those death regions (306 here);
- the 112 ult 0s from R1.

## R3 (required for negatives): coverage bridges withheld frames and seeks

`cast_events` coverage pairs consecutive *reads* up to the hide time apart (ult 60 s, team-up 15 s, GOH 8 s,
charges 6 s, ammo 2 s), across any frames that were not read:

- **Team-up** 0s rest on a 10.0 s read gap spanning 1,203 dead frames.
- **Ult** 0s rest on a 10.0 s gap spanning other-POV and dead frames.
- **Web Cluster's** 2 zeros rest on a 1.64 s gap spanning hp-0 frames.
- **Ult:** 15 gaps of more than 1 s go charging→charging. A ready-and-cast inside one would leave no event and still
  count as coverage, and the reader has no ult percentage to rule that out.
- **Seeks:** coverage pairs are not split at seeks. The reader has an Amazing Combo "transition" spanning
  1504.5-1630.8 s across a seek. It is not placed and not covered, so it does no harm here.

**What I checked:**

- No 0's evidence window crosses a seek or an EXCLUDE boundary.
- No run crosses a seek.
- These negatives rest on game assumptions: cooldowns persist through death, and there is no hidden charge-and-cast.
  Neither assumption has been measured.

**Required, in the reader's press-coverage fix:** end coverage at withheld frames (other POV, dead, timeline), and
at seeks, EXCLUDE spans and capture gaps, not only where reads are missing.

## What holds

**Q2, masks.** On all 29,561 rows, for all five casts, `press_known[c]` is exactly `press[c] is not None`.
Everything else holds too:

- `held_known` and `release_known` are all False;
- movement, jump, both swings, spider_power, melee and goh_targeting are null in `press` on every row;
- `yaw_deg` and `pitch_deg` are null on every row.

**Q4, gradient.** `train.Batches` builds `act_mask` from `act_known` (known, press_known, release_known) and
`camera_mask` from `camera_known`, so both are zero by construction on these rows.

- The test's real slice is the run with the most known labels, up to 1,000 rows. On it, the fit lane's
  `loss_terms` gives exactly zero gradient on movement and camera, and a non-zero gradient on the casts.
- I re-ran it: it passes.
- `fill_camera` is not applied to the table.

**Q5, `expert_context`.**

- `viewer_fov_assumption: "viewer, unverified"`, the player, the match and the replay source are all present.
- The calibration says camera and movement are "none", with the reasons.
- Nothing in the header claims degrees, a FOV or settings it doesn't have.

**Q6, split.**

- **The original `363eb624` wrote `split: "train"`.** Under HEAD's `steps.py`, a replay-only cohort with
  `splits=("train",)` would have loaded it as train. It would never have mixed with the human data, because a cohort
  holds one source kind.
- **At `174ea3cb`** the table carries `split: "replay"`. The working-tree `steps.py` (`82cca65d`):
  - refuses any other split for a replay source;
  - refuses the replay split in every cohort unless `allow_replay` is passed;
  - is never called with `allow_replay` by any code.
- **I found no loader that globs `data/demos/replays`.**
- The test asserts the `load_cohort(splits=("train",))` refusal.
- **Condition:** the builder must land with or after that `steps.py` change. Before it, the builder fails closed,
  because HEAD's `steps.py` has no `REPLAY_SPLIT`.

**Also sound:**

- **The clock:** 0 unmapped frames, residual 0.33 ms or less.
- **Runs:** none crosses a seek, and there are no rows in EXCLUDE spans or route-map off-target seconds (bar the
  forgiven bar blips).

## Also needed

- **Two stale docs:** `docs/lanes/replay-hud.md` §7 (still `9bb0c1e5`) and the hand-back both still say
  `split: "train", my choice`. Update both.
- **The bar-blip forgiveness itself is defensible.** It is the route map's rule, and the 617 s ult sits in a 2.57 s
  bar blip, as though the ult's VFX hid the bar. After R1, labels inside such blips must come only from R1's widened
  windows.

## Review aids (scratchpad, not the repo)

- `rsteps.py` through `rsteps7.py`: the independent mask, coverage, true-window, seek, withheld and death-cluster
  checks.
- `rsf/*.jpg`: the decoded frames.
