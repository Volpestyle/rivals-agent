# L6 — offline integration and eval

**Status: replay done and reported; eval reader done with a finding attached.**
Nothing in this lane touches the PC desktop or sends input — it reads frames L1
already recorded, pulled over SSH.

Owned here: `perception/replay_states.py`, `perception/evalread.py`,
`tests/test_replay_states.py`, `tests/test_evalread.py`, this file.

## What runs

```sh
# recorded run -> State JSONL the brain can load
uv run --no-project --with opencv-python-headless --with numpy \
    python -m perception.replay_states data/run1 data/l6/run1-states.jsonl --finder outline

# the scripted brain over those States
uv run --no-project python -m agent.replay data/l6/run1-states.jsonl --json

# what the screen honestly says about the run's outcome
uv run --no-project --with opencv-python-headless --with numpy \
    python -m perception.evalread data/run1
```

The finder is a plain function argument, `frame_bgr -> list[Detection]`. The CLI
takes `outline`, `none`, or `yolo:<weights.pt>`; anything callable works from
Python. `none` writes `detections=None`, which is State's way of saying the
detector did not run, as opposed to ran and saw nothing.

## The first real-perception timeline (run1, 6360 frames, 636 s)

Perception over the whole run, `outline.detect` as the finder:

| | |
|---|---|
| frames read | 6360 of 6360 listed, 0 missing |
| cost | 14.0 ms/frame (HUD + finder + tracer, single thread, shared Mac) |
| hp unknown | 2.6% |
| max_hp unknown | 6.5% |
| webs unknown | 0.4% |
| ability `ready` unknown | 0.0–0.4% per slot |
| `on_target` unknown | **100%, by design** — see below |
| frames with an enemy box | 25.8% |
| enemy detections | 2317, tracer unknown on 4.4%, tagged on 2.4% |

The brain over those States at 10 Hz — **4078 ticks, 636 s, 403 intent
switches**:

| intent | seconds | segments |
|---|---|---|
| search | 346.6 | 196 |
| engage | 270.1 | 201 |
| combo | 18.3 | 6 |
| webstrike | 0.9 | 1 |

First attack at 0.6 s. Compare the synthetic story in `agent/replay.py`, which
walks every branch: on real perception the agent spends its life alternating
search and engage, and the close-range branches barely fire. The reason is the
first mismatch below.

Eval read over the same run: 25.8% of frames have a hostile marked, at most 6 at
once, minimum hp 250 (nothing ever hurt Spider-Man), ult charge full for the
entire run and therefore 0.0 gained. `damage_dealt` and `eliminations` are
`None` — see **The eval finding**.

## Interface mismatches found

Reported here rather than fixed: `agent/` is rivals-brain's, `detect.py` and
`outline.py` are rivals-det's.

1. **The brain's `near` distance band is unreachable with the finder that
   exists.** Across all 2317 enemy detections the box height / frame height was
   min 0.043, median 0.086, p75 0.121, max 0.350 — and `brain.NEAR_H` is 0.35,
   so `near` fired for no enemy at all and every one landed `mid` (1353) or
   `far` (964). That is why `combo` ran 6 times and `webstrike` once. Two causes
   compound: `NEAR_H`/`FAR_H` are marked as guesses in `brain.py`, and
   `outline.py`'s body box is visibly short — in `data/run1/000334.jpg` the bot
   is at melee range and its box covers head to waist, about 0.167 of frame
   height. Either the constants want calibrating against the finder's boxes, or
   the finder's `BODY_H` wants raising; measuring one against the other is the
   fix, not moving one blind.
2. **`agent/replay.py` discards a third of a 10 fps recording when asked for
   10 Hz.** The decimation test is `s.t - last >= 1/hz - 1e-9`, and L1's frame
   spacing jitters either side of 0.1 s — 3181 of 6359 gaps in run1 are *under*
   0.1 s, so they fail the test and the tick is dropped: 4078 ticks from 6360
   frames, a reported 6.41 decisions/s for a 10 Hz replay of a 10 fps
   recording. Lowering `--hz` makes it worse, not better. A tolerance
   (`>= 0.9 / hz`) or snapping to the nearest tick would keep them.
3. **`outline.py` boxes the player.** The three largest "enemy" boxes in run1
   (`002485`, `005437`, `005438`) are Spider-Man's own suit or empty ground, not
   bots — see `docs/evidence/l2/l6-outline-false-positives.png`. The aspect-ratio
   player-exclusion rule holds most of the time but not always, and because
   these are the *largest* boxes they are exactly the ones a distance heuristic
   weights most.
4. **`on_target` cannot be read, so this lane always writes `None`.** The
   crosshair is the same small white square whether or not a hostile is under
   it — checked across 1544 frames including 32 where an enemy box covers screen
   centre. `brain.aimed_at` already falls back to crosshair-in-bbox geometry
   when `on_target` is None, which is the correct behaviour; the field is simply
   not perceivable and nothing should wait for it.

Non-mismatches worth recording: `State.from_dict` round-trips `Detection.tagged`
correctly, and `Hud.state_kwargs()` plugs straight into `State(t=..., frame=...)`
with no adapter.

## The eval finding

**Damage dealt and eliminations are not on screen in the practice range.** This
is a property of the game mode, not a gap in the reader, and it was checked
against all 6360 run1 frames and 347 trial1 frames:

- No scoreboard. The mode draws the player's HUD and the bots' nameplates. A
  scoreboard needs TAB held, which is input, which is not this lane.
- No kill feed. The top-right holds the FPS/ping overlay and nothing else.
- No damage counter; floating damage numbers drift from the hit and fade, so no
  fixed region holds them.
- **A nameplate vanishing is not an elimination** — it happens 511 times in
  run1's 636 s, because the camera turns away.
- The enemy health bar's red length shrinks with damage *and* with distance, and
  its empty part is not separable from the background at 720p, so it yields no
  fraction to difference into damage.

`perception/evalread.py` therefore returns `None` for both, by construction, and
reports what the screen does carry: hostiles visible, max at once, hp floor, ult
charge and the charge gained across a run. Ult charge is the only damage-shaped
number available and it is a proxy with an uncalibrated conversion — it is
reported as ult charge and never as damage.

To get real numbers, someone has to record frames with the scoreboard open. The
reader can be pointed at those frames when a lane that sends input produces them.

## Dead ends, so nobody repeats them

- **Crosshair on-target reader**: built as far as measuring, then dropped. No
  colour, ring or shape change; 1507 of 1544 frames show a plain white dot and
  the rest are background bleeding through it, with zero red ones.
- **Enemy health bar as a damage source**: the red component's width is
  confounded with distance and the slot behind it is not reliably dark. Measured
  on frames 334–360 of run1, where a bot visibly takes damage: red width goes
  126 → 107 → 106 → 105 px while the bot also gets further away.
- **Marker disappearance as an elimination signal**: 511 events in 636 s.

## Facts about the recordings

- An L1 run directory is `NNNNNN.jpg` frames beside `frames.jsonl`, one line per
  frame with `i`, `t` (seconds from run start), `file`, `step` and the `pad`
  state at that moment. `run1` is 6360 frames, 636 s, 1280x720, ~1.3 GB — pull
  it by zipping on the PC (`Compress-Archive`) and `scp`ing the archive; `rsync`
  is not available on the Windows side, and 1197 individual `scp`s is far slower.
- `frames.jsonl` is the place to find what the player was doing: `pad.lt > 0.5`
  marks web-cluster shots, which is how to find tracer-tagged bots. In `run1`
  the LT bursts around frames 50–70 and 207–225 hit scenery, but those around
  frame 334 tag Luna Snow.
