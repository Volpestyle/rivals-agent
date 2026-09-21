# L2 — HUD readers

## Event stream format

### Upgrading a loader from format 2 — the exact diff

`agent/demos.py` reads format 2 and so refuses every file on disk. Everything
below is what changed. **Nothing was removed or renamed between 2 and 4**; format
5 renames the two icon kinds and adds kinds and fields, all listed below.

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
| **5** | **`ability_cast` is recomputed**: a countdown read again after unread frames is the same cooldown, not a new cast (see **Writer fix, format 5**). | Expect fewer casts: 17 visually confirmed duplicates on the train sections are gone. |
| **5** | **Every event gains `known_i` / `known_at`**: when the evidence its assertion needs is available (per kind below). `[t_from, t_to]` is now only **occurrence**: the earliest and latest the change can have happened on evidence alone. For timer events that is the expiry window less the kit's length, no later than the first read — never the frame before the first readable digit — and `amount` is the timer's first read value. | **Select events by `known_at <= now`, never by `t_to`**: a use bounded at 2.0 s may be known only at 3.3 s. A prefix of the reads yields exactly the events whose `known_at` falls inside it. |
| **5** | **Durations are inputs.** meta gains **`kit`**: the source's recorded `patch` and where it came from, the kit `table` used (null: none), per position `{length, lock}` (null = unknown), and `alarms` (a ticking countdown longer than the kit allowed, from when). | `table: null` means every timer-derived event is `ability_uncertain`. Team-up's length is always null: it depends on the partner's variant, which nothing identifies yet. |
| **5** | new kind **`ability_uncertain`** (with `slot`, `slot_pos`, `amount`): a timer this segment may or may not have started, a timer the kit cannot produce, or a single countdown read never confirmed (emitted once its expiry passes). | Treat its interval as **unknown** for that ability: neither a positive nor a negative. |
| **5** | new kind **`cooldown_ended`** (one-charge slots): a timer read in its last seconds (≤ 2) ran out by its own clock. | **History, not readiness.** A recast the reader missed can start the instant it ends; the slot's state after it stays unknown until the next confirmed timer. |
| **5** | `ult_spent` needs the meter seen refilling (part-charged) before it is next lit, and is known from that read; `ult_ready` needs a part-charged meter since it last went dark. Otherwise the ult icon's change is `icon_dimmed` / `icon_lit` with `slot: "ult"`. | A prohibition mark darkens the ult and brings it back full; it is not a spend. |
| **5** | **renamed** `slot_unavailable` → **`icon_dimmed`**, `slot_available` → **`icon_lit`**. Display state only. | Rename; and never read either as availability or as a cast. |
| **5** | `hp_lost` / `hp_gained` gain **`cause`**: `"damage"` / `"heal"` only with max hp read unchanged on each side of the change — one read at or before the last old frame, another after it, up to the confirming frame — else `"unknown"`. Every event carries `cause` (null outside these two). | Do not read `hp_lost` as damage unless `cause == "damage"`. |
| **5** | meta gains **`timer_lengths`** (required): per position `{s, timers, agree, max}`, the tops of the footage's own ticking timers in own-play segments. **A report, never used as a length**: a timer first read late tops out below its full length. | Do not read it as a cooldown. |
| **5** | segment lines gain **`hero_weak_frames`**: frames kept as own play on an own-portrait match under 0.39, `null` when no scores were recorded. | A weak match is low confidence that the hero is ours (see **Segmentation** under **Writer fix**). |
| **5** | `observed` loses `relock_s` for charged slots (they emit no `cooldown_ended`), and its `countdown` counts first-read values, a different distribution from format 4's. | Compare fingerprints only within one format. |

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
batched, and are followed by one regeneration: open sources through
`regenerate` / `from_video`, sources under sealed handling one at a time
through `scripts/regenerate_sealed.py`, which keeps all job output in a mode-600
log nobody reads and prints only source, written, format, writer and check.

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
  press happened somewhere between. At 10 fps that is about 100 ms wide. Timer
  events (`ability_cast`, `ability_uncertain`) are wider: the earliest and
  latest the use can have been on evidence.
- **`known_i` / `known_at` is when the evidence an event needs is available**,
  and no later read changes it: an event, once asserted, is never edited or
  withdrawn; a later contradiction raises a kit alarm and changes only what
  follows. Per kind, the evidence is: the frame proving the new value, for the
  icon, charge, ammo and ult-ready channels; that plus one frame (the despike
  check) and SHIELD_WINDOW frames (the max-hp pairing) for hp, shield and
  max-hp kinds; the confirming second read for a timer's `ability_cast` or
  `ability_uncertain`; for a single unconfirmed read, the first frame past its
  expiry; for `cooldown_ended`, the first frame past the expiry; for
  `ult_spent`, the refill read; for the ult's `icon_dimmed`, the next ult change
  or the segment's real end. On top of each, **SEG_LAG = 12 frames**: the longest
  a frame's own-play membership can still change (a short blip is judged by what
  follows it within LOOKAHEAD = 6 frames). `known_at` may lie past the last frame
  read, for an event still pending when the reads end.
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
- **`format` is 5.** Version 1 had `ability_used` / `ability_ready` and called a
  slot `pull`. Version 2 split those into `ability_cast` and
  `slot_unavailable` / `slot_available`. Version 3 makes `slot` the ability read
  off the icon and adds `slot_pos`. Version 4 adds the editorial-cut break and
  the `cuts` and `observed` meta keys, and later gained the optional
  `cut_times`, `recipe` and per-segment `cooldowns` without a bump. Version 5
  makes countdowns timers, adds `ability_uncertain` and `cooldown_ended`,
  renames the icon kinds and gives hp changes a `cause`. The upgrade table at the top of this
  section is the contract; **Format 3** and **Format 2** below give the
  reasoning behind each.
- Event `kind` is one of: **`ability_cast`** (with `slot`; `amount` is the
  countdown it was first read at), **`ability_uncertain`**, **`cooldown_ended`**,
  **`icon_dimmed`** / **`icon_lit`** (with `slot`), `charges_spent`,
  `charges_regained` (with `slot` and `amount`),
  `web_cluster_fired`, `web_cluster_reloaded`, `hp_lost`, `hp_gained`,
  `shield_decayed`, `shield_gained`, `max_hp_changed`, `ult_ready`, `ult_spent`,
  `ko_feed`, `death`, `respawn`.
- Slots are `teamup`, `swing`, **`get_over_here`** (was `pull`), `uppercut`,
  `ult`.
- **`ability_cast` is the only kind that claims an ability fired.
  `charges_regained` claims a charge is back; `cooldown_ended` claims only that
  a watched timer ran out, and nothing about the slot after it.**
  `icon_dimmed` / `icon_lit` say what the icon looked like — dimmed on a wall
  climb, mid-swing, charmed, red prohibition marks — and nothing about what the
  ability could do.
- **Verified on match footage, per type.** 30 events on the Req clip were checked
  frame by frame against their own before/after crops. What passed, and what did
  not, is in **Hand-check, Req clip** below. Types not marked verified there are
  proposals, not labels.
- **`hp_lost` is damage only when `cause == "damage"`**, which needs max hp read
  unchanged on both sides. Bonus health moves hp too — a team-up shield
  decaying, an ultimate's +250 — and max hp is often unreadable exactly then;
  such changes carry `cause: "unknown"`. Before format 5, where max hp could not
  be read, a shield tick surfaced under this name: 68 of run1's 903 events
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

**Format 5 changes this contract.** Everything below is stated for the frozen
writer `1336262e179c`; a B0 build against format-5 files must apply these
instead:

- **"Lit, no number" certifies nothing.** It is display state: on the stream
  HUD the icon reads lit through 31–91% of its own cooldown frames (see the
  addendum below), and a lit icon beside an unread digit is exactly how a
  continuing cooldown became a phantom cast.
- **Readiness and negative eligibility for a one-charge slot stay unknown
  until a supported resynchronisation**, which is a confirmed countdown read (on
  cooldown: no use possible until its expiry). `cooldown_ended` is not one: a
  recast the reader missed can start the instant a timer ends, so the frames
  after it are unknown, not ready. There is no pixel evidence of "ready" for
  these slots on this HUD. **Charged slots** rest on the charge badge, as
  before.
- **`ability_uncertain` intervals are unknown** for that ability, whatever the
  per-frame reads say.
- **The per-frame sidecars stay valid as raw reads**, and the rows below that
  read `ready` stay valid as descriptions of the icon. What is derived from
  them — which frames are observed, which horizons are negatives — has to be
  recomputed under these rules.
- **Measured cost** (the native-frame reviewer, on b6ae015's weaker rule that
  still let `cooldown_ended` certify ready): team-up alone falls from 92–93% of
  in-segment frames observed to 45–49%, and *all channels known* from 31.8% to
  11.1% (Day) and 20.9% to 11.3% (Req), before B0's 14-consecutive-frame
  requirement. The rule above is stricter still, so those are upper bounds.

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

**Not distinguishable: on these MK clips the raw reads cannot discriminate a
lockout.** This does not show that no lockout state exists. Measured read-only on B0's per-frame sidecars
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

**All 14 events files are format 5, writer `21a390f547eb`** (645ade3),
regenerated on 2026-09-21 from their own recipes; the format-4 originals and
their manifests are kept read-only under
`data/demos/backups/format4-pre-migration-20260921/`. Each recipe records the
patch that selected its kit. For the open sources:

| source | patch (from) | kit |
|---|---|---|
| `sections/daymr-2879354299-21660-900s` (train) | Season 10, Version 20260911 (manifest) | 20260911 |
| `sections/reqmr-2873352801-1980-900s` (train) | Season 10, Version 20260911 (manifest) | 20260911 |
| `daymr-2879354299-21600-60s`, `reqmr-2873352801-1920` (samples) | Season 10, Version 20260911 (manifest) | 20260911 |
| `youtube/Cf_2goe1snQ`, `ftnk5SVycXY`, `G7HmV8zyEh8`, `V6iaq9dP8FQ` | none recorded | none: every Get Over Here timer uncertain; swing and uppercut casts only where a badge decrement places them |
| `guides/day-pull-lesson`, `guides/ffame-stack` | none recorded | none |

The two sealed sections and the two YouTube uploads under the same handling
(`d0C8RMBnFfA`, `yjc51uOjKEQ`) were regenerated through the sealed wrapper;
nothing about their content is recorded here.

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

## Gap-resumption casts (measurement)

**Some `ability_cast` events in the frozen stream are one continuing cooldown,
read again after a short gap, and counted as a new cast.** Read-only
measurement on the two accepted train sources, `daymr-2879354299-21660-900s`
and `reqmr-2873352801-1980-900s`, writer `1336262e179c`. Script and outputs:
`data/l2/` (`gap_casts.py`, `gap_sheets.py`, `gap_b0_impact.py`; the sheets
under `data/l2/sheets/`). No event file, manifest or B0 artifact is changed.

**Mechanism.** The extractor repairs a countdown that drops out for **one**
frame between two numbers. A dropout of two or more frames becomes the value
"off", and the number's return reads as `off → N`: an `ability_cast`. On the
checked frames the countdown is usually visible the whole time, and the reader
fails to read it: over a bright or red background, on a two-digit "11", with
Twitch chat bleeding into the slot's edge, or for three frames while DayMR's
overlay or his translucent scoreboard darkens the slot. The fix belongs in the
frozen writer and goes through the lead.

### The heuristic, exactly

A cast of slot S, first read as N at frame `i_to`, is **flagged** when both:

- **U, unreadable before it:** within the 10 frames (1.0 s) before `i_to`, at
  least one frame has S unreadable: `ready is None` for S's position, the HUD
  absent, or the frame outside every segment.
- **C, compatible with a continuing countdown:** the last frame within 16 s
  before `i_to` on which S's countdown was an integer `v_prev` at `t_prev`
  satisfies `v_prev − Δ − 1.2 ≤ N ≤ v_prev − Δ + 1.2`, where
  `Δ = t_cast − t_prev`, and `v_prev − Δ > −0.2`.

The tolerance is 1.2 s: the display shows whole seconds, so a read of v means
anywhere in a one-second band whose rounding direction is unknown (1 s), plus
one frame's timing either side (0.1 s each). The 16 s lookback is just over the
longest countdown in these sources (team-up, observed 15 s). The full cooldown
per slot (`meta.observed` countdown mode: Get Over Here 8, team-up 15,
uppercut 1) is not part of the flag. It is the evidence a real cast would show:
**the countdown restarting at its full value** rather than continuing.

A flag is a candidate, never a duplicate.

### Denominator, flags and the visual check

Sampling, fixed seed 20260921: the eight casts the annotator disputed; three
further flagged casts per source; every C-only cast (C true, U false), up to two
per source; three unflagged casts per source matched on slot to the flagged
sample. Each was checked on the native 10 Hz frames: the slot's icon from before
the prior countdown to 2 s after, and full frames at −0.5, 0 and +0.5 s.

| source | slot | casts | U | C | flagged (U∧C) | checked | duplicate | valid | unknown |
|---|---|---|---|---|---|---|---|---|---|
| Day | Get Over Here | 43 | 34 | 11 | 9 | 10 | 8 | 2 | 0 |
| Day | team-up | 21 | 11 | 7 | 6 | 3 | 2 | 1 | 0 |
| Day | uppercut | 53 | 33 | 1 | 1 | 0 | — | — | — |
| Day | swing | 22 | 18 | 0 | 0 | 0 | — | — | — |
| Req | Get Over Here | 37 | 33 | 9 | 9 | 8 | 5 | 3 | 0 |
| Req | team-up | 21 | 8 | 6 | 4 | 2 | 2 | 0 | 0 |
| Req | uppercut | 22 | 19 | 4 | 3 | 1 | 0 | 0 | 1 |
| Req | swing | 27 | 20 | 0 | 0 | 0 | — | — | — |
| **total** | | **246** | 176 | **38** | **32** | **24** | **17** | **6** | **1** |

- **All eight disputed casts are confirmed duplicates**: Day Get Over Here at
  41.7, 63.7, 244.4 and 339.3 s; Day team-up at 337.8; Req Get Over Here at
  86.9 and 369.3; Req team-up at 600.4. In each, the countdown runs on through
  the gap (3 → 2 → 1, or 12 → 11 → 10) and never restarts at its full value.
  Two more facts rule out a real cast: Get Over Here and team-up have one
  charge and cannot be used while counting down, and at 369.3 s Spider-Man is
  Frozen.
- **The six unflagged controls are all valid new casts**: the icon is showing,
  then a fresh countdown appears at or near its full value.
- **Req uppercut 52.0 s is unknown.** Its prior "countdown 7" is Twitch chat
  ("back?") read over the slot, so its C is spurious. Uppercut has two charges,
  so a continuing countdown would not rule out a real second use either.

**How the heuristic did, against these 24 only** (the disputed eight were
chosen by the annotator, not at random, so these are not population rates):

| rule | flagged and checked | duplicate among them | duplicates it caught |
|---|---|---|---|
| U∧C, as stated | 13 | 13 | **13 of 17** |
| C alone | 18 | 17 (1 unknown) | **17 of 17** |

**U is the weak half.** Four confirmed duplicates had no unreadable frame at
all: the digit failed to read while the icon still read "lit". Req team-up
600.4 is one of them. C alone flagged every duplicate and no valid cast among
the checked ones. For the one-charge slots (Get Over Here, team-up), a C flag
is strong evidence; for the charged ones (uppercut, swing) it is not, because a
real second use continues the running countdown. C flags **38** of 246 casts:
Day Get Over Here 11, team-up 7, uppercut 1; Req Get Over Here 9, team-up 6,
uppercut 4. No swing is flagged.

### Impact on B0 (read-only; nothing rebuilt or fitted)

Mapped onto `data/experiments/b0-multilabel-v1/windows.json` by interval.
"Confirmed" is the 17 visually confirmed duplicates; "suspected" is every C
flag. Day is the training source of `day-to-req` and the test source of
`req-to-day`; Req the reverse.

| source | channel | B0 unique positives | confirmed: unique hit / windows / left | suspected (C): unique hit / windows / left | ≥ 20 gate |
|---|---|---|---|---|---|
| Day | Get Over Here | 42 | 7 / 29 / 35 | 10 / 42 / 32 | holds either way |
| Day | team-up | **20** | 1 / 4 / **19** | 6 / 28 / **14** | **falls below on the one confirmed** |
| Day | uppercut | 54 | 0 / 0 / 54 | 1 / 5 / 53 | holds |
| Day | swing | 32 | 0 | 0 | holds |
| Req | Get Over Here | 35 | 5 / 24 / 30 | 9 / 43 / 26 | holds either way |
| Req | team-up | 17 | 2 / 8 / 15 | 4 / 18 / 13 | already below |
| Req | uppercut | 23 | 0 / 0 / 23 | 4 / 18 / **19** | falls below only if every suspected one is removed; none is confirmed |
| Req | swing | 35 | 0 | 0 | holds |

"Windows" counts positive windows that contain an affected interval. On the
confirmed set every one of them loses all of its positive intervals for that
channel; on the suspected set all do except 3 of 42 for Day Get Over Here and 4
of 18 for Req uppercut. Two confirmed duplicates are not B0 positives at all,
both removed by B0's own 5 s history rule: Day Get Over Here at 63.8 (1.2 s into
its segment) and Day team-up at 84.8 (see below).

### Three named anomalies

- **Day pt1-04 (context window t 89.3 s): the segmenter should have cut.** From
  84.3 to 84.8 s a "1s SPECTATING" banner is on screen over a white-haired
  teammate's HUD (325/325). At 85.2 s a one-to-two-frame black respawn
  transition, then Spider-Man's own HUD at 85.4 s (250/250). Three gates fail
  on the same second:
  - the banner reader returns nothing for the one-second variant (it reads
    the banner at 79–82.5 s, as it misses "10s SPECTATING" in
    `ftnk5SVycXY`);
  - the portrait check reads the teammate as Spider-Man;
  - the black transition is shorter than the six-frame HUD-absence vote.

  The segment starting at 84.3 s therefore carries three events from the
  teammate's HUD: team-up cast 84.7–84.8 (also a gap duplicate), hp 325 → 50
  and 50 → 250. **B0 excludes them as labels**: its 5 s history rule makes
  89.4 s the segment's first window. It **does not exclude them from history**:
  the four windows 89.4–90.0 s carry the teammate's frames in their 5 s of context.
- **Day ~330.0 s `killcam`: correctly not cut.** One frame reads `killcam`
  while the screen shows ordinary play (Spider-Man inside a shield dome, a
  stream alert). The three-frame banner vote absorbs it and nothing downstream
  changes. B0's windows there are unaffected.
- **Req ~657.7 s scoreboard: the segmenter should have cut, by its own rule.**
  The board fades in at 657.6, is fully open at 657.7–657.8 and gone at 657.9,
  about three frames. The detector reads the two fully open frames, one short
  of the three-frame vote. The HUD never counts as absent because the bar keeps
  reading, so the segment 656.4–684.0 runs straight through. No event falls in
  it. **B0 excludes it from labels** (the segment's first window is 661.4 s),
  but the seven windows 661.4–662.6 s carry it in their history.

## Writer fix, format 5

The root fix for **Gap-resumption casts** above, plus the HP and icon semantics
the learning plan's owner asked for. Two layers, kept apart: what the readers
now read, and what the event logic does with reads it still does not get.

### At the reader: countdown digits

Every visible countdown the old reader returned nothing for, on the two train
sections, failed at **classification, not segmentation**: the right-sized glyph
was found on every threshold pass. Two causes:

- **6 against 8, and 9 against 8, inside the template margin.** A countdown 6
  differs from an 8 only at its open top-right, and normalising to 16x24 smears
  that gap; the classifier then refused (margin under 0.04) or, on one frame,
  was nearer 8. Holes counted on the glyph *before* normalising do not smear: a
  6 has one hole in its lower half, a 9 one in its upper half, an 8 one in each,
  a 0 one tall one. The reader now uses that **only when the templates read
  nothing**, **only between candidates the templates already rank close**, and
  **only when all six threshold passes agree** — a 9 whose tail half-closes over
  a busy background grows a second "hole" on some passes and not others (Day
  team-up 337.7), and one such pass would otherwise read 8.
- **"11" merged into one component twice a digit's width**, which the size
  window threw away, and **"10"**'s 0 had no close countdown template. The same
  topology stage splits a double-width component at its ink valley.

**The change is purely additive**: the template stage is the old reader byte
for byte. Measured on every frame of both train sections against the frozen
reads: **0 changed values, 0 lost reads, 84 new reads**, every one of them on
the same timer as a frozen read of that slot within 1.5 s. The 145-frame
hand-checked accuracy set still reads **0 wrong**. The reader cannot rescue a
digit behind DayMR's translucent scoreboard or his overlays, or two frames the
passes disagree on (Day 337.7–337.8, 339.2–339.3): those are the event logic's.

### At the reader: charge badges on M&K

The M&K layout draws a charge badge two ways: a light disc with a dark digit
("2") and a light digit on a dark centre inside a progress ring ("1"), whose ring
is often too faint to find. The reader tried only the ring, and read neither
across all seven Day uppercut decrements the native re-check found (badge 2 → 1
at 46.6/46.7, 240.9/241.0, 320.9/321.0, 612.9/613.0, 721.4/721.8, 748.9/749.0,
759.0/759.1). It now tries the ring, then the disc, then a lone digit on a dark
centre — each only when the one before reads nothing, so no existing read
changes. A lone digit must be the only digit-sized shape in the badge box:
Twitch chat ("for some 1v1s", Req 163.9–167.2) read as badges before that rule.

**A fallback digit must be digit-shaped** (width ≤ 0.75 × height; a badge
digit is 9-12 px wide by 18-19 high). A bright Twitch emote band abutting a
"2" merged into its digit and read as "1" on every one of the 37 Req uppercut
disc-fallback reads of "1" (237.5–240.1, 250.7, 443.0–444.5), fabricating two
`charges_spent`. The census of every fallback read on both sections: the guard
removes exactly those 37 and one correct "2" (Day 807.7, a badge fading in; the
next frame reads it), changes no other read, and the lone-digit path does not
read those frames either.

Req uppercut around 150 s looked kit-impossible (2 → 1 → 2 in 1.4 s) and is
not: the badge shows "2" under chat at 142.6–143.0, the uppercut lock is
visible at 144.0, the badge reads "1" (mostly under chat) from there to 151.1
across a black transition, and "2" again from 151.2 — a use around 143–144 and
its recharge completing about 7 s later. The spend's interval [142.9, 149.9] is
wide because chat covered the badge; the 1.4 s was its `t_to` to the regain.

Measured on every frame of both train sections: 0 existing reads changed;
about 6,000 (Day) and 4,800 (Req) new swing and uppercut reads; a seeded
sample of 96 new reads checked by eye, 96 correct (chat-covered badges among
them). What else they include: 6 Day Get Over Here "1" reads at 199.2–199.7 and
27 Day uppercut "3" discs at 78.9–80.0 and 315.0–316.4 — the pixels show those
badges — and one Req team-up "2" at 319.2. The 145-frame hand-checked HUD set
still reads 0 wrong. The seven decrements are native regressions.

### In the event logic: durations are inputs, knowledge is when evidence arrives

One forward pass over a segment's frames. Each event is decided at the first
frame where its evidence is complete and **never revisited**, so a prefix of
the reads yields exactly the whole's events with `known_at` inside it (tested
on every prefix of every own-play segment of both train sections, and on the
source cut at tenths).

- **Durations come from a kit table keyed by the source's recorded patch**
  (`KITS` in `perception/events.py`, from `docs/spiderman-kit.md`): Get Over
  Here 8 s; swing 6 s recharge, lock unknown; uppercut 6 s recharge and a 1 s
  lock on Season 10 Version 20260911, 2 s on 20260903. **Team-up's length is
  unknown**: Symbiote Bond is 15 s and Parker Power-Up 10 s, the slot's
  variant is a property of the partner hero and can change mid-match, and the
  icon matcher returns a generic `teamup`. Where the kit, the variant or a value
  is unknown, a one-charge slot's timers are `ability_uncertain`, never casts.
  - **One resolution drives the file.** `from_video(..., patch=)` resolves the
    patch once (`resolve_patch`): the argument if given (`patch_from:
    "argument"`), else the `patch` on the first line of
    `<video stem>.manifest.jsonl` beside the video (`"manifest"`; both train
    sections: "Season 10, Version 20260911"), else none (`"none"`). That patch
    selects the kit `extract()` uses; the meta line's `kit` is built from the
    kit `extract()` actually used (`table` names it, null when there was none)
    together with the resolution and the manifest's own value; the recipe
    records `patch` and `patch_from`, and `regenerate` replays them as recorded
    without consulting the manifest again. **Absent or unrecognised**: no kit,
    every timer-derived event uncertain, a `WARNING` on stderr, `kit.table:
    null`. Written-output tests cover a known, a missing, an unrecognised and an
    overriding patch, each rebuilt by `regenerate` after its manifest changes.
    The frames CLI takes `--patch` (it writes no recipe); the video path has no
    command-line override.
  - `extract()` takes the kit as an argument and defaults to `None`: an
    omitted patch is not evidence of the current one. Tests and fixtures with
    known mechanics pass the kit explicitly.
- **Measured lengths are an alarm, never a calibration.** An observed maximum
  is a lower bound on a full length (a use a second before the first readable
  digit looks exactly like a shorter cooldown), so it cannot shorten a kit
  value. A countdown ticking *above* the kit's length (two values, each read
  twice, over 1.5 s) does contradict it: from that frame on the slot writes
  only uncertainty, and the meta line records the alarm. The alarm is
  one-sided: only evidence that identifies a duration could make it
  two-sided, and nothing here does.
- **Occurrence.** One-charge, known length F: a timer whose digits put its
  expiry in (lo, hi] started in (lo − F, hi − F], no later than its first read.
  The lower side is from the digits exactly; the upper keeps the frame-timing
  slack (TIMER_EPS) and is capped by the first read. A timer first read at its
  full value V at t gives (t − 1, t] — and (t − 0.9, t] when the next frame reads
  V as well. Charged: the use came after the recharge on screen began
  (expiry − recharge), after the previous timer ran out, after the last
  confirmed badge decrement began, and after the last badge read ≥ 1 less the
  lock where the lock is known; no later than the first read. With the
  recharge unknown, the previous timer bounds nothing — its end implies a
  returned charge only through the recharge — and **only an independent badge
  decrement places a use**; it needs no duration. A decrement counts once
  confirmed (two reads) by the frame that confirms the countdown, and only if
  its last pre-drop read came before the countdown's first read; the latest
  such decrement is the bound.
- **Charge evidence is validated against the kit's maximum** (swing 3,
  uppercut 2): a badge read above it is unknown, in the one derivation
  (`charge_evidence`) that both `charges_*` events and cast placement read. The
  raw read in the Hud stays as read, never clamped; without a known maximum a
  read is taken as read.
- **Unknown, and nothing.** A timer that may have started before the segment
  opened is uncertain; one that certainly did is nothing. A single read that
  never confirms is uncertain once its expiry passes (Req uppercut 89.7, 98.5).
  **A kit-impossible timer read while the previous one provably still runs is
  a misread of that one and emits nothing** — including Day team-up 109.9, whose
  uncertain event used to censor 8.2 s of known cooldown. A restart is a cast
  only where its start window meets the previous expiry window, within one
  frame of timing (boundary regressions at 0.1 s and 1 s early).
- **The previous timer** is the confirmed one expiring latest, not the latest
  created (the fabricated Day team-up cast at 101.8).
- **Team-up, variant unknown**: with the patch known and its variant set
  complete (Symbiote Bond 15 s, Parker Power-Up 10 s), each candidate length is
  evaluated on its own against the confirmed timer, and the event's interval is
  the **union** (enclosing interval) of the in-segment start windows the
  candidates allow — never their intersection, never the shortest; each
  window's lower end is clamped to its upper, so no bound falls after the
  first read (needed when the reads leave an expiry window narrower than the
  rounding slack; unexercised on the train sections). A candidate is excluded only by
  the timer's own confirmed value (a countdown never shows more than its
  length, so a read of 15 or 11 rules out 10 s) or by starting before the
  previous timer ended; one that starts before the segment, or would be the
  running cooldown continuing, places no in-segment use, and when no candidate
  does, there is no event (Day 170.5: a segment's first frame reads 11). The
  kind stays `ability_uncertain` whatever remains. **Only a confirmed timer
  narrows**: a single unconfirmed read keeps the broad interval (Req
  (111.3, 136.9]). Unknown patch, an incomplete set, or every candidate
  excluded: the broad interval, from the segment start or the previous timer's
  end. Req [610.9, 642.5] becomes (641.6, 642.5].
- **Reads the kit cannot produce** — above the length, or above the longest
  variant where the variant is unknown (team-up: 15) — are not countdowns.
- **`cooldown_ended`**: a timer read in its last two seconds ran out. History
  only; the observability contract above says what it does not certify.
- **hp's spike filter** uses the largest max hp read so far, never a later one:
  a larger max further on once kept a 200 hp drop (Req 621.7) that a prefix
  ending there had removed. The real-segment prefix test found it.
- **Segmentation settles within SEG_LAG.** A short blip is judged only by what
  follows within LOOKAHEAD = 6 frames, and a clip's leading unknown portrait
  takes the first verdict only when it comes that soon.

### Glyph evidence: measured, switched off

A running countdown replaces the icon glyph, so a frame matching the slot's
**expected** glyph is a candidate witness that no countdown is drawn there.
`hud.glyph_evidence` records it (reader `GLYPH_READER`, thresholds
identify_slot's, frozen before the audit), one-sided: no match is unknown. It
is recorded per frame only when `GLYPH_EVIDENCE` is on, and it is off. Nothing
reads it. Its claim is "glyph displayed / no countdown drawn", **not** "not yet
used": Day uppercut's badge drops at 46.7 while the glyph still matches at 46.8
and the lock reads at 46.9, so the glyph cannot bound a use, and it certifies
no readiness or negative.

Audit over every own-play frame of both sections, per slot, glyph matches
among frames where a countdown is drawn (false matches):

| creator | countdown read by OCR | countdown drawn, OCR missed (bracketed by reads of one timer ≤ 1 s either side) |
|---|---|---|
| Day | 1 / 5,115 (uppercut) | 0 / 86 |
| Req | 0 / 4,133 | 0 / 78 |

Among the unscored frames (no countdown read and none bracketed) it matched
on 9,042 / 14,351 Day and 12,176 / 17,749 Req slot-frames — unscored because
their truth is unknown. On dimmed or prohibition-marked frames it matched 5
/ 489 (Day) and 8 / 237 (Req), all unscored; on the 4 dark frames per source, 0 (Day)
and 2 (Req). Not yet measured: the OCR-missed
denominator is small (164); chat-covered, dark and heavy-effect frames are not
separated (dark frames barely occur inside own play); and no
frame was labelled by eye for this audit. Acceptance, and any use for labels,
is the plan owner's.

### Icon semantics: display state

A dimmed icon or a red prohibition mark (Day 13.9–18.8 s dimmed; 19.5–24.5 s
prohibition marks on three slots) is **what the icon looked like**, and the
events are renamed to say so: `icon_dimmed` / `icon_lit`. Renaming rather than
gating, because the observation is still worth having and a gate would have
thrown it away; and because the old names were read as availability. Only a
countdown (`ability_cast`) or a charge change (`charges_*`) certifies a cast;
nothing on this HUD certifies a one-charge slot's return. The ult's icon is the
same: going dark is `ult_spent` only once the meter is seen part-charged,
refilling, before it is next lit (known from that read), and lighting is
`ult_ready` only after a part-charged meter since it went dark. A prohibition
mark darkens it and brings it straight back full, which is `icon_dimmed` /
`icon_lit` with `slot: "ult"`. The observability contract above says what this
does to B0's rules.

### HP semantics: a change in hp is not a cause

`hp_lost` and `hp_gained` keep the direction the HUD showed and gain `cause`:
`damage` / `heal` only with max hp read unchanged on each side of the change —
one read at or before the last old frame, a different one after it, no later
than the confirming frame (one read serving both sides proves nothing about the
other, and a later one would not be known with the event); a same-delta
max-hp change still becomes `shield_*`, and `max_hp_changed` stays the evidence
channel; everything else is `cause: "unknown"`. On Day 62–71 s the old stream
emitted ten "damage" events for a bonus pool decaying (400 → 304 in 6 and 12 hp
ticks, max hp unread); at 342.2 s a "heal" of 255 that was an ultimate's bonus
health. Both now say unknown.

### Segmentation

- **Two-frame scoreboard taps cut.** The board gets its own two-frame vote;
  banner words keep three, so one false `killcam` frame (Day 330.0) still does
  not cut. Several of the confirmed duplicates' dark gaps were such taps.
- **A black game area cuts at once**, under `no_hud`, when its brightest
  channel averaged over the game area is under 8. Measured over all 17,986
  frames of both train sections (native-frame review): firings reach 7.56; the
  next values up are 10.03–10.19; **ordinary dark gameplay starts at 11.49**
  (Req 46.5 s, combat in the underground map). The margin is 1.4x, not a clean
  gap; boundary tests pin 7 (black) and 11 and 22 (not), and Req 46.5 is a
  native regression. All 15 places it fires are real transitions (checked
  twice, independently; Req 656.1 is the end of a spectated hero, hp 675/675
  then 250/250).
- **The two teammates DayMR spectates are portrait negatives**, beside Doctor
  Strange. They passed the one-class match at 0.36–0.38 and were kept as own
  play around 85, 201, 363, 693 and 718 s. Real Spider-Man frames score at
  most 0.705 against the negatives (391 frames); the teammates 0.72–0.99.
  **Known limit: this is a per-source patch.** The own-hero bar is still the
  one-class 0.34, and the next spectated hero not among the negatives who
  scores in that band passes as own play, silently. What would generalise is
  the SPECTATING banner, which is not read. So a weak own match is made
  visible: segment lines carry `hero_weak_frames`, the frames kept as own play
  on an own-portrait score under 0.39 (own frames: median 0.41, 5th
  percentile 0.396, over 692 sampled own-play frames; the teammates 0.36–0.38).
- **The "1s SPECTATING" banner is not read by the banner reader**, and the
  offset search tried for it read "killcam" over ordinary play on 2,251 Req
  frames and 475 Day frames, so it is not part of this fix. The stretch is closed
  by the teammate's portrait and the respawn black instead.

### Checks

- **Review probes as regressions**: the first review's eight, the second
  round's five and the third round's six (three findings, three positive
  controls), all passing; the three findings fail on a63a510. Two of the first
  review's eight carry declared adaptations: one selects on `known_at` instead
  of `t_to`, one passes the kit explicitly. One of the eight is restated on
  `known_at`: it selected by `t_to`, which was the knowledge time then and is
  occurrence now. The native reviews' findings each have a regression,
  including the seven M&K badge decrements, Req chat over a badge, and the
  fabricated team-up cast (a numbers fixture of Day 101.6–145.6 s).
- **The prefix invariant, executable**: for every prefix, the events with
  `known_i` inside it equal the whole's, field for field, with identical kit
  inputs. It runs over every fixture sequence, over the review probes'
  sequences, over synthetic runs built to stress it (a blip on the frame that
  changes, a blip followed by two seconds of unknown portrait, an hp spike, a
  shield tick with max hp a frame late, the ult's refill arriving later), and
  over **every prefix of every own-play segment of both train sections** plus
  the whole source cut at tenths (native, `RIVALS_DATA`).
- **Not vacuous**: the 6 valid controls and the 3 charged second uses must come
  out as casts with finite bounds, width ≤ 2.5 s and `known_at − t_to` ≤ 1.5 s
  (measured 0.9–2.3 s and 0.1–1.1 s, from extract_one, without the segment
  lag); every prefix test also asserts a minimum count of known casts.
- **Mutations in a scratch copy: 72 of 72 killed.** The union's lower-end
  clamp is load-bearing: two team-up reads of 15 exactly 1.2 s apart leave an
  expiry window so narrow that the 15 s candidate's start window has its lower
  end up to TIMER_EPS after its upper, and without the clamp the event's `t_to`
  lands a frame after the frame on which the countdown was already read
  running. That synthetic case is a regression; no kept window needs the clamp
  on the two train sections, so their output does not depend on it. (Two
  earlier counts here were wrong: 68 of 68 named the "meta `table` from the
  resolved patch" mutant as killed when it survived, and 71 of 72 called the
  clamp mutant equivalent when it is not.)
  Among the killed: the disc
  fallback accepting a wide blob, the file-writing path using the reference kit
  or an unknown patch defaulting to it, regenerate dropping the recorded patch,
  the meta `table` taken from the patch instead of the kit used, extraction with
  no kit while the meta claims the patch, a variant shorter than its countdown
  kept, one unconfirmed digit narrowed by the variants, a later or the
  earliest decrement placing a use, and the variant union intersected, reduced
  to the shortest, used without a complete set, or promoted to a cast; restoring a
  default kit, letting the previous timer bound a use with the recharge
  unknown, dropping or clamping the charge maximum in either path, removing the
  segmentation lag, the hp settling, the bounded lookahead, the causal spike
  ceiling, closed timers, the alarm's confirmation and span, the kit ceiling,
  the misread-inside-a-running-timer rule, and the badge fallbacks and their
  chat rule.
- Tests that read local data honour `RIVALS_DATA`, so from a worktree they
  run against a checkout's `data/`. Those that open anything under
  `data/demos` are marked `corpus` and run only with `--corpus`; one of them
  checks that every file under `data/demos/events/` is at the current format
  and writer.
- Fixtures are numbers (per-frame reads) and small portrait-region crops only;
  whole-frame checks read native frames from `RIVALS_DATA` and skip without it.

### Deferred, not built

- **Charm and frozen state readers.** Frozen and charmed Spider-Man shows the
  prohibition marks and cannot cast; nothing reads that state yet, so those
  stretches are simply icon display plus whatever countdowns do.
- **KO-medal readers.** The kill feed is read as a line appearing (`ko_feed`);
  the medals and streak banners are not.

### Stage-2 seams (other owners; nothing here edits them)

- **Loader and policy gate on `known_at`.** The loader gates observation
  construction and validation, and each historical policy event-feature step,
  on `known_at`; occurrence bounds `[t_from, t_to]` remain for targets. A
  format-5 file missing `known_at` fails loudly and never falls back to `t_to`.
  `cause` and the renamed kinds are updated together. Selecting on `t_to`
  would backdate every event by the settling lag (1.3 s for a cast). The
  loader (9c2169f) and the policy consumers (cafcfc0) do this; the corpus was
  regenerated after both landed. The format-4 originals stay untouched in the
  backup.
- **B0**: censor `ability_uncertain` intervals for their ability; use
  `known_at` for causal inputs and `[t_from, t_to]` only as occurrence; apply
  the observability contract (readiness unknown after `cooldown_ended`); drop or
  flag a slot whose meta `kit.alarms` fired; recompute its causal baselines.
- **Policy**: `EVENT_KINDS` gains `ability_uncertain` and `cooldown_ended` and
  renames the icon kinds.
- **Team-up variant**: per-segment partner identity needs its own verified
  reader; until then team-up timer events stay uncertain, bounded by the
  variant union.
- **Old sidecars and event files are archives.** Retained frames are re-read
  under the new writer into a new output, never relabelled in place.

### Dry run on the two train sections (read-only; no event file changed)

The whole pipeline from the VODs, writer `21a390f547eb`, kit resolved from
each source's manifest (Season 10, Version 20260911, recorded in the recipe),
no alarms, against the frozen stream (`1336262e179c`). Scratch only.

| source | slot | casts: frozen → **now** | `ability_uncertain` |
|---|---|---|---|
| Day | Get Over Here | 43 → **30** | 1 |
| Day | team-up | 21 → **0** | 14 |
| Day | uppercut | 53 → **53** | 6 |
| Day | swing | 22 → **21** | 4 |
| Req | Get Over Here | 37 → **27** | 0 |
| Req | team-up | 21 → **0** | 15 |
| Req | uppercut | 22 → **12** | 6 |
| Req | swing | 27 → **27** | 1 |

- **Team-up has no casts**: its variant is unknown. Bounded by the variant
  union, its uncertain events censor 12.5 s of Day play and 37.9 s of Req
  (median 0.9 s each), where the broad interval censored 127.9 s and 226.7 s.
- **The seven Day uppercut uses** are casts placed by their badge decrements:
  (46.6, 46.9], (240.9, 241.1], (320.9, 321.8], (612.9, 613.2], (721.4, 721.8],
  (748.9, 749.2], (759.0, 759.3]. `t_from` is the last frame still showing the
  old count, so the use is after it.
- **The 17 confirmed duplicates**: none emits anything. **The 6 valid controls**:
  5 casts (Day Get Over Here 226.0 (225.1, 226.0], 255.6 (254.7, 255.6]; Req
  254.0 (253.1, 254.0], 143.7 (141.8, 142.9], 621.2 (619.3, 620.4]); Day
  team-up 297.4 is uncertain. **The 3 charged second uses** are casts: Day swing
  51.5 (49.7, 51.5], Day uppercut 140.5 (139.0, 140.5], Req swing 93.4
  (91.1, 93.4].
- **Charge events**, frozen → now: `charges_spent` Day 40 → 133 (uppercut 56,
  swing 77), Req 33 → 103 (uppercut 25, swing 78); `charges_regained` Day 29 →
  106 (44, 62), Req 25 → 88 (22, 66) — the M&K badge reads. The digit-shape
  guard removed Req uppercut's two fabricated spends (229.9–237.6 and
  439.4–443.1) and the regain after the second; the kit maximum makes 7 Day
  uppercut reads unknown and changes no event.
- **Occurrence widths**, `t_to − t_from` of casts whose first read equals the
  kit length (8 s Get Over Here, 6 s swing and uppercut): Day 31 (0.9 s on 26,
  0.8 on 1, 0.3 on 3, 0.2 on 1 — the charged ones tightened by a decrement),
  Req 20, all 0.9 s. First read below the length: Day 73, median 0.5 s (p10
  0.1, p90 1.9, max 3.3); Req 46, median 1.1 s (p10 0.1, p90 4.3, max 5.9).
  The native re-check reported different width figures with the same counts;
  these were re-derived from this run's events with that definition.
- **`known_at − t_to`** for casts: median 1.3 s, max 2.1 s; 1.2 s of it is
  SEG_LAG, an upper bound on when membership settles (it needs at most 10
  frames), the rest confirmation.
- **`cooldown_ended`**: Day 33, Req 27. **Segments**: Day 48, Req 32.
- **Against bdc145b**, exactly two lines differ, both Day team-up: the
  zero-width `ability_uncertain` at (170.6, 170.6] is gone (the 10 s variant
  cannot show 11; the 15 s one started before the segment), and that timer,
  now one that predates the segment, has its end recorded as history,
  `cooldown_ended` (180.7, 181.0]. Req is identical apart from the writer.

## Bonus maximum health and hp cause (measured, VUH-1306)

Read-only, on the two promoted train sections under writer `21a390f547eb`;
native frames read by eye. A **bonus pool** is the blue segment on the hp bar:
maximum health above 250 (the ultimate's +250, a team-up shield). It arrives and
leaves as hp and max hp moving together.

**Every `max_hp_changed` row, and what the frames show:**

| source | row | frames | verdict |
|---|---|---|---|
| Day | (64.5, 65.7] 40 → 400 | 400/400 throughout; "40" read once under a diagonal streak | **misread**: the segment's first max read |
| Day | (765.9, 766.7] 500 → 250 | 500/500 with a blue segment, then 250/250 | real: the bonus pool ends |
| Req | (11.9, 13.7] 250 → 500 | 242/250 → 246/250 → 496/500, blue segment appears | real: the bonus arrives |
| Req | (14.0, 18.7] 500 → 250 | 500/500 → 420/420 → 250/250 | real: the pool shrinks in two steps |
| Req | (627.6, 628.3] 250 → 500 | 229/250 → 479/500 | real: the bonus arrives |
| Req | (630.5, 635.3] 500 → 250 | 500/500 with a blue segment, then 250/250 | real: the pool ends |
| Req | (664.1, 664.7] 25 → 250 | 175/250 throughout; "25" read once under a web overlay | **misread**: the segment's first max read |

**Every hp event beside a max change, and every damage or heal label with hp
above 250 on either side** (the bonus present), checked on the frames:

| source | event | cause written | frames | right? |
|---|---|---|---|---|
| Day | `hp_lost` (765.8, 766.0] 500 → 250 | damage | the pool ends; nothing hit | **no** |
| Day | `hp_lost` (65.9, 67.2] 400 → 394 | unknown | a bonus pool decaying | yes |
| Req | `hp_gained` (11.8, 12.1] 242 → 500, 258 | heal | the bonus arrives, with a few hp of healing | **no** |
| Req | `hp_lost` (14.2, 14.3] 500 → 420 and (14.9, 15.0] 420 → 250 | unknown | the pool shrinking | yes |
| Req | `hp_gained` (627.7, 627.8] 229 → 479 | unknown | the bonus arrives | yes |
| Req | `hp_gained` 479 → 491 → 495 → 499 (628.2–629.1) | heal | 4 hp ticks under a steady 500/500, bar glowing green | yes |
| Req | `hp_lost` (629.9, 630.7] 500 → 250 | damage | the pool ends; nothing hit | **no** |

So **three events are mislabelled**: Day one of its 19 `damage` labels; Req
one of its 27 `damage` labels and one of its 63 `heal` labels. The other
bonus arrivals and departures already say cause unknown.

**Why the cause came out known.** `cause` needs max hp read unchanged on each
side of the change: one read at or before the last frame showing the old hp,
another after it, no later than the frame confirming the new hp. The after
side is searched over the frames between the last old hp read and the first new
one. When hp goes unread there for a frame or more, those frames still show the
**old** maximum. They are before the change, not after it: Day 765.9 reads
max 500 with hp unread, Req 630.1–630.6 likewise, and Req 11.9 reads max 250.
So the rule sees 500 → 500 (or 250 → 250) and writes damage or heal. The shield
fold (`_merge_shield`) would have caught the two losses, a same-delta
`max_hp_changed`, but it pairs only within SHIELD_WINDOW = 3 frames of the hp
event's confirmation, and max hp is confirmed 7 and 8 frames later, after
unread frames and its two-read hold.

**Why the two maxima are misread.** A channel's first sighting in a segment
becomes its value at once, without the hold that every later change needs. A
single misread "40" or "25", the first max read of its segment, becomes the
`before` of a change that never happened.

### Proposed for the next writer opening (not built)

Recorded for a future writer opening; none is being implemented now.

- **R1, the after-side max read comes from after the change.** Take max hp's
  after-side read from the frames at or after the first frame reading the new
  hp, up to that event's settling frame (i_to + HP_SETTLE, already its
  `known_at`, so nothing is decided later than now), never from the gap before
  it. An unread or different max there gives cause unknown. All three mislabels
  become unknown: Day 766.0–766.4 and Req 630.7–631.1 read no max; Req
  12.1–12.5 read none either, and a 500 there would differ from 250.
  **Regression frames**: Day 765.8–766.0; Req 629.9–630.7; Req 11.7–12.1.
  **Controls that must keep their labels**: Req 628.2–629.1, heals, with max
  500 read at 628.3–628.5 and 628.9; and a damage control with max 250 read
  after the change, chosen at the opening.
- **R2, the first sighting needs the hold.** A debounced channel takes its
  first value only after `hold` agreeing reads, as for a change. That removes
  both phantom maxima. **Regression frames**: Day 64.5; Req 664.1. It changes
  every channel with a hold of 2 (charges, webs, max hp, kill feed), so its
  effect on each is measured at the opening before it is accepted.
- The alternative to R1, folding a same-delta `max_hp_changed` whose interval
  overlaps the hp event's (not only within 3 frames), catches the two losses
  but not the heal (the max change at 11.9 is +250 against +258). R1 is the
  smaller rule.

### Team-up variant on the train sections (measured, VUH-1306)

Read-only, by eye on native frames (`data/experiments/b0/frames/<source>/`), one
tile of the team-up slot at the start, middle and end of each own-play segment
where no countdown was read. The two icons: Symbiote Bond (Venom) a jagged
radial burst, 15 s; Parker Power-Up (Peni Parker) a bomb, 10 s on this patch
(`docs/spiderman-kit.md`).

**Coverage.** Three tiles per segment were inspected. Every legible one shows
Symbiote Bond: DayMR in 37 of 48 segments (seg 18 shows only its countdown),
ReqMR in 21 of 32. No bomb appears in any inspected frame: no contrary
evidence. The other segments have **unknown** identity: short stretches (1 to
23 icon frames) of another screen, another hero's ability row kept as own play
for a few frames, or a blur. Sampled points do not show that the variant never
changes in the frames between them or in the segments with no legible icon;
identity is supported only where it was seen.

| source | seg | t | variant seen | sure | frame (middle tile) |
|---|---|---|---|---|---|
| Day | 0 | 0.0–2.6 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/000014.jpg` |
| Day | 1 | 4.5–8.1 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/000064.jpg` |
| Day | 2 | 8.9–41.5 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/000253.jpg` |
| Day | 3 | 41.8–59.8 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/000509.jpg` |
| Day | 4 | 60.3–61.4 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/000610.jpg` |
| Day | 5 | 62.6–63.5 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/000632.jpg` |
| Day | 6 | 63.8–75.2 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/000696.jpg` |
| Day | 7 | 85.4–101.1 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/000930.jpg` |
| Day | 8 | 101.6–145.6 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/001379.jpg` |
| Day | 9 | 152.5–152.5 | none legible (crossed slashes: another screen) | — | `daymr-2879354299-21660-900s/001526.jpg` |
| Day | 10 | 153.2–153.2 | none legible (another screen) | — | `daymr-2879354299-21660-900s/001533.jpg` |
| Day | 11 | 154.6–155.4 | none legible (another hero's ability icon) | — | `daymr-2879354299-21660-900s/001551.jpg` |
| Day | 12 | 155.8–170.1 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/001610.jpg` |
| Day | 13 | 170.5–191.8 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/001841.jpg` |
| Day | 14 | 202.1–213.5 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/002079.jpg` |
| Day | 15 | 214.1–236.9 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/002205.jpg` |
| Day | 16 | 237.2–282.8 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/002698.jpg` |
| Day | 17 | 285.4–300.6 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/002915.jpg` |
| Day | 18 | 300.9–306.7 | slot drawn, countdown only (10, 10, 8) | no icon | `daymr-2879354299-21660-900s/003034.jpg` |
| Day | 19 | 313.4–313.4 | none legible (blurred) | — | `daymr-2879354299-21660-900s/003135.jpg` |
| Day | 20 | 315.8–316.5 | none legible (another hero's ability icon) | — | `daymr-2879354299-21660-900s/003163.jpg` |
| Day | 21 | 316.8–352.6 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/003261.jpg` |
| Day | 22 | 356.1–356.3 | none legible (another hero's ability icon) | — | `daymr-2879354299-21660-900s/003563.jpg` |
| Day | 23 | 388.4–390.6 | none legible (white, blurred) | — | `daymr-2879354299-21660-900s/003896.jpg` |
| Day | 24 | 576.6–576.9 | none legible (a menu (Spider-Man portrait)) | — | `daymr-2879354299-21660-900s/005769.jpg` |
| Day | 25 | 588.3–594.1 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/005913.jpg` |
| Day | 26 | 594.7–595.7 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/005953.jpg` |
| Day | 27 | 598.1–598.9 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/005986.jpg` |
| Day | 28 | 599.5–604.4 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/006021.jpg` |
| Day | 29 | 604.8–606.9 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/006060.jpg` |
| Day | 30 | 607.4–636.9 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/006178.jpg` |
| Day | 31 | 637.9–666.7 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/006548.jpg` |
| Day | 32 | 668.5–683.7 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/006732.jpg` |
| Day | 33 | 693.8–696.2 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/006951.jpg` |
| Day | 34 | 698.0–709.2 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/007010.jpg` |
| Day | 35 | 719.4–734.0 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/007235.jpg` |
| Day | 36 | 734.4–735.1 | none legible (blurred) | — | `daymr-2879354299-21660-900s/007352.jpg` |
| Day | 37 | 737.4–743.2 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/007429.jpg` |
| Day | 38 | 743.5–745.5 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/007446.jpg` |
| Day | 39 | 745.8–754.4 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/007502.jpg` |
| Day | 40 | 754.8–769.1 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/007621.jpg` |
| Day | 41 | 769.5–770.4 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/007701.jpg` |
| Day | 42 | 771.4–780.8 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/007762.jpg` |
| Day | 43 | 781.1–781.3 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/007813.jpg` |
| Day | 44 | 781.8–793.0 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/007875.jpg` |
| Day | 45 | 793.7–795.0 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/007945.jpg` |
| Day | 46 | 795.6–802.5 | Symbiote Bond (jagged radial burst) | high | `daymr-2879354299-21660-900s/007979.jpg` |
| Day | 47 | 803.1–803.2 | none legible (blurred) | — | `daymr-2879354299-21660-900s/008033.jpg` |
| Req | 0 | 0.0–5.5 | Symbiote Bond (jagged radial burst) | high | `reqmr-2873352801-1980-900s/000029.jpg` |
| Req | 1 | 7.2–54.0 | Symbiote Bond (jagged radial burst) | high | `reqmr-2873352801-1980-900s/000271.jpg` |
| Req | 2 | 54.8–58.0 | none legible (grey blur) | — | `reqmr-2873352801-1980-900s/000581.jpg` |
| Req | 3 | 58.5–72.0 | Symbiote Bond (jagged radial burst) | high | `reqmr-2873352801-1980-900s/000672.jpg` |
| Req | 4 | 72.7–110.6 | Symbiote Bond (jagged radial burst) | high | `reqmr-2873352801-1980-900s/000844.jpg` |
| Req | 5 | 111.3–150.2 | Symbiote Bond (jagged radial burst) | high | `reqmr-2873352801-1980-900s/001244.jpg` |
| Req | 6 | 150.9–152.2 | none legible (dark, no slot) | — | `reqmr-2873352801-1980-900s/001522.jpg` |
| Req | 7 | 194.4–197.8 | Symbiote Bond (jagged radial burst) | high | `reqmr-2873352801-1980-900s/001962.jpg` |
| Req | 8 | 198.3–243.3 | Symbiote Bond (jagged radial burst) | high | `reqmr-2873352801-1980-900s/002209.jpg` |
| Req | 9 | 246.0–274.6 | Symbiote Bond (jagged radial burst) | high | `reqmr-2873352801-1980-900s/002679.jpg` |
| Req | 10 | 275.7–275.7 | none legible (blurred) | — | `reqmr-2873352801-1980-900s/002758.jpg` |
| Req | 11 | 283.6–283.6 | none legible (white card: another screen) | — | `reqmr-2873352801-1980-900s/002837.jpg` |
| Req | 12 | 284.8–304.7 | Symbiote Bond (jagged radial burst) | high | `reqmr-2873352801-1980-900s/002927.jpg` |
| Req | 13 | 313.8–314.0 | none legible (another hero's ability icon) | — | `reqmr-2873352801-1980-900s/003140.jpg` |
| Req | 14 | 315.1–333.5 | Symbiote Bond (jagged radial burst) | high | `reqmr-2873352801-1980-900s/003244.jpg` |
| Req | 15 | 334.0–342.6 | Symbiote Bond (jagged radial burst) | high | `reqmr-2873352801-1980-900s/003384.jpg` |
| Req | 16 | 342.9–354.8 | Symbiote Bond (jagged radial burst) | high | `reqmr-2873352801-1980-900s/003490.jpg` |
| Req | 17 | 355.0–384.5 | Symbiote Bond (jagged radial burst) | high | `reqmr-2873352801-1980-900s/003659.jpg` |
| Req | 18 | 385.0–385.8 | none legible (grey blur) | — | `reqmr-2873352801-1980-900s/003859.jpg` |
| Req | 19 | 386.2–386.2 | none legible (no icon frame) | — | — |
| Req | 20 | 428.6–434.2 | Symbiote Bond (jagged radial burst) | high | `reqmr-2873352801-1980-900s/004315.jpg` |
| Req | 21 | 435.4–462.9 | Symbiote Bond (jagged radial burst) | high | `reqmr-2873352801-1980-900s/004493.jpg` |
| Req | 22 | 464.3–515.9 | Symbiote Bond (jagged radial burst) | high | `reqmr-2873352801-1980-900s/004824.jpg` |
| Req | 23 | 526.5–538.6 | Symbiote Bond (jagged radial burst) | high | `reqmr-2873352801-1980-900s/005344.jpg` |
| Req | 24 | 539.9–541.2 | Symbiote Bond (jagged radial burst) | high | `reqmr-2873352801-1980-900s/005407.jpg` |
| Req | 25 | 541.6–589.1 | Symbiote Bond (jagged radial burst) | high | `reqmr-2873352801-1980-900s/005729.jpg` |
| Req | 26 | 589.7–646.1 | Symbiote Bond (jagged radial burst) | high | `reqmr-2873352801-1980-900s/006235.jpg` |
| Req | 27 | 656.4–657.6 | none legible (overlay) | — | `reqmr-2873352801-1980-900s/006569.jpg` |
| Req | 28 | 657.9–684.0 | Symbiote Bond (jagged radial burst) | high | `reqmr-2873352801-1980-900s/006677.jpg` |
| Req | 29 | 689.7–689.7 | none legible (another hero's ability icon) | — | `reqmr-2873352801-1980-900s/006898.jpg` |
| Req | 30 | 690.1–692.0 | none legible (another hero's ability icon) | — | `reqmr-2873352801-1980-900s/006919.jpg` |
| Req | 31 | 714.1–715.3 | none legible (another screen) | — | `reqmr-2873352801-1980-900s/007148.jpg` |

**Supported identity, per team-up timer.** For each of the 29 team-up timers,
the three frames immediately before its first countdown read were inspected:
the icon on screen at or just before the use. All 29 show the Symbiote Bond
burst (often lit yellow on the use). These frames, and the sampled tiles in the
table above, are the intervals with supported identity:

| source | event (now `ability_uncertain`) | seg | icon frames inspected | icon | first countdown read |
|---|---|---|---|---|---|
| Day | (99.5, 100.4] | 7 | 100.1–100.3 | Symbiote Bond | 100.4 |
| Day | (120.9, 121.8] | 8 | 121.5–121.7 | Symbiote Bond | 121.8 |
| Day | (164.9, 165.8] | 12 | 165.5–165.7 | Symbiote Bond | 165.8 |
| Day | (186.5, 187.4] | 13 | 187.1–187.3 | Symbiote Bond | 187.4 |
| Day | (225.7, 226.6] | 15 | 226.3–226.5 | Symbiote Bond | 226.6 |
| Day | (245.0, 245.9] | 16 | 245.6–245.8 | Symbiote Bond | 245.9 |
| Day | (296.5, 297.4] | 17 | 297.1–297.3 | Symbiote Bond | 297.4 |
| Day | (330.4, 331.3] | 21 | 331.0–331.2 | Symbiote Bond | 331.3 |
| Day | (348.9, 349.8] | 21 | 349.5–349.7 | Symbiote Bond | 349.8 |
| Day | (626.6, 627.5] | 30 | 627.2–627.4 | Symbiote Bond | 627.5 |
| Day | (676.9, 677.8] | 32 | 677.5–677.7 | Symbiote Bond | 677.8 |
| Day | (702.9, 703.8] | 34 | 703.5–703.7 | Symbiote Bond | 703.8 |
| Day | (726.4, 727.2] | 35 | 726.9–727.1 | Symbiote Bond | 727.2 |
| Day | (799.2, 800.1] | 46 | 799.8–800.0 | Symbiote Bond | 800.1 |
| Req | (7.2, 7.8] | 1 | 7.5–7.7 | Symbiote Bond | 7.8 |
| Req | (27.7, 28.6] | 1 | 28.3–28.5 | Symbiote Bond | 28.6 |
| Req | (46.2, 47.1] | 1 | 46.8–47.0 | Symbiote Bond | 47.1 |
| Req | (85.1, 86.0] | 4 | 85.7–85.9 | Symbiote Bond | 86.0 |
| Req | (111.3, 136.9] | 5 | 136.6–136.8 | Symbiote Bond | 136.9 |
| Req | (136.1, 137.0] | 5 | 136.6–136.8 | Symbiote Bond | 136.9 |
| Req | (251.3, 252.2] | 9 | 251.9–252.1 | Symbiote Bond | 252.2 |
| Req | (299.5, 300.4] | 12 | 300.1–300.3 | Symbiote Bond | 300.4 |
| Req | (375.5, 376.4] | 17 | 376.1–376.3 | Symbiote Bond | 376.4 |
| Req | (484.7, 485.6] | 22 | 485.3–485.5 | Symbiote Bond | 485.6 |
| Req | (514.3, 515.2] | 22 | 514.9–515.1 | Symbiote Bond | 515.2 |
| Req | (555.0, 555.9] | 25 | 555.6–555.8 | Symbiote Bond | 555.9 |
| Req | (595.3, 596.2] | 26 | 595.9–596.1 | Symbiote Bond | 596.2 |
| Req | (641.6, 642.5] | 26 | 642.2–642.4 | Symbiote Bond | 642.5 |
| Req | (676.1, 677.0] | 28 | 676.7–676.9 | Symbiote Bond | 677.0 |

Req (111.3, 136.9] is a single "1" read at 136.9, the frame on which the next
timer's "15" appears; its icon evidence is that timer's.

**A reader is not needed for these two sources.** The icon matcher
(`identify_slot`) has one generic `teamup` template and cannot separate the two
by construction; a per-variant template was not built, because a declaration
covers both sessions. It becomes necessary for a source whose partner changes
mid-match, which neither of these does.

**What a known variant would change** (current reader, each segment's team-up
events extracted as now and with Symbiote Bond's 15 s supplied). Recovered
identity alone certifies nothing: the accepted occurrence rules still decide.
"Eligible" below means the event would be written `ability_cast` under them — a
confirmed timer, a start window inside its segment, no running or continuing
cooldown it conflicts with. Nothing is promoted; no writer, kit or manifest
change is made.

| source | now: `ability_uncertain` | eligible as `ability_cast` with 15 s known | still uncertain |
|---|---|---|---|
| Day | 14 | 14 (first read 15 on all; width 0.8–0.9 s) | 0 |
| Req | 15 | 13 (first read 15 on all; width 0.9 s) | 2 |

The intervals do not move: a confirmed first read of 15 already excludes the
10 s variant, so the union bounds are the 15 s ones. Declaring the variant
changes eligibility, not the width. Req's two that stay uncertain: (7.2, 7.8], the
segment opening at 7.2 with the first "15" at 7.8, so the start window
(6.8, 7.8] crosses the segment start; and (121.7, 136.9], a single "1" that never
confirms (single reads never narrow).

- **R3, a declared team-up variant (one possible outcome, not decided).** A
  source's recipe may carry a team-up variant declaration with its provenance
  (by-eye audit, frames named) and only the time ranges with supported
  identity; a per-source declaration covering unobserved stretches is a
  judgment the plan owner makes, not something these samples prove. Within them the kit uses that variant's length and
  team-up timers classify as for any known length; outside them, or with no
  declaration, the variant stays unknown and the union rule applies. No
  declaration is inferred. A source whose partner changes gets one range per
  partner, or a per-variant icon reader measured before use.
  **Regression frames**: Day team-up 297.4 (becomes eligible as a cast,
  (296.5, 297.4]); Req 642.5 (eligible, (641.6, 642.5]); Req 7.2–7.8 (stays uncertain: crosses the
  segment start); Req 121.7–136.9 (stays uncertain: one unconfirmed read); and
  a source with no declaration, whose team-up events are unchanged.

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
