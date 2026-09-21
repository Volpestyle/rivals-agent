# L2 — HUD readers

## Event stream format

### Upgrading a loader from format 2 — the exact diff

`agent/demos.py` reads format 2 and so refuses every file on disk. Everything
below is what changed; **nothing was removed or renamed between 2 and 4**, so a
loader that accepts the new values and keys is done.

| # | Change | What a loader must do |
|---|---|---|
| 3 | `slot` is now **the ability the icon says is in that position**, or `null` when the icon could not be identified. The layout position moved to the new **`slot_pos`**. | Read the ability from `slot`, not from position. Treat `null` as unknown — never fall back to `slot_pos`, which names a position, not an ability. |
| 3 | meta gains **`slot_mapping`** (position → ability) and **`slot_mapping_from`**. | Optional. Use it to check a source's key order. |
| 4 | `ended_by` gains **`hard_cut`**, `started_by` gains **`after_cut`** — an abrupt full-frame discontinuity: an edit, or one of the game's own screen transitions. | Accept the two new values. A segment still never spans one. |
| 4 | meta gains **`cuts`**: how many cuts were found, `0` for a continuous capture, `null` for "nobody looked". | Optional. |
| 4 | meta gains **`observed`**: the cooldowns this source's own HUD showed, per ability. | Optional; see **Patch fingerprint**. |
| 4 | meta `slot_mapping` is **`null` when no mapping was attempted**, where format 3 wrote `{}`. `{}` now means the icons *were* read and none identified. | Distinguish the two. Every file written so far carries a real mapping, so nothing on disk changes meaning. |
| 4, added | **A cut inside a gap marks both sides.** When a cut falls in a gap that opened for another reason (a scoreboard tap, a death), the segment before now ends `hard_cut` and the one after starts `after_cut`. Before this, such a gap read `scoreboard` / `scoreboard_closed` and looked bridgeable. | **Never bridge a gap with `hard_cut` or `after_cut` on either side.** A gap is a bridgeable scoreboard tap only if it ends `scoreboard` *and* resumes `scoreboard_closed`. |
| 4, added | meta gains **`cut_times`**: every cut's `t` (first frame on its far side), `null` when cuts were not looked for. | Optional: lets you check any gap for a cut directly. |
| 4, added | meta gains **`recipe`**: source video, `hz`, window `start`/`duration`, `layout` — how the file was made. | Optional. `python -m perception.events regenerate` rebuilds from it. |
| 4, added | segment lines gain **`cooldowns`**: `"normal"` when a countdown inside the segment proved cooldowns are on, else `"unknown"`. **Never `"off"`**: the HUD cannot prove an absence. | Read per segment. See **Cooldown regime per segment** for the guides. |

Event `kind` values, the `t_*`/`i_*` semantics and the three-line-kind layout
are unchanged from 2. **Slot `pull` became `get_over_here` back in format 2.**

Rows marked **4, added** arrived after format 4 was first written and did **not**
bump it: each is an optional field, or — for the cut inside a gap — the existing
`hard_cut` / `after_cut` values used in one more place, which only ever makes a
format-4 reader more conservative. A reader that ignores all of them is still
correct.

**Keeping the directory on one format.** `python -m perception.events check`
lists every file under `data/demos/events/` at another format, without a
recipe, or written by older code (missing a field the writer now always
emits), and exits non-zero if there is one; `python -m perception.events
regenerate [--all]` rebuilds stale files (or every file) from their own recipes.
`tests/test_events.py` fails while the local directory is mixed.

A format change is a cross-lane interface change; this table is the contract.

**The writer is frozen.** `perception/events.py`, `perception/hud.py` and
`perception/scoreboard.py` are fingerprinted into every file's `writer`, and the
loader applies the same staleness rule as `check`. Any edit to any of the three
re-stales every events file and, with them, the annotation and training inputs
built on them. **Changes to those files go through the lead first**, are
batched, and are followed by one `regenerate --all`.

### The format itself

`data/demos/events/<clip-stem>.jsonl` is the agreed location, one file per clip,
written by `perception/events.py`. Three line kinds, told apart by `type`:

```jsonc
{"type": "meta", "format": 4, "source": "reqmr-2873352801-1920", "layout": "mk",
 "frames": 601, "fps": 10.0, "t_origin": "first frame of the media",
 "pts_origin_s": 0.0, "duration_s": 60.0, "segments": 4, "events": 106,
 "slot_mapping": {"teamup": "teamup", "swing": "swing",
                  "get_over_here": "get_over_here", "uppercut": "uppercut"},
 "slot_mapping_from": "ability icon matched by shape, voted over sampled frames"}

{"type": "segment", "start_i": 0, "start_t": 0.0, "end_i": 78, "end_t": 7.8,
 "started_by": "run_start", "ended_by": "death", "cooldowns": "normal"}

{"kind": "ability_cast", "i_from": 299, "t_from": 29.9, "i_to": 300, "t_to": 30.0,
 "slot": "get_over_here", "slot_pos": "get_over_here", "amount": 8,
 "before": "off", "after": 8, "segment": 2}
```

**Events carry no `type` key**, so readers already consuming them keep working.
Order is meta, then segments in time order, then events in time order.

- **All `t_*` are seconds from the first decoded video frame**, not from the
  times a clip was requested at. Three clocks are recorded apart, because a
  container can start before its video stream — `daymr-2879354299-21660-900s`
  has audio from 1.589 s and video from 1.616 s:
  - `pts_origin_s`: the first decoded frame's PTS **on the video stream's own
    clock** (decoded with `-copyts`, so never rebased);
  - `stream_start_s`: the video stream's start time, from ffprobe;
  - `container_start_s`: the container's start time, which is what players and
    ffmpeg's `-ss` count from.

  So **stream PTS = `t + pts_origin_s`**, and **seek / player time = `t +
  pts_origin_s − container_start_s`**. Before this, a 1.616 s origin was
  presented as the way back to the original timeline; for seeking it was
  1.589 s out, because a decode without `-copyts` rebases by the container's
  start and puts that section's first frame at 0.027 s. All `i_*` are frame indices *at the sampling fps in the
  meta line* — not the source video's native frame numbers. The clips here were
  sampled at **10 fps** from 60 fps sources.
- **An event is an interval, never an instant**: `i_from`/`t_from` is the last
  frame showing the old value, `i_to`/`t_to` the first showing the new one. The
  press happened somewhere between. At 10 fps that is about 100 ms wide.
- `segment` on an event is the index of the segment line it belongs to. **No
  event ever spans a segment boundary**; channels reset at each one.
- `ended_by` is one of `run_end`, `death`, `killcam`, `spectating`,
  `scoreboard`, `not_our_hero`, `no_hud`, `hard_cut`. `started_by` is
  `run_start`, `respawn`, `killcam_over`, `spectating_over`,
  `scoreboard_closed`, `hero_returned`, `hud_returned`, `after_cut`.
- **`cuts` in the meta line counts the source's abrupt full-frame changes** — edits and
  the game's own screen transitions — and is `0` when none were found. `null` means nobody looked, which is not the same thing.
- **`observed` in the meta line is what this source's own HUD said each
  ability's cooldown is** — a patch fingerprint for footage dated only by an
  upload. See **Patch fingerprint** below for what each number means and which
  two of them do not mean what they look like.
- **`format` is 4.** Version 1 had `ability_used` / `ability_ready` and called a
  slot `pull`. Version 2 split those into `ability_cast` and
  `slot_unavailable` / `slot_available`. Version 3 makes `slot` the ability read
  off the icon and adds `slot_pos`. Version 4 adds the editorial-cut break and
  the `cuts` and `observed` meta keys, and later gained the optional
  `cut_times`, `recipe` and per-segment `cooldowns` without a bump. The upgrade table at the top of this
  section is the contract; **Format 3** and **Format 2** below give the
  reasoning behind each.
- Event `kind` is one of: **`ability_cast`** (with `slot`; `amount` is the
  cooldown it started at), **`slot_unavailable`** / **`slot_available`** (with
  `slot`), `charges_spent`, `charges_regained` (with `slot` and `amount`),
  `web_cluster_fired`, `web_cluster_reloaded`, `hp_lost`, `hp_gained`,
  `shield_decayed`, `shield_gained`, `max_hp_changed`, `ult_ready`, `ult_spent`,
  `ko_feed`, `death`, `respawn`.
- Slots are `teamup`, `swing`, **`get_over_here`** (was `pull`), `uppercut`,
  `ult`.
- **`ability_cast` is the only kind that claims an ability fired.**
  `slot_unavailable` means the icon dimmed, which also happens on a wall climb
  or mid-swing, and is not a cast.
- **Verified on match footage, per type.** 30 events on the Req clip were checked
  frame by frame against their own before/after crops. What passed, and what did
  not, is in **Hand-check, Req clip** below. Types not marked verified there are
  proposals, not labels.
- **`hp_lost` is damage only when hp is below max.** Where max hp could not be
  read, a shield tick still surfaces under this name: 68 of run1's 903 events
  (7.5%) are shield movement wearing an `hp_lost` / `hp_gained` /
  `max_hp_changed` label, every one of them at full health. The shield events
  proper are the ones where both numbers were read and moved together. In the
  practice range *nothing damages the player*, so any `hp_lost` there is a
  shield tick by construction.

### Per-frame observability contract (for B0)

For persisting the frozen readers' per-frame observations of the two train
media (`daymr-2879354299-21660-900s`, `reqmr-2873352801-1980-900s`, both
**layout `mk`**) under `data/experiments/b0/`. Writer `1336262e179c`. "Observed"
below means *an event on that channel, had it happened, would have been
emitted*. Everything else is **unknown**, never a negative.

**(1) Raw fields that make a channel observable on a frame.** `hud` is
`perception.hud.read(frame, LAYOUTS["mk"])`. Slot fields are keyed by layout
**position**; the ability in a position comes only from the file's
`meta.slot_mapping`.

| channel | events it emits | observed on this frame iff |
|---|---|---|
| web ammo | `web_cluster_fired` / `_reloaded` | `hud.webs` is an int |
| get_over_here, teamup (one charge, a countdown after each use) | `ability_cast` | the position is in `slot_mapping` **and** either `hud.cooldowns[pos]` is an int (on cooldown: no use is possible), or `hud.abilities[pos][0] is True` and `hud.cooldowns[pos] is None` (lit, no number: ready) |
| swing, uppercut (charges) | `ability_cast` (first use from full), `charges_spent` (a use while recharging) | mapped **and** either lit with no number (full charges; the badge is not drawn at full, so `charges` is `None` here and that is fine), or `cooldowns[pos]` is an int **and** `abilities[pos][1]` is an int (recharging, badge readable) |
| ult | `ult_spent` / `ult_ready` | `hud.ult_ready is not None` (`False` = charging: no spend possible) |

**(2) Ambiguous raw states.**

- **`ready is False` with `cooldown is None`: not observed.** A dimmed icon with no
  readable number is either a lockout (wall-climb, mid-swing — no use) or a
  countdown the reader failed to read — a use that went unseen. It cannot be
  told apart. The extractor itself turns `cooldown None` into the value `"off"`
  (and only a one-frame `"off"` between two numbers into unknown), so **"off" in
  the extractor is not proof that the slot was visible**; use `ready` as above.
- **A digit read failing**: `webs` / `hp` / `cooldowns[pos]` / `charges` come back
  `None`. `None` is unknown everywhere except the cooldown case just described.
  Countdowns of three or more digits are discarded as `None` (chat).
- **Slot spill** (`abilities[pos][0] is None` because something runs through the
  slot and its gaps; on `mk` the test is live, threshold 0.15): not observed.
  `ready is None` from an in-between red fraction: not observed.
- **Icon identity.** Mapping is voted once per source, not per frame. A position
  absent from `slot_mapping` is unobservable for every ability, on every frame.
  No per-frame identity check exists in the extractor; if B0 adds one
  (`hud.identify_slot`), a mismatch should make that slot unknown. A small
  overlay covering the icon but not the slot's gaps (DayMR's animated overlays)
  is **not** caught by the spill test — not provable that such frames are clean.
- **`charges is None`**: fine at full charges (badge not drawn); not observed for
  a charged slot whose countdown is running.
- **HUD absent** (`read` returns an empty `Hud()`: no hp digits and no bar), **not
  our hero, scoreboard, killcam, spectating, a cut**: the frame is not valid at
  all — see (3). Do not re-derive these per frame; the segments already encode
  them with the voting below.
- **Layout.** Always `meta.layout` (`mk` for both media). `pad` reads different
  boxes (other slot centres, ammo in the other slot, spill test effectively off at 0.95) and every
  read would be wrong. Never inferred from a frame.

**(3) Frame validity, before any channel counts.**

- The frame's index `i` lies inside a segment line of the regenerated events
  file. Segments already require: HUD present (voted over `HUD_HOLD` = 6
  frames), not a known other hero (`PORTRAIT_HOLD` = 3, now with the negative
  portraits), no banner or scoreboard (`BANNER_HOLD` = 3), no hp 0, no cut.
- **What the extractor needs around an event** (10 Hz, all within one segment,
  because every channel resets at a segment boundary and its first reading in a
  segment is never an event):
  - **before:** at least 1 frame with a valid read of the channel, earlier in the
    same segment;
  - **after:** the new value on `hold` consecutive valid reads — `webs` 2,
    `charges` 2, `ready` 1, `cooldown` 1 (plus 1 more frame, because a lone
    `"off"` needs a neighbour on each side to be judged), `ult_ready` 1.
- **Edge margin: 6 frames (0.6 s) from each end of the segment.** That is a
  conservative choice, not a derived requirement: edges fall exactly on vote-run
  boundaries, but the frames beside a transition (a fade, a scoreboard opening)
  are the likeliest to be misread, and 6 is the longest vote window.

**(4) Rule for a fully observed negative.** For channel `c` and horizon `(t, t+1 s]`
= frames `i0+1 … i0+10`:

1. frames `i0 − 1 … i0 + 10 + hold(c)` (+1 for cooldown) all lie inside **one**
   segment, at least 6 frames from both of its ends;
2. **every** one of those frames is observed for `c` under (1)–(2) — one unknown
   frame makes the horizon unknown;
3. for slot channels: the position is in `slot_mapping`, and the **source's
   cooldown regime is normal by provenance** (a matchmade game runs normal
   cooldowns; the practice range and custom games can turn them off). The segment field `cooldowns` does *not*
   establish this: it says `"normal"` only where a cast happened, so it can
   never support a negative. With cooldowns off, casts show no countdown and
   every "negative" would be silent and false — **not provable** for the guides;
4. the raw value of `c` is constant across those frames (a change that the
   debounce did not confirm is unknown, not a negative);
5. the events file has no event of `c` with `i_to` in `(i0, i0 + 10 + hold(c)]`
   (for a slot: neither `ability_cast` nor `charges_spent` for that ability).

All five → **observed negative**. An event in (5) → **positive**, whatever the
coverage. Anything else → **unknown**. There is no fourth outcome.

**(5) How to get the raw reads, and what is on disk.**

```python
import json
from pathlib import Path
from perception.events import extract_frames, scene_cuts, read_run
from perception.hud import LAYOUTS

meta = json.loads(open(events_path).readline())
r = meta["recipe"]                                   # video, hz, start, duration, layout
run_dir = Path("data/experiments/b0/frames/<stem>")  # VOD frames stay under data/
origin = extract_frames(r["video"], run_dir, r["hz"], r["start"], r["duration"])
(run_dir / "cuts.json").write_text(json.dumps(
    scene_cuts(r["video"], pts_origin=origin, start=r["start"], duration=r["duration"])))
reads = read_run(run_dir, layout=LAYOUTS[r["layout"]])
# reads[k] = (i, t, Hud, playing, aside, killfeed, cut) -- exactly what the extractor saw
```

`i` and `t` then match the events file (check: `len(reads) == meta["frames"]`,
`origin == meta["pts_origin_s"]`). **No per-frame reads are retained on disk.**
`from_video` decodes into a temporary directory under `data/.work/` and
deletes it; the events file keeps only meta, segments and events. A rerun is
needed: about 10 minutes per 15-minute section on this machine, niced.

#### Addendum: is a lockout distinguishable in the raw reads?

**Not distinguishable — and on these MK clips there is no lockout state to
distinguish.** Measured read-only on B0's per-frame sidecars
(`data/experiments/b0/visibility/*.json`, writer `1336262e179c`), frames inside
segments, per slot: its raw state (a) inside its **own** cooldown (from its own
`ability_cast`, for the countdown it started at), (b) in the second after
**another** slot's cast while not on its own cooldown — where a lockout would
be — and (c) neither. "lit/dim/unread" is `ready` True/False/None; "num" is an
int in `cooldowns[pos]`.

| slot | own cooldown: a number read | after another cast: dim + no number | neither: dim + no number | after another cast: unread | neither: unread |
|---|---|---|---|---|---|
| ReqMR teamup / swing / GOH / uppercut | 97 / 82 / 93 / 35% | 2 / 3 / 0 / 1% | 1 / 2 / 1 / 1% | 10 / 20 / 66 / 65% | 5 / 16 / 54 / 57% |
| DayMR teamup / swing / GOH / uppercut | 90 / 77 / 92 / 89% | 0 / 2 / 1 / 1% | 0 / 4 / 3 / 7% | 8 / 24 / 38 / 22% | 7 / 37 / 40 / 34% |

- **(a) against a lockout: the raw field that differs is `cooldowns[pos]`.** Own
  cooldown shows a number on 77–97% of its frames (ReqMR uppercut 35%, where the
  slot is unread on most frames). `ready` does **not** separate them on MK: the
  readiness reader calls a cooling icon "lit" on 31–91% of own-cooldown frames.
- **The only raw state a lockout could produce — dim with no number — is not
  enriched after another slot's cast** (0–3%, against 0–7% at baseline). During
  another ability's animation the other slots read like any other frame: mostly
  lit with no number, which the contract counts as observed-ready. A per-frame
  lockout label cannot be read from these fields.
- **(b) unreadable is its own raw state** (`ready is None`). Its rate after
  another cast differs from baseline by up to 13 points in either direction
  (ReqMR Get Over Here 66% against 54%; DayMR swing 24% against 37%), with no
  consistent sign, so it is not a lockout marker either. Per creator it is driven by the slot, not the cast: ReqMR's
  Get Over Here and uppercut are unread on 54–57% of ordinary frames, DayMR's
  swing on 37%.
- **PAD: not measured** on these clips (both are MK). The range audit saw PAD
  icons dim without a countdown during wall climbs and swings, which is the
  same raw signature as an unread countdown; not distinguishable per frame there
  either, on that evidence.

**What `docs/spiderman-kit.md` supports:** some abilities are cast *during or
at the end of* another's animation — Web Cluster cancels the swing animation,
and the fast-cancel chain fires RB, RT, LT and X in quick succession — with the
cancel windows marked **U** (unverified). It says nothing about a greyed slot:
whether a greyed slot accepts input is **not established** by any source in it.

**For B0, a pointer rather than a finding:** under rule (4) a positive needs no
coverage at all, and 14–81% of 1 s horizons per slot are fully observed on
these clips (teamup 69–81%, Get Over Here 42–47%, swing 14–39%, uppercut
16–22%). Requiring *every* slot to be observed around a cast is stricter than
the contract and, with these per-slot rates, would leave almost nothing
eligible. No label changes on this inference.

### Reproducing any of this

`uv run --group perception python -m perception.events ...` — the shared venv's
two-opencv clash is fixed.

```sh
# One path makes every demonstration file, and records how in its meta line.
python -m perception.events video <clip>.mp4 data/demos/events/<stem>.jsonl            # 10 Hz
python -m perception.events video <guide>.mp4 <out>.jsonl --hz 30 --start 1200 --duration 230
python -m perception.events check                  # stale: other format, no recipe, other writer
python -m perception.events regenerate [--all]     # rebuild from each file's own recipe
```

Frames are taken as every Nth *decoded* frame on an exact grid (`select=not(mod(n,N))`),
never `-vf fps=N`, which resamples and lands a source frame off. `writer` in the meta
line fingerprints `perception/events.py`, `hud.py` and `scoreboard.py`; a file with any
other value was made by other code, and `check` says so.

`from_video` measures all three clocks itself; nothing is taken from the times
a clip was requested at.

### Hand-check, Req clip (30 events, frame by frame)

Sampled across every type, each checked against the two frames that prove it.

| type | verdict | n |
|---|---|---|
| `hp_lost`, `hp_gained` | **verified** | 3/3 |
| `web_cluster_fired`, `web_cluster_reloaded` | **verified** | 5/5 |
| `charges_spent`, `charges_regained` | **verified** | 5/5 |
| `ability_cast` | **verified after a fix** | 5/5 (2 phantoms removed) |
| `slot_unavailable` / `slot_available` | **verified after a fix** | 6/10 before; the 2 wrong ones now read unknown |

Ammo, hp and charge events were right every time — 13/13.

**`ability_cast` had phantoms, now fixed.** Three of seven sampled casts were not
casts: the countdown blinked "off" for a single frame and came back, and the
return read as a fresh cast. A countdown dropout is now treated as unknown
rather than as the ability being cast again, which removed two of them. The
third turned out to be a real cast that I had misjudged — the slot shows its
icon at i183 and a `4` fades in by i187 — so the check corrected me as well as
the code.

**`slot_unavailable` / `slot_available` committed to verdicts on slots they
could not see.** Two of the ten sampled were on frames where **Twitch chat runs
through the ability row**, and the reader answered True/False anyway — the one
thing every reader here must not do. It now measures the ink in the narrow gaps
either side of the slot: an icon stays inside its box, a line of chat does not.
Covered slots read unknown, and the Req stream's slot events fell from 20 to 12,
all of the loss being frames under chat. Two of the ten sampled remain
dim-versus-red judgements too marginal to settle by eye, so this type carries
more unknowns than the others by design.

**The threshold for that test belongs to the layout, not the reader.** The pad
HUD draws its own separators in those gaps and measures up to 0.91 ink on 580
clean slot readings, while the M&K row leaves them empty: 0.09 clean, 0.22 under
chat. A single global number would either fire constantly on our own captures or
never fire on a stream, so `Layout.slot_spill` carries it — 0.15 for M&K, and a
dormant 0.95 for the pad, where nothing is ever drawn over the HUD.

**`ability_cast` was unaffected** — a countdown has to be centred in its slot,
which chat text is not.

### Format 3: the ability is read, not assumed

`slot` is now the ability whose icon is in that position, or `null` when the
icon could not be identified; `slot_pos` keeps the layout position it fired in.
The meta line carries `slot_mapping` and `slot_mapping_from`.

This exists because **a slot position names no ability**: the ability-to-key
binding is a player setting, and both guide sources have Web-Swing and Get Over
Here the other way round from the clip the layout was measured on. See **How the
slot-to-ability mapping is decided**.

### Format 2, and why

An audit by two annotators against native frames found version 1 was emitting
casts that never happened and missing the ones that did. Reproduced on the frames
and fixed:

1. **A dim or red icon is a lockout, not a cast.** The swing icon goes red during
   a wall climb with the charge count unchanged, and every `ability_used` in the
   old file lasted 0.1-1.4 s. Those are now `slot_unavailable` /
   `slot_available`.
2. **What proves a cast is the countdown.** A real cast replaces the slot's icon
   with a number — clearly visible at i300, where Get Over Here becomes `8`. The
   old reader never looked for it, so *neither* visible Get Over Here cast
   (i299-300 and i401-402) produced an event. `ability_cast` now fires on a
   cooldown number appearing or a charge going down, and carries the cooldown it
   started at. The cooldown digits are 42-43 px tall against the hp row's 23-33
   and needed their own templates: an 8 read as 3 until they were learned, from
   two countdowns that label themselves as they tick.
3. **hp emits raw steps, never a net.** 250 -> 195 -> 220 at 10 Hz is three
   things that happened; it was being reported as a single net loss of 30. With
   raw steps the losses across 45.1-50.0 s now total **210 hp, matching the
   annotator's by-eye count exactly**, where the old stream reported 55 and
   missed two hits. **A net figure is never reported as damage.**
4. **The hp bar's red damage stripe is the corroborating witness.** A one-frame
   drop that returns to the same number looks exactly like a misread, so it is
   dropped — unless the jump is small enough to be plausible or the bar is
   showing a fresh red stripe. Filtering on the shape alone deleted a real 25 hp
   hit, and worse, deleted the heal between two hits and so erased the second
   hit too.
5. **Twitch chat scrolls through the ability row** and its letters are the right
   size to read as cooldown digits: eight "uppercut casts" in 2.6 seconds on a
   7 second cooldown. A countdown is centred in its slot; off-centre text is not
   ours.

Two findings did not reproduce as bugs:

- **The 43.7 s segment edge.** On an exact 10 Hz grid the scoreboard is up
  i433-i437 and gone by i438, and the segment starts at 43.8 — after the overlay,
  as it should. The 43.7 s reading came from `-vf fps=10`, which lands one source
  frame off. **Use `select='not(mod(n,6))'` on a 60 fps source.**
- **The team-up slot is tracked**, and its use at 40.9 s appears as
  `ability_cast:teamup` with a 15 s cooldown.

This format is stable within a version. Anything added will be a new key or a new
`type`; anything that changes the meaning of what is above bumps `format`.

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
`tests/test_hud*.py`, `docs/evidence/l2/`, plus `perception/events.py`,
`perception/scoreboard.py`, `perception/replay_states.py`,
`perception/evalread.py`, `perception/camera_motion.py` and their tests. Tracked as VUH-1294; the offline
integration lane that consumes these readers is `docs/lanes/l6-integration.md`
(VUH-1298).

**Demonstration corpus.** Two sets, both segmented and evented at an exact 10 Hz
into `data/demos/events/`:

- **Four retained 15-minute Twitch sections** (`sections/`), continuous capture,
  two of them reserved as evaluation. See **Retained sections**.
- **Six ReqMR YouTube uploads** (`youtube/`), edited, 104 raw minutes across two
  balance patches. Cuts are detected per file so no segment spans an edit; see
  **Edited uploads**. They do not reuse the Twitch footage — see the overlap
  section — and each file's own cooldowns date it, see **Patch fingerprint**.

Everything derived from a VOD lives in gitignored `data/` and is never
committed; `docs/evidence/` holds no VOD frame.

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

**Widened on L4's eight native boards** (KOs 6–13, Damage 1375–2680) against
their `truth.json`: **81/81 values correct, 0 wrong, 0 unread**, across all nine
boards and all nine fields. Leave-one-out — learn the digits from every other
board, read the held-out one — is also **81/81**, so that is not a training
number. Digits 2, 6, 7, 9 and the `%` slash are now in the bank; the widening
path is `scoreboard.learn()`, which labels glyphs positionally against values a
human read.

Three defects the eight boards exposed, all of which produced **wrong numbers**
rather than unknowns:

- **Missing digits do not fail safe when the bank is small.** With only six
  digits learned, a 6 matched the nearest thing to it and read as 8, and a 9 read
  as 0. The margin rule cannot help when the right answer is absent entirely.
  Widening is the fix; the lesson is that a partial bank is more dangerous than
  an empty one.
- **The thousands separator split the number.** "1,375" — the comma is a 5x8
  mark, far below glyph size, so it drops out and leaves a gap wide enough to
  start a new group. Damage read `1`. Stats are now read as *every digit over a
  label* rather than grouped first.
- **The percent slash.** Stripping any unnamed trailing glyph turned "12" into
  "1" whenever the 2 had no template. Only a glyph positively classified `%` is
  dropped now.

**The kill feed** is the fastest KO signal — it appears as the KO lands, long
before anyone opens a scoreboard. `is_killfeed(frame)` keys on two things,
because the banner is semi-transparent and its brightness follows the background
(V~160 over a dark ceiling, ~230 over sky): its saturation collapses (~80 to
~20) **and** it is a crisp rectangle. Saturation alone fires on pale sky at 0.61.
Measured on L4's two kill-feed frames and 115 ordinary ones: the feed scores
0.88–0.90 and 0.94–0.99, and no ordinary frame clears 0.5 on both. A line
appearing emits a `ko_feed` event. In the range every line is ours; in a match
the feed shows everyone's kills and attributing one would mean reading the
killer's name, which is not done.

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

## Guide timings

Unblocked by reading the icon in each slot (below), then run over the two 16:9
practice-range guide windows at an exact 30 Hz. **Neither yields per-ability
combo timings, for a reason that is worth more than the timings would have
been.**

| technique | source | ability order observed | intervals | confidence | what the HUD could not show |
|---|---|---|---|---|---|
| FFAme Stack | F 20:00–23:50 (`ffame-stack.jsonl`) | 37 lockout flashes over Web-Swing, Get Over Here and one uppercut | see below | **low** — lockouts, not casts | no cooldown numbers at all; no charge changes |
| Matchu pull lesson | D 01:22–02:49 (`day-pull-lesson.jsonl`) | 9 lockout flashes | too sparse to sequence | **low** | same, plus a facecam that breaks segmentation |
| Sekkombo | S 00:26–01:21 | not run | — | — | vertical edit, needs its own layout |
| *(reference)* Req match clip | 60 s, `reqmr-…-1920.jsonl` | **14 casts, cooldown-proved** | table below | **high** | — |

**Both guide sources run with cooldowns off.** Across 6900 FFAme frames and 2610
Day frames there is not one countdown anywhere in the ability row — the signal
that proves a cast. That is what a teaching demo looks like: the presenter wants
to repeat a combo without waiting. It also means the HUD cannot prove a cast in
either video, so no interval from them can be called a cast interval.

**Lockouts are not a substitute, and the guide footage shows why.** In the FFAme
window Web-Swing and Get Over Here go unavailable *on the same frame* eleven
times (t1217.53, t1265.67, t1339.57, t1357.93, t1381.17, t1399.33 …). Two
abilities are not being cast on one frame; that is a global "cannot act" state —
mid-swing, mid-animation — dimming every slot at once. A per-slot lockout cannot
be attributed to that slot's ability.

**Where the narration and the HUD can be compared, they agree but do not
resolve.** The arsenal doc has the Stack as *"Get Over Here! → uppercut in very
rapid succession, Get Over Here! first"* (F 20:07–21:30). The one place the HUD
shows both slots flashing close together is t1305.13–1305.67 (Get Over Here) and
t1305.17–1305.20 (uppercut) — **within half a second, consistent with "very
rapid succession"**, but the two event intervals overlap, so at 30 Hz the HUD
cannot confirm which came first. The narration's ordering claim is neither
supported nor contradicted.

### Inter-cast intervals that are actually proved

From the Req match clip, where cooldowns are on and every cast is proved by a
countdown appearing. Each bound is the widest and narrowest gap the two event
intervals allow:

| from → to | interval |
|---|---|
| Get Over Here → Web-Swing | 0.80–1.00 s |
| Get Over Here → team-up | 0.70–0.90 s |
| Web-Swing → Get Over Here | 1.80–2.00 s |
| Web-Swing → Web-Swing | 2.60–2.80 s, 4.60–4.80 s |
| uppercut → Get Over Here | 1.90–2.10 s |
| Get Over Here → Get Over Here | 2.30–2.50 s |
| Get Over Here → uppercut | 2.80–3.00 s |
| uppercut → uppercut | 4.20–4.40 s |

**Match footage is the source for combo timing, not range demos.** The thing
that makes a range demo easy to film — no cooldowns — removes the only evidence
the HUD has that an ability was used. The four retained match sections bear this
out: they give hundreds of cooldown-proved casts each, where 230 seconds of
clean range teaching gave none.

**The Sekkombo Short was not run and is not worth its own layout yet.** It is a
1080x1920 vertical edit with the HUD rescaled and moved (ammo at x 0.091–0.115
against 0.246–0.270 on a 16:9 M&K HUD). Its HUD is stable across the window, so
a layout is measurable, but it is a *range demo* — so by the finding above it
would produce lockouts and no casts, at the cost of a bespoke layout used by one
video. Worth doing only if someone wants the lockout sequence specifically.

## How the slot-to-ability mapping is decided

The three practice-range guide windows were extracted at an exact 30 Hz
(`select='not(mod(n,2))'` on a 60 fps source) and the Day window run through the
extractor. It produced segments and slot events but **zero casts**, and the
reason is worth more than the timings would have been.

**A slot position is not an ability.** Reading the same four slot centres on
three sources:

| slot centre | Req | Day | FFAme |
|---|---|---|---|
| 0.7516 | team-up | team-up | team-up |
| 0.7950 | **Web-Swing** | **Get Over Here** | **Get Over Here** |
| 0.8348 | **Get Over Here** | **Web-Swing** | **Web-Swing** |
| 0.8723 | uppercut | uppercut | uppercut |

Swing and Get Over Here are **swapped** on both guide sources relative to the
clip the layout was measured on, because the ability-to-key binding is a player
setting: Req's row reads C / LSHIFT / R / F, Day's reads C / mouse / LSHIFT / F.
Any interval reported from these windows now would have attributed half the
casts to the wrong ability on two of the three sources.

The good news is that only the *naming* is wrong. The slot **positions** are
stable: detecting the underline beneath each icon finds slots at 0.7948, 0.8346
and 0.8742 on all three sources, within a pixel of the layout's values. So the
geometry transfers and the mapping does not.

**So the icon decides, not the position.** `identify_slot` matches the four
Spider-Man icons — the swinging figure, the arrow, the fist, the star — as ink
*shapes*, because the same icon is drawn white normally and gold while a team-up
buff is up. `slot_mapping` votes over sampled frames, because a slot spends much
of its time showing a countdown, an overlay or nothing. The result and the method
go in every events file's meta line as `slot_mapping` / `slot_mapping_from`.

A position whose icon never identifies is **left out of the mapping**, and its
events carry `slot: null` with `slot_pos` still set — never a guessed name. That
happens on the FFAme window, whose team-up slot is empty throughout.

Checked against the three sources: Req maps straight through, Day and FFAme both
have Web-Swing and Get Over Here the other way round, and Req's four known casts
(29.9, 40.1, 40.9, 48.1 s) keep their names.

## Retained sections: how much is actually own-Spider-Man play

Four 15-minute 1080p60 expert sections, sampled at an exact 10 Hz and segmented.
The number nobody had: **how much of an expert's recorded session is our hero,
in our control, with nothing on top of the HUD.**

Per section, `data/demos/events/sections/<id>.jsonl`, same format as the clips
(format 3) with `pts_origin_s` in the meta line. **Times are keyed to the first
decoded frame**, and `pts_origin_s` records what the decoder reported as the
source's first PTS — 1.616 s for `daymr-2879354299-21660-900s`, 0 for the other
three. The requested cut times are not used for anything.

| section | PTS origin | own-Spider-Man play | share | segments | median / longest | events |
|---|---|---|---|---|---|---|
| `reqmr-2871472478-5400-900s` | 0 s | **11.57 min** of 15 | 77% | 55 | 6.5 / 65.8 s | 1669 |
| `reqmr-2873352801-1980-900s` | 0 s | **9.11 min** of 15 | 61% | 31 | 12.1 / 56.4 s | 910 |
| `daymr-2879354299-21660-900s` | 1.616 s | **8.22 min** of 15 | 55% | 43 | 4.9 / 68.7 s | 978 |
| `daymr-2877719252-1800-900s` | 0 s | **9.59 min** of 15 | 64% | 69 | 3.9 / 84.1 s | 922 |
| **total** | | **38.5 min** of 60 | **64%** | 198 | | 4479 |

Writer `1336262e179c`. **About two thirds of a retained expert section is usable,
and a third is not.** Budget on 0.64, not on wall-clock minutes. The DayMR
section's minute of Doctor Strange (see **Another hero passing as ours**) is the
one real loss against earlier counts.

Events per section, the types a policy would learn from:

| section | get_over_here | swing | uppercut | team-up | hp_lost | hp_gained | web fired | ko_feed |
|---|---|---|---|---|---|---|---|---|
| `reqmr-2871472478-5400-900s` | 55 | 47 | 53 | 30 | 384 | 326 | 183 | 6 |
| `reqmr-2873352801-1980-900s` | 37 | 27 | 22 | 21 | 132 | 236 | 115 | 6 |
| `daymr-2879354299-21660-900s` | 43 | 22 | 53 | 21 | 188 | 131 | 96 | 4 |
| `daymr-2877719252-1800-900s` | 31 | 16 | 43 | 28 | 142 | 147 | 102 | 7 |

Slot mapping came out per source, by icon: Req maps straight through, both Day
sections have Web-Swing and Get Over Here the other way round. Each section's
file carries its own `slot_mapping`, so the names are comparable across the table
above even though the key order was not.

### The play is not in long runs

The median segment is **3.9–12.1 s**, against longest runs of 56–84 s. That is
not the segmenter being twitchy — it is the players. **ReqMR taps the scoreboard
on and off inside fights**: at 60.1 s of `reqmr-2871472478` the board is up
(his row highlighted, 837 damage), at 60.5 s he is mid-swing at 245/250, at
60.8 s the board is up again. Board frames score 0.97 and play frames 0.06, so
these are decisive detections a third of a second apart, not threshold flicker.

Two numbers a consumer will want:

| section | segments >= 5 s | play inside them | after bridging scoreboard taps < 1 s |
|---|---|---|---|
| `reqmr-2871472478-5400-900s` | 34 | 11.1 min | 40 runs, median 14.5 s, longest 66 s |
| `reqmr-2873352801-1980-900s` | 18 | 8.9 min | 19 runs, median 19.9 s, longest 145 s |
| `daymr-2879354299-21660-900s` | 21 | 7.7 min | 29 runs, median 7.4 s, longest 82 s |
| `daymr-2877719252-1800-900s` | 28 | 8.4 min | 36 runs, median 7.1 s, longest 84 s |

Bridged here only where the format allows it: a gap that ends `scoreboard` and
resumes `scoreboard_closed`, under a second, so no gap with a cut in it is ever
joined. That cuts the segment count by a quarter to a half and roughly doubles
the median run, at almost no cost in play time. **It is a loader policy, not a change to this format**
— the files keep every break, because a bridged run has up to a second of
scoreboard frames inside it, which must be masked rather than learned from.

What gets removed is as interesting as what is left. In
`reqmr-2873352801-1980-900s`, **184.7 s — a fifth of the section — is after the
last play segment**: the DEFEAT and rank screens, the next match's intro, and
hero select, where the player picks **Jeff the Land Shark**. Spot-checked by eye
at 720, 760, 820 and 880 s. A pipeline that trained on "15 minutes of expert
Spider-Man" would have been training partly on a shark.

## Cooldown regime per segment

Every segment line carries `cooldowns`, and it can only ever be one of two
values. **`"normal"` is proved** by a countdown appearing in the ability row
inside that segment. **`"unknown"` is everything else**, and it is never
promoted to `"off"`: the HUD cannot prove an absence. A segment without a
countdown may have cooldowns off, or may simply contain no cast.

**The guides.** Both guide windows (`guides/ffame-stack.jsonl`,
`guides/day-pull-lesson.jsonl`) contain no countdown anywhere across 9510
frames, so every one of their segments reads `"unknown"`. That they are
cooldown-free in the practice-range stretches comes from the videos'
narration and provenance, not from pixels, so it belongs in the loader's source
metadata, stated as provenance. **Per segment, from the HUD, it cannot be
determined**, and this file does not pretend otherwise. Every retained section
and upload segment with a cast reads `"normal"`.

## Another hero passing as ours

**Found by the box annotator:** in `sections/daymr-2879354299-21660-900s`,
source 820–882 s were kept as own-Spider-Man play while DayMR was on **Doctor
Strange** (650 hp). **Cause: the portrait gate's tolerance.** It was one Spider-Man
template scored against a threshold, with the band set from a handful of other
heroes (0.225–0.304). Strange scores **0.32–0.40** against that template —
inside Spider-Man's own band — so 537 of 621 frames read "playing Spider-Man".
No hero swap mid-match was involved, and no hp check existed.

**Fix: other heroes are now negatives**, on an absolute bar (`PORTRAIT_OTHER`,
0.75). "Nearer class wins" would have been wrong: real Spider-Man frames score
0.46–0.48 against the Strange template, *higher* than against his own, because
the colour match is weak. Over 89 kept frames from every source, the highest
score against Strange was 0.69, a frame an editor had blurred whole; Strange
himself scores 0.78–1.00. The bar sits in that gap and the three-frame hold
absorbs a stray blurred frame. One Strange frame, mid-animation, reads unknown
(0.64), which is carried across rather than trusted. Test:
`test_doctor_strange_is_not_spider_man`, local VOD only.

**hp cannot back this up**, which I checked before trying: Spider-Man in his
ultimate with a shield reads **650/650** (`V6iaq9dP8FQ`, 884 s) — exactly
Strange's base maximum. Any hp veto near that value deletes real play.

**The gap is narrow and the fix is per hero.** A hero whose portrait scores like
Spider-Man and who is not yet a negative still passes. The durable fix is a
portrait classifier trained on crops of the whole roster, or a second vote from
the ability icons (`identify_slot` recognises Spider-Man's four icons, which no
other hero draws). Until then this is tech debt, stated as such.

**Found alongside:** `ftnk5SVycXY` at 1404 s is a SPECTATING screen the banner
reader missed (the older patch draws it as a large yellow "10s SPECTATING"),
and a DayMR scoreboard drawn translucent under his facecam was kept inside a
play segment in `daymr-2877719252-1800-900s`. Both are open.

**Animated overlays.** DayMR's stream overlays appear, move and disappear.
- *HUD reads:* the slot readers go unknown when something runs straight through
  a slot and its gaps (`_slot_occluded`, built for chat); digit readers reject
  ink that does not match a glyph closely enough. A small overlay covering a
  slot but not its gaps is **not** caught by the occlusion test — his Spider-Man
  bobblehead sits over the lower-right HUD — and that has not been measured.
- *Camera motion:* the learned overlay mask only covers overlays that never
  move; an animated one is left to RANSAC, which rejects it when it is smaller
  than the world's share of features.

## Do the YouTube uploads reuse the retained Twitch footage?

**No.** An upload ID is not a session, and the two September uploads sit close
enough to the retained ReqMR broadcasts to be the same matches re-cut, so this
was decided on the pixels rather than on dates.

**The cheap test failed, and it is worth knowing why.** Fingerprinting each file
by its sequence of *(damage, gap since the previous damage)* pairs and looking
for a long shared run found **8 consecutive shared pairs between a May upload
and a September section** — footage that cannot possibly overlap. An expert
repeating the same combo produces the same damage sequence at the same spacing
every time, so this measures a player's habits, not a shared recording. **Do not
use event content to test for duplicate footage.**

The pixels decide it. Sampling all four sources at 1 Hz and comparing perceptual
hashes: matches exist (4–36 per pair), but **they are all scoreboard frames** —
the board's fixed layout collides under the hash while the names and numbers
underneath are completely different. The test that settles it is the *shape* of
the match set: shared footage appears as a **diagonal**, the same time offset
repeated across consecutive seconds. The largest number of matches sharing any
single offset is **1**, against a control of 880/880 for a source against
itself. No diagonal, no shared footage.

Scope: the two September uploads against both retained **ReqMR** sections, which
is where overlap was possible. The April–May uploads predate those broadcasts by
months, and the two DayMR sections are a different player. At 1 Hz an overlap of
a second or two could hide, but any reuse worth caring about — a fight, a match —
would show as a long diagonal.

## Patch fingerprint: dating footage by its own cooldowns

A balance patch moves cooldowns, so **the cooldowns visible in a recording date
it**. That matters for footage whose only date is an upload, and it is the drift
alarm for our own runs: if a live capture stops matching the kit, the game
patched. `observed` in every events file's meta line carries it, per ability.

**The countdown the HUD prints is the measurement. The gap between casts is
not.** A player presses when the fight allows, not when the timer clears, so the
gap distribution has no floor at the true cooldown — and its *minimum* is
whatever artifact is shortest, measured at 0.4–0.6 s for Get Over Here, which
has an 8 s cooldown. `countdown_mode` is the most common number seen the instant
after a cast; reads that caught the timer a tick late fall below it, so the mode
is the full value and the tail sits underneath.

Observed against `docs/spiderman-kit.md` (Season 10, Version 20260911), which is
the only place the patch is stated — **no patch value lives in `perception/`**:

| source | date | Get Over Here | Amazing Combo | team-up |
|---|---|---|---|---|
| four Twitch sections | Season 10 | **8** (37–55 casts) | **1** (22–71) | 15 (21–30) |
| `yjc51uOjKEQ` | Sep 12 | **8** (76) | **1** (67) | 15 (32) |
| `d0C8RMBnFfA` | Sep 11 | **8** (46) | **1** (60) | 15 (34) |
| `ftnk5SVycXY` | May 10 | **8** (120) | **2** (103) | — |
| `Cf_2goe1snQ` | May 9 | **8** (104) | **2** (111) | — |
| `V6iaq9dP8FQ` | Apr 27 | **8** (105) | **2** (56) | — |
| `G7HmV8zyEh8` | Apr 25 | **8** (65) | **2** (68) | — |
| *kit, Season 10* | | 8 s | 1 s (**was 2 s**) | — |

**It works, and it separates the two patches perfectly.** Every Season 10 source
reads Amazing Combo at **1**; all four April–May uploads read **2**, the
pre-Season-10 value — on `V6iaq9dP8FQ` that is 46 of 56 casts with not a single
cast reading 1. Get Over Here reads 8 on both sides, which is right: that patch
touched only Amazing Combo and Parker Power-Up. **A source can now be placed
against the balance history from its own footage**, with no date needed.

The same check on our own live runs is the drift alarm: if a capture stops
matching the kit, the game patched.

One incidental observation from the same table: **none of the four April–May
uploads has an identifiable team-up icon** — each gets a three-entry mapping and
emits no team-up casts — while both September uploads identify all four slots.
So `slot: null` fires on real data exactly as intended, rather than guessing.

### What each fingerprint is consistent with

A fingerprint narrows the patch; it does not name one. Two sources that read
the same could still be on different patches that happen to share these
values. So the loader should record, in this wording, **the patch range the
observation is consistent with** — against the balance history in
`docs/spiderman-kit.md`:

| `observed` value | consistent with | not consistent with |
|---|---|---|
| `uppercut.countdown_mode` = **1** | **Season 10 (Version 20260911) or later**, until the kit next changes Amazing Combo | any patch before Season 10 |
| `uppercut.countdown_mode` = **2** | **before Season 10 (Version 20260911)** | Season 10 as shipped |
| `get_over_here.countdown_mode` = 8 | every patch in the kit history — uninformative | — |
| team-up | nothing: the loaded team-up ability cannot be told apart | — |
| `charges` | nothing beyond kit − 1 on every patch listed | — |

So the six uploads and four sections resolve as: all four Twitch sections and
both September uploads **consistent with Season 10 or later**; all four
April–May uploads **consistent with before Season 10**. Only the lower bound of
"before Season 10" is open — the kit history does not say when Amazing Combo
first became 2 s, so these observations cannot date the April–May footage
more closely than that. A file whose uppercut reads neither 1 nor 2, or whose
mode rests on fewer than about 20 casts, is not consistent with any listed
patch and should stay unknown.

Two things that look like disagreements and are not:

- **The team-up slot reads 15 s everywhere, including confirmed Season 10
  footage, while the kit has Parker Power-Up at 10 s (was 15 s).** The team-up
  ability depends on the partner hero, and `identify_slot` names the *position*,
  not which team-up is loaded into it. A constant 15 across six sources is
  consistent with Symbiote Bond, whose cooldown that patch did not touch. **Not
  a patch mismatch — an ability-identity gap**, and until the two team-ups can
  be told apart this slot cannot date anything.
- **Charge counts read one below the kit** — 1 against 2 for Amazing Combo, 2
  against 3 for Web-Swing, on all six sources. The badge is not drawn at full
  charge, so the highest value it ever shows is one under the maximum. Compare
  against kit − 1.

Web-Swing's countdown is not a fingerprint at all: with three charges on a 6 s
recharge the number shown is whatever recharge is in flight, so its mode carries
no patch information.

## Edited uploads: finding the cuts

A Twitch section is one continuous capture, so a segment can only be interrupted
by something the game did. A YouTube upload is **cut**: the editor splices
unrelated matches, maps and days together. Two frames either side of a splice
are unrelated footage, so a segment that spans one is a fiction — hp 250 before
and 180 after is not 70 damage, it is two different fights.

`scene_cuts()` finds them, and `segment()` breaks on them with
`hard_cut` / `after_cut`. Two things about how, both of which cost an attempt:

**The cut is invisible at the sampling rate and obvious at the native one.** At
the 10 Hz grid these files are sampled on, consecutive frames are 100 ms apart,
and a fast camera whip moves the whole frame as much as a splice does. Measured
on `yjc51uOjKEQ`, mean absolute difference on a 0–255 scale: median 20.5,
p99 47.6, and the actual cuts 52–80. **The distributions overlap, so no
threshold separates them.** At 60 fps adjacent frames barely differ and a splice
stands out, so the detection runs on the video with ffmpeg's own scene score —
one `ffprobe` pass, about two minutes for a 15-minute 1080p60 file.

**The threshold has to clear the in-game overlays, not just the noise floor.**
On that file the scene scores fall in two groups with nothing between them:

| score | what it actually is | count |
|---|---|---|
| 0.40–0.45 | the **scoreboard** opening or closing over continuous play | 10 |
| 0.67–1.00 | abrupt full-frame changes: the game's round-end lightning wipe, a glitch transition, the victory/MVP outro | 8 |

An overlay appearing is a real full-frame change and scores like one. Taking the
obvious "anything above the noise" threshold of 0.4 would have labelled every
scoreboard peek an edit — and on these players that is dozens per section, each
one already carrying its own correct break reason. `CUT_SCORE` is **0.55**, in
the gap. Checked by eye on a before/after sheet of all 18 moments.

A fade is not a cut and must not read as one: it changes the frame gradually, so
every step scores low and none crosses the threshold. Only an abrupt change does.

**The false positives cost almost nothing, but they are not zero.** Run against
the continuous Twitch sections — which have no editorial cuts, so every hit is a
false positive — the detector fires 4 to 15 times per 15 minutes on genuinely
abrupt transitions. Most land inside a scoreboard, killcam or transition the HUD
already excludes, but **some do split a play segment**:

| section | detected | breaking play | play time lost |
|---|---|---|---|
| `reqmr-2871472478-5400-900s` | 4 | 0 | none |
| `reqmr-2873352801-1980-900s` | 15 | 4 | 9.12 → 9.11 min |

**What they are.** The four on `reqmr-2871472478` (t 394.4, 406.3, 436.4, 894.1
s), checked frame by frame: the round-end lightning wipe into ROUND 1 COMPLETE;
the round-complete board snapping to hero select; a round-start flash; ROUND 2
COMPLETE. **Every one is the game's own screen transition at a round boundary**,
none an error of the detector and none inside play. So **`hard_cut` means an
abrupt full-frame discontinuity — an edit *or* a game screen change** — and
either way nothing on one side continues on the other, which is the property a
loader relies on. It does not mean "an editor cut here". The lightning wipe in
the edited uploads is the same game animation, not an editing style.

**A false positive splits a segment, it does not delete play** — the frames
either side stay in the corpus, just in two segments instead of one. Half a
second across a 15-minute section is the whole cost. Note also that a Twitch VOD
is not guaranteed continuous: a streamer switching OBS scenes is a real cut in
the broadcast even when the game is not interrupted, so some of these are
arguably correct detections rather than errors.

### What the six uploads actually contain

| upload | date | raw | usable play | share | cuts | split play | in a gap | segments | events |
|---|---|---|---|---|---|---|---|---|---|
| `G7HmV8zyEh8` | Apr 25 | 14.1 min | **10.91 min** | 77% | 10 | 4 | 6 | 44 | 1496 |
| `V6iaq9dP8FQ` | Apr 27 | 16.2 min | **12.83 min** | 79% | 76 | 21 | 48 | 74 | 1946 |
| `Cf_2goe1snQ` | May 9 | 20.9 min | **16.86 min** | 81% | 55 | 10 | 44 | 58 | 2796 |
| `ftnk5SVycXY` | May 10 | 25.4 min | **20.39 min** | 80% | 7 | 1 | 6 | 75 | 2697 |
| `d0C8RMBnFfA` | Sep 11 | 12.8 min | **10.56 min** | 83% | 6 | 2 | 1 | 42 | 1594 |
| `yjc51uOjKEQ` | Sep 12 | 14.7 min | **13.00 min** | 89% | 8 | 1 | 0 | 48 | 2075 |
| **total** | | **104.1 min** | **84.6 min** | **81%** | 162 | 39 | 105 | | 12604 |

Writer `1336262e179c`. "Split play": the cut falls between two frames of play
and ends a segment there. "In a gap": the cut falls inside a scoreboard, death
or other gap, which then ends `hard_cut` and resumes `after_cut` so it is never
bridged. The other 18 fall before the first segment or after the last.

**An edited upload is the richer source per raw minute: 81% usable against the
retained sections' 64%.** The editor has already cut the queueing, the hero
select and the post-match screens that eat a third of a live broadcast. Budget
on 0.8 for an upload and 0.64 for a raw section.

**Edit density is a property of the upload, not of the era** — 7 cuts in one May
upload and 76 in an April one. So the cut pass cannot be skipped for any file on
the grounds that its neighbours were lightly cut.

**Most cuts fall where the HUD already knows something changed**, at match
boundaries and in outros: only 39 of 162 split a play segment. Those 39
are the whole point — each is a place where a segment would otherwise have
spanned two unrelated fights, and `V6iaq9dP8FQ` alone accounts for 21.

## Camera motion from video: can camera commands be recovered?

`perception/camera_motion.py`, tests in `tests/test_camera_motion.py`. A bounded
feasibility probe under `docs/learning-plan.md`, **E enablers**: no model, no
training, nothing live. Outputs under `data/camera_motion/`.

**Verdict.** Camera *direction* is recoverable from footage well enough to be
a training target; camera *rate* is recoverable coarsely, and only at 60 fps.
At 60 fps, over ordinary turns on held-out range footage, the video gets the
turn direction right 97–99% of the time and reconstructs the commanded stick
to within 0.03–0.05 for slow aim corrections and about 0.15 for the 0.45-stick
spin (neutral baseline: 0.45). The 10 Hz proxies are not enough for anything
faster than slow aim: they fit only a third of fast-turn intervals and
under-read the rest by half. **The range supports no claim about expert VOD
transfer**: there are no swings in it, and the ReqMR minute can be judged for
plausibility only. The next step the spec allows is a small audited expert
transfer set at 60 fps — not bulk inferred actions.

### Three quantities, never merged

| name | what it is | status |
|---|---|---|
| **observed** | matched feature displacement between frames, px | measured |
| **estimated** | camera yaw/pitch fitted to that motion, deg/s | an estimate |
| **inferred** | the stick command that rotation implies through the turn map | an inference |

The pad log is truth about what was **commanded**, nothing more. The turn map
(`agent.controller.Cal`) is a calibration model of what a command does, not
truth about achieved motion — and the probe found regimes where the two part
company (below). So every table here says which comparison each number is:

- **rotation** columns: *estimated* rate against the *map's prediction* from the
  commanded stick — agreement between two models, not accuracy;
- **command** columns: *inferred* stick against *commanded* stick — the real
  inverse-dynamics target, scored against truth.

### Method

ORB features outside the HUD bands, the third-person body and any logged enemy
box; Lowe's ratio test (the defence against repeating wall panels, which defeat
phase correlation); then a rotation-only fit — pixels back-projected to rays
with the calibrated focal length (465 px at 1280 wide), Kabsch inside RANSAC on
two-point samples. No small-angle approximation. The game camera cannot roll, so
fitted roll is world yaw seen from a pitched camera, and world yaw is taken as
the length of the yaw-roll component. Checked against synthetic rotations with
known truth (`K R K⁻¹` warps), including signs, 15° steps and a 40°-pitched
camera.

**Static overlays had to be learned per source.** The first version read the
0.45-stick spin as standing still: the range's "Practice Range" menu panel and
the FPS counter sit outside the fixed HUD mask, never move, and out-voted a
blurred or sparse world. `static_mask` now learns each source's static overlays
from pixel variance across 60 frames spread over the run, restricted to the
frame borders so a camera that holds still does not mask its own world. It
moved held-out stick error on the spin run from 0.20 to 0.07 and direction from
67% to 95%. It does **not** handle animated overlays (DayMR's); those are left
to RANSAC.

### Data and alignment

- Four 300 s range runs with pad state at ~55 Hz (`data/l1/baseline1..4`).
  Their 720p proxies are ~9.3 Hz, one video frame per saved image, so alignment
  is exact by construction.
- Native 60 fps recordings of `baseline4` and `loop30g`, copied from the PC.
  **Their clocks were tied to the logs by image identity** — saved frames found
  in the recording by nearest thumbnail — never by motion, which would fold the
  latency under test into the alignment. Offsets: `baseline4` 3.772 s (24 of 28
  samples agreeing within 26 ms), `loop30g` **3.749 s** (27 of 28 within 30 ms),
  `baseline2` 3.734 s (11 of 28: mostly a static view). `loop30g` had been noted
  as 4.0 s; that figure was rounded, and would have put 250 ms of error straight
  into the latency.
- Held out by **whole run**: the one fitted parameter, the stick-to-motion lag,
  is fitted on three runs and frozen for the fourth. It came out 30 ms in every
  fold. Uncertainty is a bootstrap over contiguous 10 s blocks within a run.
- **Strata.** `still` (no command), `turn` (steady right stick, nothing else),
  `mixed` (stick changed within the interval), `moving` (left stick: translation
  and parallax), `ability` (a button in the preceding 0.5 s: pull and web strike
  drag the camera), `attack` (a trigger held: melee or Web Cluster). **There are
  no swings in any range recording** — no LB press in 67,000 ticks — so nothing
  here validates swing recovery. There is also almost no fast turning: under 20
  ticks above 0.6 stick in all four runs.

### Results, held-out range runs at ~9 Hz (proxies)

Command reconstruction, stick units, with 95% block-bootstrap intervals:

| run (held out) | coverage | inferred vs commanded | neutral | direction right |
|---|---|---|---|---|
| `baseline1` | 0.84 | **0.042** (0.035–0.049) | 0.073 | 88% |
| `baseline3` | 0.79 | **0.048** (0.042–0.056) | 0.100 | 90% |
| `baseline4` (spin) | 0.59 | **0.074** (0.070–0.078) | 0.186 | 95% |
| `baseline2` (still) | 1.00 | 0.002 | 0.000 | — |

By stratum, pooled impressions across the three moving runs: `still` reads
0.2–0.8 deg/s (a correct zero); `attack` and `ability` track the map at r
0.62–0.80; the clean 0.45 `turn` band is fitted on only 33–56% of intervals and
under-reads by 61–76 deg/s against a map of 172. Rotation correlation over all
fitted intervals, estimated vs map: 0.74–0.81.

### 60 fps against 10 Hz, same footage

`baseline4`, lag frozen at 30 ms from the proxy folds:

| clean 0.45-stick spin | 10 Hz | 60 fps |
|---|---|---|
| intervals fitted | 34% | **99%** |
| direction right | 99% | 98% |
| estimated rate, median (map 172) | 83 deg/s | 129 per frame; **150** over 0.1 s |
| inferred vs commanded stick | 0.188 | **0.147** (0.141–0.153) |
| neutral | 0.450 | 0.450 |

At full stick (9 intervals) 60 fps reads 389 deg/s against the map's 415. So
there is a residual under-read of roughly 6–13% against the calibration at 60
fps, which this probe cannot attribute: it may be the estimator (masked centre,
parallax) or the calibration's conditions (measured level, not pitched down).
Slow aim corrections are good at 60 fps: `loop30g` low band r 0.80, 9.8 deg/s
against a neutral 18.8, direction 100%. The 60 fps noise floor on a still camera
is 5 deg/s — per-frame angle noise times 60 — which is why rates should be
averaged over ~0.1 s before use.

**Latency, stick to visible motion: 20 ms**, fitted on the 60 fps `baseline4`
run alone as a diagnostic (the error is flat from 0 to 40 ms and rises steeply
past 70 ms). That matches the controller lane's 17–20 ms pad-to-screen
measurement. `loop30g` is too still to say anything.

### What breaks it

- **Combat holds the camera.** During melee combos the stick commands a turn
  and the camera barely moves — visible frame to frame on `loop30g` (−0.21
  commanded, the world still). Here the video is right and the map is wrong. It
  means an inverse model trained on our pad logs would learn *commanded* stick
  in those windows, while video can only ever show *achieved* motion: these
  strata must be labelled as rotation, not as command.
- **Low frame rate** (above): fast turns abstain or under-read at 10 Hz.
- **Static overlays**: handled by the learned mask. **Animated overlays**: not.
- **Translation**: `moving` intervals err 32–47 deg/s (few samples) — parallax
  that a rotation-only model partly absorbs.
- **Swings and fast mouse flicks**: no paired data; unvalidated.
- The third-person body is masked; the blur of a very fast turn thins features
  but at 60 fps coverage stays at 99%.

### The ReqMR minute: plausibility only

`samples/reqmr-2873352801-1920.mp4`, 1080p60, mouse. **No truth, and a range
score does not transfer**; the focal length assumes our 108° FOV, and a
different FOV would rescale every rate without changing its shape.

At 60 fps the output is **plausible in shape**: 96% of intervals fitted; yaw
rate median 13, p99 419, max 919 deg/s — bounded, and a mouse player's range;
frame-to-frame correlation 0.69 with 5 isolated one-frame spikes in 3,440. Six
bursts above 600 deg/s, **all within a second of a cast** (mostly Web-Swings,
one 70 ms after a Get Over Here), against about 40% of the minute lying within
a second of some cast by chance. But five of the six last a single frame, which
is noise rather than a human flick; only one (134 ms, 877 deg/s, half a second
before a Web-Swing cast) has a flick's duration. A swing moves the camera by
itself, so none of this shows aiming.

**No swing here is labelled aimed, and no anchor is inferred** (VUH-1322). Simple
versus aimed swing is part of the action contract (`docs/learning-plan.md`), and
the HUD's swing event — a charge spent, a recharge countdown appearing — proves
neither the mode nor the anchor. Camera motion before or during a swing is not
evidence of either: with Automatic Swing the game picks the anchor itself, and
the swing arc drives the camera on its own. Nothing in this probe or its outputs
may be read as a swing-mode or anchor label. At 10 Hz the same minute tops out at 236 deg/s: the
fast moves are simply invisible.

### Next

Per the spec, only a small audited expert transfer set at 60 fps: hand-checked
stretches of expert footage where the camera motion is unambiguous, labelled as
**rotation** (not stick — a mouse player has no stick), before any bulk labels.
Swing intervals are excluded from that set: their camera motion cannot be
separated from the arc, and it would say nothing about swing mode or anchor.
Paired swing footage from our own runs is the missing stratum, and has to wait
for the live-input freeze to lift.

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
### read_tagged at native resolution

Measured on L4's 153 native tagged frames (4 trials, one distance ~3 m), with
enemy boxes from `outline.detect` — the real pipeline, not hand-placed boxes:

| | |
|---|---|
| precision | **1.000** (0 false positives) |
| recall | **0.970** (97 of 100 tagged frames) |
| unknown | 1 frame, where the web-shot VFX covers the marker |

**The measurement found a confidently-wrong reader.** The marker template was
cut from a 1280-wide capture and searched at a fixed 0.7–1.5 size ladder, so on
a 2560-wide native frame the marker was off the top of the ladder and
`read_tagged` returned **False** — not None — on every tagged frame. Recall was
**0.000** before the ladder was made relative to frame width. A reader whose
whole contract is "unknown rather than wrong" was handing out a wrong boolean at
a resolution nobody had tested it at. The ladder is now frame-relative, so
distance still moves the marker within it but resolution no longer does.

One disagreement with the delivered truth, resolved in the frames' favour: the
note puts the marker on frames 003–027, but it is **still visible on 028** —
checked by eye on `t0-b-after-web-cluster-028`. Scored as delivered it is
precision 0.990; scored against what the frame shows, 1.000.

**How it should degrade at range.** The marker is drawn in world space above the
enemy, so its on-screen size goes roughly as 1/distance. At ~3 m it measures
about 27x27 px at 2560. The ladder spans 0.7–1.5 of that, which covers roughly
2 m to 4.3 m. **Past about 4.5 m recall should fall away**, not gradually but
sharply, because the marker drops below the smallest template. Extending
`TRACER_SCALES` downward (0.5, 0.35) would cover 6–9 m, but that is arithmetic,
not measurement — it needs frames at those distances before anyone relies on it.
The three misses at 3 m are all box placement, not the marker reader: the enemy
box drifted and the search band went with it.

- **`read_tagged`'s thresholds beyond this distance** (trial1 frames 71–86,
  one bot, one distance). In the 1197 `run1` frames I hold, the web-cluster
  bursts hit scenery rather than bots, so they contain no tagged enemies.
  `tagrun` is being recorded for this; until it lands, the five-scale search
  covers other distances on reasoning rather than measurement. The large web-splat VFX scores 0.45–0.53 against
  the tracer template, below the 0.60 match threshold, so it yields `None` or
  `False` — never a false `True`.
- **The ammo box is cropped tight enough that a two-digit count would clip.**
  Fine for Spider-Man's Web-Cluster; another hero may need the box widened.
