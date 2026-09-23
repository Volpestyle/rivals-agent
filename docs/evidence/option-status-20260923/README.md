# Observed option status: before and after (VUH-1315)

`Combo`, `Pull`, `WebStrike` and `SwingTo` used to be held for a guessed time (3.0 / 0.8 / 0.8 / 1.2 s). Now each is an option.
Evidence ends it: a KO on the kill feed, the target's arrival, its loss or a retreat. The old time is kept only as a named upper
bound. The rules, the status structure and the residuals are in
[docs/lanes/l5-brain.md, "Observed option status"](../../lanes/l5-brain.md#observed-option-status-vuh-1315).

**The invariant.** The ending option's own remaining presses are removed; later choices may start sooner.
- A KO stops a burst's primitive, even one whose option already ended on track loss.
- A pull's or a web strike's rest is a wait, so nothing is stopped for them, on a KO or on arrival.
- An option that ends early reopens the choice sooner.
  - That choice can re-commit a burst on the same decision. `tests/test_options.py` pins this as accepted behavior (review F1).
  - Neither recording has a row where the branch sends an attack input the base does not. The base sends 33 such rows on
    trial 0 and 24 on plaza30 that the branch does not (`summary.json`, `attack_rows_tree_only` and `attack_rows_base_only`).

**Sequencing.** This branch lands after the next candidate's pilot. `agent/brain.py` and `agent/loop.py` feed the checkpoint's
selector and perception identity hashes, so landing earlier would change the identity the pilot was bound to.

## Reproduce

From the repository root. The recordings are read in place under `C:\rivals-agent\data` and never copied. No input is sent.

```
uv run --offline --no-project --with opencv-python-headless --with numpy python -B docs/evidence/option-status-20260923/feed.py
uv run --offline --no-project python -B docs/evidence/option-status-20260923/run.py
uv run --offline python -B docs/evidence/option-status-20260923/mutation.py
uv run --offline pytest --corpus tests/test_options.py::test_the_slot4_range_replay_is_identical_to_the_base_commit
```

- `feed.py` reads `perception.scoreboard.is_killfeed` on every saved frame of the two recordings and times each read. It writes
  `feed-trial0.json` and `feed-plaza30.json`.
- `replay.py` replays one recording through one `agent/` tree's Tracker, brain and Controller. `run.py` runs it for the base commit
  `0f71336`, whose `agent/` is exported by `git archive`, and for this tree, then writes `summary.json`.
  - plaza30 follows the order of `docs/evidence/l4/postfreeze30_replay.py`.
  - Only some decision frames were saved. So this tree reads the kill feed from the latest saved frame at or before each
    decision, compared at the log's 4-place precision. On plaza30 that frame is p50 0.040 s and at most 0.100 s earlier; 45 of
    304 decisions read their own frame. A KO is therefore seen up to that much later than live, never earlier.
  - 32 of plaza30's 304 decisions read the same saved frame as the decision before. Two True reads can therefore be one image,
    so the replay does not exercise the two-frame debounce in general.
    - The two plaza30 KOs are confirmed from two frames each: 000060 then 000061, and 000165 then 000166. Trial 0's is from
      000027 then 000028.
    - The review found the 25.075 KO confirmed from 000165 read twice. Rows log `t` to 4 places, so the decision's own frame
      000166 (25.0754) compared as later than its `State.t` (25.075384) and was skipped. The comparison now uses the log's
      precision, and `summary.json` lists each KO's frames.
- `mutation.py` breaks each rule in a copy of the tree and writes `mutation.json`.

Inputs (sha256):

| Input | sha256 | Saved frames read (digest over each file's sha256) |
|---|---|---|
| `C:\rivals-agent\data\l4\burst\log.jsonl` (burst trial 0, t 0-4 s) | `955b07c2…c7348027` | 53, `1c34defc…9885e92b` |
| `C:\rivals-agent\data\l1\plaza30\frames.jsonl` | `ee7d43e4…fcd2f25578` | 272, `08c250a7…bb5d72eb` |
| `data/l1/galacta-pilot-20260922-04-learned/frames.jsonl` (slot 4, for range-skill identity) | `1eadcb5e…9e071a6` | none |

`summary.json` holds the full hashes and the code's LF-normalized sha256.

## Burst trial 0: the issue's burst

This is the recording behind "the bot was already dead at about 2 s and the brain kept bursting". The live trial was a pad script,
not the brain. The replay commits the `Combo` through `brain.commit` on the first decision in the burst phase, at 0.400 s. Replayed
through the base, it reproduces every recorded trigger and button on all 138 rows: LT 0.471, RB 0.793, X 1.560, RT 2.111-3.412,
LT 3.450. The aim sticks differ, because the trial script aimed with its own code.

The base's hold did not run to its bound. It was cancelled on track loss at 2.348, and from then the base brain searched, while the
burst primitive played on to 3.450. Only `Idle` and `Disengage` cut a primitive there. So the brain-level gain is one decision (2.234
against 2.348), and the gain that matters is the stop. The option ended at the KO and its primitive stopped there. On the base the
option ended on track loss and the burst played on to 3.45 s.

| | Base (hold) | This tree (option) |
|---|---|---|
| Kill feed | not read | saved frames: False to 1.935, `None` 2.034, True from 2.111. Decisions read False on 1.998 and True on 2.111 and 2.234 |
| The option ends | hold cancelled on track loss at 2.348 (last held 2.234); the primitive plays on | **completed, `ko_feed`, at 2.234**: "kill feed False at 1.998, True at 2.111, 2.234" |
| Presses after the KO | RT 2.275-3.375, LT 3.450 | **none**: the stop cuts RT on 2.234 |
| Last attack press | 3.450 | 2.195 |

## plaza30: brain-chosen bursts, two KOs

This tree confirms a KO at 13.526 and at 25.075. Pads are identical to the base before the first KO. The replay reproduces every
recorded trigger and button: 1542/1542 rows through the base. Aim sticks match on 339 rows, because the replay is open loop and
the controller has changed since the recording.

| Option (replay ids) | Base | This tree |
|---|---|---|
| `Combo(1)` at 7.128 | cancelled at 9.787 (track lost) | interrupted, `track_lost`, at 9.787. Identical |
| `Combo(23)` at 13.112, never armed (no box after the choice) | held to 13.926, cancelled at 14.036 by loss | **completed, `ko_feed`, at 13.526**. `Engage(26)` (a far dummy) from 13.637 instead of 14.036. Nothing was playing, so no press changes |
| `Combo(56)` at 22.531, armed at 22.668 | held to its 3 s bound (lapsed at 25.570), then re-issued by the flicker grace to 25.866; RT held to 25.585, LT at 25.651 | **completed, `ko_feed`, at 25.075**. The stop takes effect on the row the decision stood on (25.155); the last press is 25.134 |

After each KO, the attack presses are identical up to 25.134. The base then presses RT to 25.585 and LT at 25.651, which this
tree does not. 600 of 1542 rows differ in all, and every one is at or after the first KO. After the stop, the differences are
sticks, because the brain chooses sooner.

**Without the kill-feed bit, this tree is the base.** Its pads match on 1542/1542 rows and its intents on every decision. No
arrival fired on plaza30, so nothing else could end an option early: the change is exactly options ending on evidence.

## Kill-feed read cost

This is the cost of `is_killfeed` alone on a decoded frame, which is what the decision worker adds per decision. It was measured on
this PC with the game stopped and sibling decode jobs running.

| Frames | p50 | p95 | max |
|---|---|---|---|
| plaza30, 272 native 2560x1440 (the live decision size) | 0.957 ms | 1.407 ms | 1.786 ms |
| trial 0, 53 at 1280x720 | 0.345 ms | 0.491 ms | 0.697 ms |

The budget is one decision per 100 ms at 10 Hz. plaza30's recorded decision compute was 48.66 ms p50 and 99.53 ms p95
(`meta.json`). The read adds ~1.4 ms at p95, 1.4% of the period.

## Rules pinned by tests; mutations

`tests/test_options.py` has 38 stdlib tests plus the corpus test. `tests/test_options_extractor.py` (perception group, 9 tests) runs
`brain._ko` and `perception.events._Channel` on the same kill-feed reads. They agree on every case, including:
- the brief's three: `F,None,T,None,T` confirms on read 4, a flicker confirms nothing, a line already up confirms nothing;
- the review's `F,T,T,T,F,T,T`: one KO, at read 2. One misread False inside a line is no second KO: after a KO, two Falses in a
  row re-arm it.

Accepted behaviors, pinned as observed (the lead's decisions on review F1):
- **A KO reopens the choice on the same decision.** A burst on a target still boxed, with RB and uppercut reading ready, restarts.
  - It adds an LT the base never presses (at 0.300) and restarts the burst 0.233 s late.
  - Test: `test_a_ko_reopens_the_choice_and_a_burst_on_a_target_still_boxed_restarts`.
- **Arrival ends a web strike and stops nothing.** Its wait holds the next attack exactly as the base did: RB 0.067, X 0.850,
  RT 1.433.
  - After the review, arrival no longer emits a stop, so the review's probe no longer moves X earlier.
  - Test: `test_arrival_ends_a_web_strike_but_its_primitive_plays_out`.
- **A KO confirmed on the commit tick is read before the choice**, so the new burst runs on. Test:
  `test_a_ko_on_the_commit_tick_is_consumed_before_the_choice`.

`mutation.py` (`mutation.json`) replaces one span at a time in a copy of the tree. It runs `test_options`, `test_brain`,
`test_tracker`, `test_jev`, `test_jev_async` and `test_loop`. The unmutated copy passes. Of 29 mutants, **28 are killed**: this
lane's 15 and 13 of the review's 14. The survivor, `loop_stop_when_stale`, is equivalent: a stale decision is `Idle`, which clears
the sequence anyway.

This lane's mutants:
- a KO does not end the option;
- a KO is never confirmed, or is confirmed on one True read;
- one False re-arms the KO detector;
- a lost target does not end the option;
- arrival does not complete;
- an unread bound reads `failed`;
- a KO stops only a running option's primitive;
- every ending stops the primitive;
- arrival stops the primitive;
- a web strike stops on a KO;
- the flicker grace re-issues a completed option;
- the controller ignores `stop`;
- the loop reads the feed in range-skill mode;
- the loop passes no `stop`.

The review's mutants are re-pointed where the fixes rewrote the mutated line, with the same intent. They include
`arrival_on_any_target_box` and `stop_on_ko_for_any_kind`, which survived the first round and are now killed.

## Range-skill mode is untouched

- `test_the_slot4_range_replay_is_identical_to_the_base_commit` (corpus) replays slot 4's 1068 range steps through the base.
  Reasons and pads are identical to the recording. This tree's rows equal the base's in the legacy and observe modes of
  `docs/evidence/range-fragment-repair-20260922/replay.py`, and in its review scenarios.
- `test_range_skill_mode_reads_no_kill_feed_and_passes_no_stop`: a reader that raises is never called. Logged states carry
  `kill_feed: null`, `stop` never reaches `Controller.step`, and the pads equal a run with no reader.
- `test_the_range_skill_brain_decides_the_same_whatever_the_kill_feed_reads`: `LearnedRangeSkillBrain` gives identical intents,
  traces and memory for any feed sequence.
- `tests/test_tracked_body_execution.py`, `tests/test_range_skill_loop.py`, `tests/test_range_skill_policy.py` and
  `tests/test_options.py` with `torch` available: **353 passed, 0 skipped**.
