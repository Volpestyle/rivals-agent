# L2 — HUD readers

## Event stream format

`data/demos/events/<clip-stem>.jsonl` is the agreed location, one file per clip,
written by `perception/events.py`. Three line kinds, told apart by `type`:

```jsonc
{"type": "meta", "source": "reqmr-2873352801-1920", "layout": "mk",
 "frames": 601, "fps": 10.0, "t_origin": "first frame of the media",
 "duration_s": 60.0, "segments": 4, "events": 84}

{"type": "segment", "start_i": 0, "start_t": 0.0, "end_i": 78, "end_t": 7.8,
 "started_by": "run_start", "ended_by": "death"}

{"kind": "ability_used", "i_from": 34, "t_from": 3.4, "i_to": 35, "t_to": 3.5,
 "slot": "swing", "amount": null, "before": true, "after": false, "segment": 0}
```

**Events carry no `type` key**, so readers already consuming them keep working.
Order is meta, then segments in time order, then events in time order.

- **All `t_*` are seconds from the first frame of the media**, not from the
  source VOD's start. All `i_*` are frame indices *at the sampling fps in the
  meta line* — not the source video's native frame numbers. The clips here were
  sampled at **10 fps** from 60 fps sources.
- **An event is an interval, never an instant**: `i_from`/`t_from` is the last
  frame showing the old value, `i_to`/`t_to` the first showing the new one. The
  press happened somewhere between. At 10 fps that is about 100 ms wide.
- `segment` on an event is the index of the segment line it belongs to. **No
  event ever spans a segment boundary**; channels reset at each one.
- `ended_by` is one of `run_end`, `death`, `killcam`, `spectating`,
  `scoreboard`, `not_our_hero`, `no_hud`. `started_by` is `run_start`,
  `respawn`, `killcam_over`, `spectating_over`, `scoreboard_closed`,
  `hero_returned`, `hud_returned`.
- Event `kind` is one of: `ability_used`, `ability_ready` (with `slot`),
  `charges_spent`, `charges_regained` (with `slot` and `amount`),
  `web_cluster_fired`, `web_cluster_reloaded`, `hp_lost`, `hp_gained`,
  `shield_decayed`, `shield_gained`, `max_hp_changed`, `ult_ready`, `ult_spent`,
  `death`, `respawn`.
- **`hp_lost` is damage only when hp is below max.** Where max hp could not be
  read, a shield tick still surfaces under this name: 68 of run1's 903 events
  (7.5%) are shield movement wearing an `hp_lost` / `hp_gained` /
  `max_hp_changed` label, every one of them at full health. The shield events
  proper are the ones where both numbers were read and moved together. In the
  practice range *nothing damages the player*, so any `hp_lost` there is a
  shield tick by construction.

This format is stable. Anything added will be a new key or a new `type`, never a
change to what is above.

## Status

**Done and accepted.** Waiting on one thing only: a run of deliberate
bot-tagging at varied distances, plus damage taken, at
`C:\rivals-agent\data\l1\tagrun\` on the PC (L4 is recording it, the lead will
say when it lands). That widens `read_tagged`'s calibration and supplies the
one missing digit template. Nothing depends on it.

`perception/hud.py` reads Spider-Man's practice-range HUD from one frame with
fixed regions and a template-matched digit classifier. No ML.
`tests/test_hud.py` passes on 145 hand-checked frames.

Owned here: `perception/hud.py`, `perception/hud_truth.json`,
`tests/test_hud*.py`, `docs/evidence/l2/`. Tracked as VUH-1294; the offline
integration lane that consumes these readers is `docs/lanes/l6-integration.md`
(VUH-1298).

## Results

145 hand-checked frames, from L1 runs `trial1` (70) and `run1` (75):

| field | coverage | wrong |
|---|---|---|
| hp | 0.979 | 0 |
| max_hp | 0.945 | 0 |
| bar_fill | 1.000 | 0 |
| webs | 0.986 | 0 |
| `ready`, all four slots | 0.993–1.000 | 0 |
| `charges` (swing, uppercut) | 0.979, 0.986 | 0 |
| ult_ready | 1.000 | 0 |

**Coverage** is the share of frames read correctly; a miss is a frame the reader
declined. **Wrong** is the share it answered incorrectly — zero on every field,
which is the property the readers are built for and the one the check asserts.

`read` costs **~4.3 ms** per frame measured quiet, `read_tagged` **~0.6 ms**;
both spread to tens of ms when several lanes load this Mac at once. Regions are
fractions of the frame and give identical answers at 960, 1280, 1920 and 2560
wide.

Full method, region table and annotated crops: `docs/evidence/l2/README.md`.

## What other lanes need to know

- **`Hud.state_kwargs()` fills `hp`, `max_hp`, `webs`, `abilities`** (with `ult`
  as an `Ability`). It deliberately leaves `frame` out — the caller owns the
  image: `State(t=t, frame=(w, h), **hud.state_kwargs())`.
- **`ult_charge`, `bar_fill` and the `teamup` slot stay on `Hud` and out of
  `State`** — the brain does not use them (lead's call). They are still read and
  still available to anything that wants them; `state_kwargs()` simply does not
  pass them on.
- **`read_tagged(frame, bbox)`** takes an `agent.state.Detection` box and
  answers whether that enemy carries a Spider-Tracer: `True`, `False`, or
  `None` when the band above the box falls outside the frame. It does not need
  the detector to be accurate to the pixel — the band is sized from the box.
- **Slot 1 is the team-up ability, not the Spider-Tracer.** Pressing Y turns the
  other icons gold and raises max hp by 50, which then decays back to 250 over
  about a minute. The tracer is a mark on an enemy, read by `read_tagged`. The
  slot key is `teamup`.
- **The ability row is laid out per hero.** The four slot centres in `SLOT_CX`
  are Spider-Man's; Human Torch has five slots at other positions. Everything
  else (hp, bar, ammo, ult) is hero-independent.
- **Max hp is not constant.** It moved between 250 and 300 across both runs as
  the team-up buff ticked down. Anything treating 250 as Spider-Man's health
  will be wrong for stretches of a run.
- **A menu or loading screen returns an empty `Hud`**, not a row of "not ready".
- **`State.on_target` cannot be read from the crosshair.** It is the same small
  white square whether or not a hostile is under it — checked across 1544 frames,
  32 of them with an enemy box over screen centre, with 1507 plain white dots and
  no red ones at all. No reader was built. `agent.brain.aimed_at` already falls
  back to crosshair-in-bbox geometry when the field is None, which is right.

## Decisions

- **Unknown over guess, everywhere.** Each reader has layout checks — a number
  must land at its anchor, be the only thing in its band, and have no
  digit-shaped ink spilling out of it — and returns `None` when they fail. This
  is why the labelled set shows zero wrong reads and why coverage is not 100%.
- **Templates are learned from values a human read, not from labelled glyph
  images.** `python -m perception.hud learn <frame>=hp:300/300;webs:5 ...`
  assigns labels positionally, so a template can only be mislabelled if the
  hand-read value was wrong. Hand-labelling glyph bitmaps was tried first and
  put a scenery blob in the bank as a digit.
- **Ready vs cooling is decided by colour, not brightness.** A red cooling icon
  can be brighter than a thin white ready one, and a buffed icon is gold. The
  test is what share of the icon's ink is red.
- **`python -m perception.hud learn` prints to stdout.** It used to write
  `glyphs.py` into the working directory, which left a stray file at the repo
  root for someone else to puzzle over. Redirect it where you want it.
- **Damage numbers and hit markers are not read.** Damage numbers float away
  from the hit and fade, so no fixed region holds them. A crosshair hit marker
  was built, measured against L1's pad log, and removed: it fired on 29 of 66
  frames where no button was pressed at all — Spider-Man's own web VFX fill
  that region. If L5 needs damage, the honest path is the scoreboard or the
  practice range's own damage readout, not the crosshair.

## Ability events from HUD reads (`perception/events.py`)

Turns a run of per-frame HUD reads into a timestamped event stream, so video with
no input log can be labelled. Three rules carry it:

- **Segment first.** The stream is cut wherever the performance is not
  continuous: the hero being played is not ours, the HUD is gone (menu, BRB,
  loading), or hp hits zero. Channels reset at every boundary, so no event is
  produced across one. The gate is a colour match on the bottom-left hero
  portrait — greyscale gives no separation at all (every hero lands 0.34–0.45),
  colour puts Spider-Man at 0.35–0.52 and other heroes at 0.23–0.30. Without
  this gate the spectating stretch of the sample VOD reads a stranger's 665 hp
  as ours.
- **Events are intervals, not instants.** Each carries `i_from`/`t_from` (last
  frame with the old value) and `i_to`/`t_to` (first with the new). No field
  claims a press time.
- **Unknown is not a value.** A None read emits nothing and does not end the run
  of the value before it. A new value must persist to be believed — 2 frames on
  slow channels, **1 on `ready`**, because a real ability use is a *one-frame*
  red icon flash at 10 fps: 165 of run1's 179 red stretches last a single frame,
  so debouncing that channel at 2 would discard nearly every real use.

Nothing is specialised to the practice range. The range simply never produces
some kinds — its ammo never moves off 5, the bots never damage the player, and a
roaming routine never casts the ult — so no `web_cluster_fired`, `hp_lost`,
`death`, `respawn` or `ult_spent` appear there. The VOD produces all of them
from the same code.

### Things the range taught us that only a real match shows

- **Shield decay is not damage.** The team-up buff lifts max hp to 300 and bleeds
  it back two points at a time, and hp falls with it. Reported as `hp_lost` that
  is a lie to anything learning from these labels, since nothing in the range
  can hurt the player. The test is whether hp is still at max after the drop; if
  it is, the pool shrank, and the event is `shield_decayed`.
- **max hp lags hp.** Its debounce coalesces consecutive shield ticks and it is
  unreadable on ~6% of frames, so the shield test looks for the nearest known
  max within a few frames rather than at one exact frame.

### Hand-verified precision

33 events sampled across every kind (four per kind, so rare kinds are
over-represented) and checked against their own before/after crops in
`docs/evidence/l2/events-verified-*.png`:

- **33/33 are real transitions.** No phantom events: every one shows the stated
  change in the two frames that prove it.
- **24/33 carry a fully correct label.** The other 9 are shield ticks named
  `hp_lost` / `hp_gained` / `max_hp_changed`, because max hp was unreadable on
  those frames. Over the whole run that class is 7.5% of events, not 27% — the
  sampler deliberately over-weights the rare kinds.

### The two demo clips

Both are 1080p60 sampled at 10 fps, read with the `mk` layout.

| | Req (2873352801) | Day (21600-60s) |
|---|---|---|
| segments | 3 | 7 |
| events | 85 | 62 |
| ability used / ready | 16 / 16 | 19 / 19 |
| web cluster fired / reloaded | **15 / 13** | **6 / 5** |
| hp lost / gained | 10 / 14 | 5 / 8 |

The ammo channel reads on both once the M&K layout is used — that was the
mirrored slot, not a reader failure.

**Every one of Day's segment boundaries is real; none is an overlay splitting
continuous play.** Checked frame by frame at each one:

| boundary | what is on screen |
|---|---|
| 12.7 s, 28.3 s, 41.6 s, 59.0 s | the player opens the **scoreboard**, which covers the HUD |
| 45.5 s | **death** — hp reaches 0 |
| 55.5 s | **killcam**: PAST LIVES, DEFEATED BY, and the killer's HUD reading 275 hp |
| 55.9 s | the near-black respawn fade |

So the Day player checks the scoreboard four times in sixty seconds. Those
breaks currently report `no_hud`, which is true but unspecific; the scoreboard
reader in the next piece of work can name them.

## The scoreboard (`perception/scoreboard.py`)

The project's only outcome measure, in two parts.

**`is_scoreboard(frame)`** works on any scoreboard — the range's on a pad HUD and
a live match's on a mouse-and-keyboard stream. It keys on the long horizontal
rule under the team headers, measured as an edge rather than an absolute
brightness, because the overlay dims the scene but so does a dark corner of a
map. Real scoreboards score **0.91–0.97**; ordinary play tops out at **0.79**.

That threshold is the lesson: set from eighteen sampled negatives it looked like
0.70 was safe, and over a whole 60 s clip 0.70 fired on 48 play frames and
shattered the segments. **Thresholds for a per-frame classifier have to be set
against every frame of a clip, not a handful of stills.** Re-measured properly
it also found a scoreboard in the Req clip at 43.6 s that nobody had spotted,
which had been reported as a plain `no_hud` break.

The segmenter now names those breaks `scoreboard` / `scoreboard_closed`.

**`read_scoreboard(frame)`** reads the **range** scoreboard only and returns a
plain dict — `kos`, `deaths`, `assists`, `accuracy`, `damage`, `damage_blocked`,
`healing`, `web_cluster_accuracy`, `spin_kos`, each an int or None, plus `open`.
On `docs/evidence/l4/scoreboard-back-native.jpg` it reads every one of the nine
correctly: 3 / 0 / 1 and 0% 845 0 0 50% 3.

Three things that HUD experience did not carry over:

- **The KO/death/assist digits are gold.** The min-channel mask that reads the
  rest of the HUD sees nothing there at all — gold has almost no blue — so the
  tallies come off the strongest channel instead.
- **The scoreboard sets numbers in a narrower face than the HUD**, 10–13 px per
  glyph at 2560 against the HUD's 14–21, so it needs its own template bank.
  Digits 2, 6, 7 and 9 do not appear on the one frame available; a value
  containing one reads None until L4's extra frames arrive.
- **Below 1920 wide the values are not there to read.** The 720p copy of the
  same capture is still detectable as a scoreboard but reads *assists as 0 when
  it is 1* and *Spin KOs as 0 when it is 3* — upscaling does not recover a 6 px
  glyph, it invents one. `read_scoreboard` refuses under `MIN_WIDTH` and says
  `too_small` rather than guessing.

**Do not key on red for the enemy panel**: its tint follows the Enemy Color
accessibility setting and is currently green. Nothing here reads panel colour.

`tests/test_scoreboard.py` checks the detector on all five known scoreboards
(range native, range 720, four match frames from the clip) and on play frames
from both clips and the range run, and picks up anything L4 drops into
`docs/evidence/l4/scoreboard/` automatically.

## Reading a streamer's HUD (1080p, mouse and keyboard)

Measured against a 60 s 1080p60 Twitch clip of ReqMR on Spider-Man and six
stills a co-lead read by eye. **The regions are fractions of the frame, so
resolution alone changes nothing — 1920x1080 is the same 16:9 as 2560x1440 and
1280x720.** What differs is the HUD itself:

| Part | Holds? |
|---|---|
| hp digits | **Yes**, same region, correct values |
| hp bar | **Yes** — 0.705 fill against a by-eye 175/250 |
| digit templates | **Yes** — the same bank reads a stream's digits |
| ammo count | **No** — the slots are mirrored. On the pad HUD the count is the *left* slot (0.162–0.179) and melee is the right; on the M&K HUD the count is the *right* slot, measured at x 0.260–0.267. Same digits, wrong box. |
| ability row | **No** — different slot centres, and the key glyphs are C / LSHIFT / R / Q instead of Y / LB / RB / X |
| ult | **No** — further right, and Twitch chat sits on top of it |
| charge badges | **No** — they follow the ability row |

So the re-templating needed is smaller than it looks: **no glyph work at all**,
just a second set of slot coordinates for the M&K layout, chosen per source. The
right shape is a small layout table (pad vs M&K) rather than the constants this
module has now.

Two things a stream adds that a capture does not: **chat overlays** the right of
the HUD, so the ult and rightmost abilities go unreadable rather than wrong; and
a **low-health red vignette** floods the screen, which is what makes the +59 s
still (6 hp) unreadable while its bar still reads 0.138.

## Open

- **No template for the digit `1`.** It appears in neither run: hp only ever
  took 250 and 252–300. An hp of 217 reads `None`, not a wrong number. The
  damage taken in `tagrun` will supply it; one `learn` pass then fixes it.
- **`read_tagged` is calibrated on one tagging episode** (trial1 frames 71–86,
  one bot, one distance). In the 1197 `run1` frames I hold, the web-cluster
  bursts hit scenery rather than bots, so they contain no tagged enemies.
  `tagrun` is being recorded for this; until it lands, the five-scale search
  covers other distances on reasoning rather than measurement. The large web-splat VFX scores 0.45–0.53 against
  the tracer template, below the 0.60 match threshold, so it yields `None` or
  `False` — never a false `True`.
- **The ammo box is cropped tight enough that a two-digit count would clip.**
  Fine for Spider-Man's Web-Cluster; another hero may need the box widened.
