# Observed option status: before and after (VUH-1315)

`Combo`, `Pull`, `WebStrike` and `SwingTo` used to be held for a guessed time (3.0 / 0.8 / 0.8 / 1.2 s). Now each is an option.
Evidence ends it: a KO on the kill feed, the target's arrival, its loss or a retreat. The old time is kept only as a named upper
bound. The rules, the status structure and the residuals are in
[docs/lanes/l5-brain.md, "Observed option status"](../../lanes/l5-brain.md#observed-option-status-vuh-1315).

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
  - The decision's own frame was not saved. So this tree reads the kill feed from the latest saved frame at or before each
    decision: p50 0.046 s and at most 0.120 s earlier on plaza30. A KO is therefore seen up to that much later than live,
    never earlier.
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

| | Base (hold) | This tree (option) |
|---|---|---|
| Kill feed | not read | saved frames: False to 1.935, `None` 2.034, True from 2.111. Decisions read False on 1.998 and True on 2.111 and 2.234 |
| The option ends | hold to 3.400 | **completed, `ko_feed`, at 2.234**: "kill feed False at 1.998, True at 2.111, 2.234" |
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
| `Combo(56)` at 22.531, armed at 22.668 | held to its 3 s bound (25.531), then re-issued by the flicker grace to 25.866; RT held to 25.585, LT at 25.651 | **completed, `ko_feed`, at 25.075**. The stop takes effect on the row the decision stood on (25.155); the last press is 25.134 |

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

`tests/test_options.py` has one test per acceptance point, 29 stdlib tests plus the corpus test. `mutation.py` (`mutation.json`)
breaks one line at a time, and **12 of 12 mutants are killed**, while the unmutated copy passes:

- a KO does not end the option;
- a KO is never confirmed, or is confirmed on one True read;
- a lost target does not end the option;
- arrival does not complete;
- an unread bound reads `failed`;
- a KO stops only a running option's primitive;
- every ending stops the primitive;
- the flicker grace re-issues a completed option;
- the controller ignores `stop`;
- the loop reads the feed in range-skill mode;
- the loop passes no `stop`.

## Range-skill mode is untouched

- `test_the_slot4_range_replay_is_identical_to_the_base_commit` (corpus) replays slot 4's 1068 range steps through the base.
  Reasons and pads are identical to the recording. This tree's rows equal the base's in the legacy and observe modes of
  `docs/evidence/range-fragment-repair-20260922/replay.py`, and in its review scenarios.
- `test_range_skill_mode_reads_no_kill_feed_and_passes_no_stop`: a reader that raises is never called. Logged states carry
  `kill_feed: null`, `stop` never reaches `Controller.step`, and the pads equal a run with no reader.
- `test_the_range_skill_brain_decides_the_same_whatever_the_kill_feed_reads`: `LearnedRangeSkillBrain` gives identical intents,
  traces and memory for any feed sequence.
- `tests/test_tracked_body_execution.py`, `tests/test_range_skill_loop.py`, `tests/test_range_skill_policy.py` and
  `tests/test_options.py` with `torch` available: **344 passed, 0 skipped**.
