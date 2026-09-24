# Lane: ability casts and resources from the replay HUD (VUH-1306, feeds VUH-1353)

**Lane writer:** pilot-prep.
**Scope:** offline only; no game input; no learned model.

The goal is the first partial expert label: the followed player's own HUD in an in-client replay, read with James's
existing readers (`perception/hud.py`, unmodified), turned into per-frame states and cast events that abstain rather
than guess.

**Code:**
- `perception/replay_hud.py`
- `scripts/measure_replay_hud.py`, `scripts/replay_hud_validate.py`, `scripts/replay_hud_run.py`
- tests in `tests/test_replay_hud.py`

**Evidence** (numbers and hashes only, no footage): `docs/evidence/replay-hud-20260923/`.

## 1. Geometry: the replay HUD is James's first-person M&K HUD, with the ability columns in the player's own order

**Method** (`scripts/measure_replay_hud.py`, output `layout.json`):
- A median image of the bottom HUD strip cancels the moving world and keeps the fixed HUD. One median is taken over
  150 clean DayMR keyframes (POV bar on B5, timeline down). Another is taken over 150 of James's first-person review
  frames (1280×720, upscaled ×2).
- Each element of the replay median is searched for in James's median over shifts and scales 0.95-1.05.
- The frames used and their sha256 are listed in `layout.json`.

| Element | Shift (px at 2560×1440) | Scale | Score |
|---|---|---|---|
| Ammo box (webs) | −0.5, 0.0 | 0.995 | 0.978 |
| HP text | 0.0, −0.5 | 0.99 | 0.962 |
| HP bar | −0.5, 0.0 | 0.995 | 0.951 |
| Swing icon (column 2) | 0.0, +0.5 | 0.98 | 0.983 |
| Get Over Here! icon (replay column 3 → James column 4) | +5.5, −0.5 | 0.99 | 0.973 |
| Amazing Combo icon (replay column 4 → James column 3) | −5.5, −0.5 | 0.99 | 0.987 |

**The column underline bars are pixel-identical** in both medians (row 1357):

| Bars | x (px) | Centre (fraction of width) |
|---|---|---|
| Team-up, split by a chevron | 1880-1911 and 1935-1966 | 0.7512 |
| Columns 2, 3, 4 | 1993-2077, 2095-2179, 2197-2280 | 0.7949, 0.8348, 0.8744 |

**Findings:**
1. **`hud.MK`'s regions apply to the replay unchanged.** Every element sits within 0.5 px and 1 % scale of James's
   first-person HUD (the 1280-wide reference limits this to about ±1 px). The intake's reads on this replay agree:
   0 wrong countdowns in 184 slot checks.
2. **The ability columns follow the player's bindings.** Read off the printed prompts:
   - DayMR: C team-up, LSHIFT swing, **R Get Over Here! (arrow), F Amazing Combo (fist, 2-charge badge)**;
   - James: C, LSHIFT, **E Amazing Combo, F Get Over Here!**.

   `hud.MK.slot_cx` names column 3 `get_over_here` and column 4 `uppercut`, which is DayMR's order. On James's HUD
   those two names are swapped, and `hud._read_ability` applies its charge logic by name. So the column order has to
   be known per source (`identify_order`, §2).
   - The ±5.5 px icon residuals above are not a geometry difference.
   - `SLOT_CX["uppercut"]` = 0.8723 sits **5.4 px left** of its column's bar centre (0.8744) on both sources, so the
     constants' 3-4 pitch is short. This is inside the readers' icon window (±0.0165 = 42 px), so it was left
     unchanged.
3. **What the medians do not share is content, not position.** DayMR's team-up is a different ability, a radial burst,
   against James's rune icon. His ult shows a charge percentage while James's is full. So the whole-row and ult
   windows register at scores 0.56 and 0.65 by content.

**For other lanes:** `policy/range_bc/hudparity.py`'s `MK_AT` already maps James's swap for the fit. Any other reader of
James's M&K sessions through `hud.MK` needs the same mapping, and `hud.slot_mapping` finds it.

## 2. The wrapper: map, then read with the existing readers, or abstain

`perception/replay_hud.py` wraps `perception/hud.py` without modifying it.

- **`layout_for(order)`:** `hud.MK`, with each ability name mapped to its column on this source.
- **`identify_order(frames)`:** the column order, settled once per source by two independent votes over columns 3
  and 4.
  - **Icons:** `hud.identify_slot`, the same templates and floor as `hud.slot_mapping`.
  - **Charge badges:** only Amazing Combo carries one. It needs at least 10 badge reads, with at most 2 % stray reads
    in the other column.
  - Both must agree, or it abstains, and the caller must declare the order.
  - Results: replay icons `[get_over_here, uppercut]`, badges 0/103 → DayMR's order. James: icons
    `[uppercut, get_over_here]`, badges 126/0 → James's order.
- **`abstain_reason`:** every row of a frame is `unknown`, with the reason, when:
  - **the replay timeline is up.** It is found from the viewer's own controls: the white "N" key cap of "Press N to
    Show" is dark, and the "- + X1" speed controls are lit. Against the intake's template labels on all 1013
    keyframes: 63/63 found, and 0 false detections on DayMR's POV (the 14 elsewhere are menu and range frames). With
    the timeline up, the readers gave confidently wrong ability and ult values (intake §3); these frames now abstain.
    A frame where neither marker decides also abstains;
  - **the viewer is not following the requested roster slot**, read from the yellow POV bar under the portrait;
  - **no HUD is drawn** (hp and bar both unread), or **hp reads 0** (the dead camera keeps the HUD at 0/250).
- **Confidence:** a read field carries its measured precision on the intake's 47 hand-labelled clean DayMR keyframes.
  This is in-sample and small n:
  - countdowns 1.0 (182/182);
  - team-up ready 41/43 (the cooling-tile case, intake §3);
  - Amazing Combo ready 35/36 (the locked-icon case);
  - the others 1.0.
  - An `unknown` row has confidence 0.

## 3. Cast events

**The logic** (`cast_events(rows, cooldowns, min_run)`):
- **Cooldown abilities** (team-up, Get Over Here!): a cast is a group of countdown reads whose windows for the
  cooldown's start still intersect.
  - The countdown shows **ceil(remaining seconds)**: read N at time t, the start lies in `[t − (D − N) − 1, t − (D − N))`,
    widened by 0.02 s for one frame of step jitter.
  - **"Not ready" without a numeral is not a cast.** On 051828 the HUD greys the other abilities for 0.2-0.8 s around
    each Amazing Combo.
  - A flicker between countdown reads doesn't split a cast.
  - **Flagged:** windows that cannot fit together, a numeral above the duration, or a later cast implying an earlier
    start. A flagged cast falls back to the plain transition interval.
  - With no duration known, the transition interval is used: the last read without a countdown, to the first with one.
- **Charges** (swing 3, Amazing Combo 2) **and ammo** (Web Cluster 5): a count that drops between two runs is that
  many casts in the interval. It's a lower bound: a charge regained in the same interval hides a cast.
- **Ult:** ready → charging.
- **Unknown reads never count as "no cast".**
  - `coverage` lists the spans between reads closer together than the ability's hide time (its cooldown or recharge).
    Only there does no event mean no cast.
  - On 2.08 s keyframes, Web Cluster ammo (2 s recharge) has **no** coverage.
- **`min_run`** drops runs shorter than N frames (the ready read flickers for 1-3 frames at 120 fps). It is 1 on sparse
  keyframes.

### Validation on a known-input source: James's 051828, 20 s under the decode gate

**The run** (`scripts/replay_hud_validate.py` → `validation-051828.json`):
- Logger time 29.54-51.03 s, 2580 frames at 120 fps.
- Only the HUD strip (rows 1180-1440) was decoded: 4 threads, low priority, free memory > 5 GB and no other ffmpeg.
- Frame times come through intake's independently anchored frame references (muxer offset 21 ms, verified).
- Every frame was read in James's column order, with `min_run` = 3, and the events matched against the input log.

**Bindings:**

| Key | Ability |
|---|---|
| C | team-up |
| E | Amazing Combo |
| F | Get Over Here! |
| RMB | Web Cluster |
| Shift / Caps Lock | swing |

**Results:**

| Ability | Presses | HUD events | Press → HUD, per event | Notes |
|---|---|---|---|---|
| Web Cluster (ammo −1) | 12 | 9 events, 10 presses | +0.085 … +0.107 s (single-frame intervals) | 2 presses fell where the ammo digit was unread for 0.2-0.5 s: abstained, not missed |
| Amazing Combo (charges −1) | 3 | 3 | +0.15 … +0.47 s | |
| Get Over Here! (countdown) | 1 | 1 | cooldown start **+0.90 … +0.94 s** after the press (±0.02 s) | the HUD kept showing "ready" until the first numeral, 1.87 s after the press |
| Team-up (countdown) | 2 | 1 | cooldown start −0.02 … +0.03 s | the second C came during the cooldown and is correctly not a cast |
| Swing (charges −1) | 61 key-downs | 6 | +0.01 … +0.27 s | weak: the key-downs are a held key's auto-repeat, so most are not casts |
| Ult | 0 | 0 | | none in the window |

**No HUD event lacks a press.** Before the fixes, dense reading found about 20 false team-up and Get Over Here! casts:
greyed "not ready" states and 1-frame flicker. The rules above removed all of them.

**The display rule is verified:**
- Get Over Here!'s numerals step down exactly 1.000 s apart (8 → 7 at 43.44 s, …, 1 → ready at 50.43 s), and the icon
  turns ready 8.00 s after the implied start. That fits ceil(remaining) with D = 8.
- James's team-up measures **D = 10 s** from its 10 → 9 step. DayMR's radial-burst team-up is Symbiote Bond, 15 s by
  the kit; on the replay, 26 of its 27 casts give intersecting windows under 15 s (one flagged), weak support.

**Precision:**
- **Dense video** (120 fps): cooldown start ±0.02 s; charge and ammo drops to one frame (8.3 ms).
- **This replay's keyframes** (2.08 s apart): cooldown start median ±0.31 s (team-up) and ±0.40 s (Get Over Here!).
  Charges, ammo and ult are bracketed ±1.04 s (±3.1 s for the ult).

**What a HUD event means:**
- It is **when the game started the cooldown or took the charge**, not the key press.
- For James's source, the measured offsets (per ability, in the table above) turn one into the other: Web Cluster
  about +0.10 s, team-up about 0 s, Amazing Combo about +0.3-0.5 s.
- Get Over Here!'s +0.92 s is one sample. It probably depends on projectile travel (80 m/s) and the pull resolving.
- **Not the same for DayMR:** these offsets are James's (his setup, latency and play). A replay adds its own render
  path, so it needs its own check: DayMR's HUD in James's replay of himself, as the brief plans.

### This replay (`scripts/replay_hud_run.py` → `data/replay-hud/daymr-20260923-004325/`)

**Read:** 1013 keyframes. 463 read; the rest abstained:

| Reason | Frames |
|---|---|
| Not following B5 (menus, Team A POV) | 366 |
| Dead | 78 |
| Timeline up | 77 |
| Timeline state unreadable | 24 |
| Reader abstained | 28 |
| No HUD drawn | 4 |

**Casts:**

| Ability | Casts | Basis | Median precision |
|---|---|---|---|
| Get Over Here! | 56 | countdown | ±0.40 s |
| Team-up | 27 | 26 countdown, 1 flagged | ±0.31 s |
| Amazing Combo | 58 | charge drops | ±1.04 s |
| Swing | 116 | charge drops | ±1.04 s |
| Web Cluster | 124 | lower bound; no coverage at this spacing | ±1.04 s |
| Ult | 6 | transition | ±3.1 s |

**Coverage** (where no event means no cast): about 1096 s for team-up, 871 s for Get Over Here!, and about 900 s for
swing and Amazing Combo charges.

**A denser read** of DayMR's HUD strip (60-120 fps over his alive stretches, under the decode gate) would bring the
transitions to one frame, and it needs no model.

## 4. Output contract

**Per-frame table** (`rows.jsonl`): one row per (frame, field):

| Column | Values |
|---|---|
| `t` | the source's clock |
| `ability` | `teamup`, `swing`, `get_over_here`, `uppercut`, `swing.charges`, `uppercut.charges`, `web_cluster.ammo`, `ult` |
| `state` | `ready`, `cooldown`, `not_ready`, `count`, `charging`, `unknown` |
| `numeral` | the countdown seconds or the count, else null |
| `confidence` | the measured precision, or 0 when unknown |
| `reason` | why unknown |

**Event list** (`events.json`):
- **Events:** `t` (interval midpoint), `t_lo`, `t_hi`, `precision` = half the interval, `ability`, `count` (a lower
  bound for charge and ammo drops), and `basis` (`countdown` or `transition`).
- **Also:** `coverage` per ability, `flags`, the identified `order` with its evidence, and a summary.
- **An event claims a cast in (t_lo, t_hi].** Absence of an event claims nothing outside `coverage`.

## 5. What the replay HUD cannot say (the learned IDM's job)

- **Aim and target:** where the crosshair was, and which enemy a Get Over Here! or Web Cluster was aimed at.
- **Swing:** hold and release timing, direction, and Simple Swing (Caps Lock) versus Web-Swing (Shift). Both spend a
  swing charge.
- **Movement:** walking, jumping, Thwip and Flip, wall crawl, and the camera.
- **Melee (Spider-Power) hits:** the HUD has no counter or cooldown for them.
- **A cast whose resource returns before the next read frame:** any Web Cluster shot between keyframes; any charge
  regained in the same interval.
- **A key press that did not cast** (no charge, on cooldown, locked): the HUD shows only effects. James's second C in
  the validation window is an example.
- **Which team-up the icon is,** beyond identifying it per segment. Its duration must be supplied per source.

## Open

1. **The validation is one 20 s window,** with small n per ability and no ult. Swing matching is weak, because the
   presses are a held key's auto-repeat.
2. **Precision on this replay is set by keyframe spacing.** A 60-120 fps HUD-strip decode of DayMR's alive stretches is
   the next step, under the decode gate.
3. **Press offsets for replay sources** need James's replay of himself (planned in the brief).
4. **The team-up durations are per source:** 10 s for James, measured; 15 s for DayMR's Symbiote Bond, from the kit.
   The team-up's "ready while cooling" misread (intake §3) no longer creates casts, since casts need numerals, but it
   still affects the `ready` rows.

## 6. Full-rate pass over the DayMR replay, and the first review's five items (2026-09-23 evening)

### The pass (`scripts/replay_hud_full.py`)

**Method.** Every frame of the match is read at 120 fps: file time 464.938-2062.887 s, 54 windows of 30 s, **191,752
frames**.
- ffmpeg streams only the POV-bar band and the HUD strip, raw, into `read_frame` (4 worker processes). Nothing
  decoded touches the disk.
- **The gate:**
  - it is checked before each window: free memory above 5 GB, and no other ffmpeg or ffprobe;
  - 4 threads, and the process lowers itself to below-normal priority (inherited by ffmpeg and the workers);
  - at most 48 frames are in flight;
  - it stops under 4 GB free and resumes later.
  The run paused twice for the intake lane's decoders and resumed.
- **Speed:** about 30 s of wall time per 30 s window.

**Outputs** (`data/demos/replays/daymr-20260923-004325/hud/`, 28 MB; derived from third-party footage, so not
committed):
- `rows-<t0>.jsonl.gz`: the per-frame table;
- `events.json`: events, coverage, press-time coverage, flags and the summary;
- `progress.json`: per window, the file's sha256, frames, first and last PTS, free memory, and the reader's sha256
  at read time;
- `manifest.json`: the sha256 of every output and of the tool, the reader and `hud.py`, plus the original's recorded
  sha256.

**Reader versions:**
- The rows were read by `replay_hud.py` `6503b74b…`; the events were computed by `30921c0c…`.
- The changes in between touch only `cast_events`, `identify_order`, `press_coverage` and the `Event` fields, not
  `read_frame` or the abstention checks.
- The older bytes were not kept, so this is stated, not proven by hash.

**Withheld share** (per frame, reason of the first field):

| Frames | Share | Reason |
|---|---|---|
| 108,058 | 56.4 % | read |
| 7,435 | 3.9 % | frame read, but the team-up field abstained |
| 39,890 | 20.8 % | viewer not following B5 (menus, Team A POV) |
| 19,466 | 10.2 % | dead (hp 0) |
| 11,204 | 5.8 % | replay timeline up |
| 4,936 | 2.6 % | timeline state unreadable |
| 763 | 0.4 % | no HUD drawn |

**Casts** (flagged stretches excluded):

| Ability | Casts | Basis | Precision: median | p90 |
|---|---|---|---|---|
| Web Cluster | 267 | ammo drops | ±0.0045 s | ±0.10 s |
| Swing | 164 | charge drops | ±0.004 s | ±0.075 s |
| Amazing Combo | 76 | charge drops | ±0.0045 s | ±0.125 s |
| Get Over Here! | 60 | countdown, cooldown start | ±0.020 s | ±0.025 s |
| Team-up (Symbiote Bond, 15 s) | 22 | countdown, cooldown start | ±0.015 s | ±0.47 s |
| Ult | 9 | ready → charging | ±0.0045 s | ±1.6 s |

The median precision is one frame. The p90 tails are transitions bridged across unknown reads. Against the keyframe
pass, where most precisions were ±1.04 s: Web Cluster 124 → 267 and Amazing Combo 58 → 76, because dense reads see
drops a regen hid at 2 s spacing.

**Two fixes found on this pass,** both tested:
- **A spike filter.** A countdown run whose numeral jumps by more than 1 from both neighbouring runs (within 2 s),
  while they agree, is a misread and is dropped: 188 frames, including a "3" for 7 frames between 13s.
- **A physical guard.** Two countdowns of a single-charge ability closer than its cooldown are merged into one cast
  and flagged.
- **Before these:** 82 "team-up casts" were counted; the physical ceiling is about 60 on 15 min alive. After: **22**
  (0 pairs closer than 15 s) and **60** Get Over Here! (0 closer than 8 s).

**Flagged stretches:** 9 team-up (a later countdown implying an earlier start). They are **listed and not counted**:
basis `flagged` is not a claimed cast.

### Review item 1: charge and ammo coverage only at the maximum

**The rule:** a no-event span is a valid negative only while the count stays at its maximum (swing 3, Amazing Combo 2,
Web Cluster 5). Below the maximum a regen is in flight, and a cast plus a regen can cancel between reads.

| Coverage (DayMR) | Before, all spans | Keyframes, max-count only | 120 fps, max-count only |
|---|---|---|---|
| Swing | 896 s | 104 s | **161 s** |
| Amazing Combo | 910 s | 477 s | **586 s** |
| Web Cluster | – | 0 s | **398 s** |

### Review item 2: HUD time is not press time

- **`press_coverage(coverage, lags)`:** a press at p first shows at p + lag, lag ∈ [lo, hi]. So a HUD span [a, b]
  with no event rules out only presses p ∈ [a − lo, b − hi]. Spans that shrink to nothing are dropped.
- **An ability without a measured lag gets no press-time coverage.** The module's default table is all `None`.
- `events.json` carries `press_coverage` from the pooled lags (item 3, used as the full observed [min, max]):

| Ability | Press-time coverage |
|---|---|
| Team-up | 138 s |
| Get Over Here! | 19 s (its lag spans 1.04-1.87 s) |
| Amazing Combo | 11 s |
| Web Cluster | 0.6 s (its range is widened by one 1.10 s outlier) |
| Swing | 0 s |
| Ult | 1171 s (n = 1: see below) |

- **Provisional.** These are James's lags, not DayMR's, with the n below.

### Review item 3: press lags on more of James's footage

Four 20 s windows (`validation-*.json`, `press-lags.json`):
- 051828 at 30.3, 133.8 and 78.3 s;
- 200129 at 1003.5 s (admitted since, so intake's anchor applies; 0 ms residual on every frame in all four windows).

| Ability | n | Press → first HUD evidence, min / median / max | Press → cooldown start |
|---|---|---|---|
| Web Cluster | 35 | 0.096 / 0.104 / 1.10 s | |
| Amazing Combo | 12 | 0.318 / 0.324 / 0.469 s | |
| Swing | 12 | 0.008 / 0.319 / 1.56 s | |
| Team-up | 6 | 0.260 / 0.316 / 1.68 s | **0.002 / 0.004 / 0.010 s** |
| Get Over Here! | 5 | 1.04 / 1.70 / 1.87 s | 0.63 / 0.90 / 0.96 s |
| Ult | 1 | 0.0085 s | |

**Excluded or unmatched:**
- **Excluded:** events at a window's edge (the cast came before it) and flagged stretches: team-up 2, Get Over Here! 1.
- **After those exclusions, every HUD event matched a press** (0 unmatched events).
- **Presses that didn't cast:** swing 91 (a held key's auto-repeat), Web Cluster 13 (ammo read 0 at those presses),
  team-up 8 (pressed during the cooldown), Get Over Here! 1, Amazing Combo 1.

**What this supports:**
- Team-up and Get Over Here! events are best placed at the **cooldown start**. For the team-up that is within 10 ms of
  the press (n = 6).
- Web Cluster and Amazing Combo lags are tight in the middle, with a few long tails: a press whose drop came from a
  later press, or a drop seen late through unread frames.
- Swing and ult are too thin or too noisy to call label precision.

### Review items 4 and 5: every column verified; the follow filter in the module

- **`identify_order(frames, source, follow)`** now filters itself: on a replay it counts only frames following
  `follow` with the timeline down, and on any source only frames with a HUD. It verifies every column:
  - team-up never another ability and never badged;
  - swing's icon and badge;
  - columns 3 and 4 by icons and badges, which must agree.
- **DayMR:** icons `[teamup, swing, get_over_here, uppercut]`, badges `[0, 240, 0, 249]`.
- **Tests:** each column's failure, and frames of another POV not voting.

## 7. The first replay-source step table (DayMR), for the fit lane

**What it is.** `scripts/replay_steps.py` turns §6's outputs into a `rivals-range-steps-v1` table with
`source_kind: "replay"`, under the fit lane's contract (`policy/range_bc/steps.py`, end-to-end-fit.md "Replay labels").
- Table: `data/demos/replays/daymr-20260923-004325/steps/20260923T054325-507Z-33696-4.jsonl`, sha256 `4180dd6d…`.
- `build.json` holds every input's sha256 and the counts.
- Derived from third-party footage, so it stays under `data/`.

**Clock and frames.**
- Anchors are 33.3 ms on the capture's composition clock, taken from the logger's `frames.csv` for the capture
  session `20260923T054325-507Z-33696-4`, with the OBS profile's 21 ms muxer offset.
- **All 191,752 reader frames map** to a logged packet: max residual 0.33 ms, 0 unmapped.
- `frame_index` is the packet's presentation-order rank.

**Spans.** A frame is in only when all of these hold:
- the reader read it: not another POV, timeline, dead or no HUD;
- the route map logs its second on target with the timeline hidden;
- it lies outside the duplicated setup footage and the operator pause.

**Short misreads are forgiven:**
- a follow-bar miss of at most 3 s inside on-target seconds (the route map's own hold rule): 3,217 frames;
- an hp-0 read of at most 0.25 s between alive reads: 209 frames.

**Runs** break at every excluded frame, every capture gap and every seek. The result: **74 runs, 29,561 rows, 985 s**,
out of 118,452 included frames.

**Labels:**
- **Cast onsets** as `press`, for team-up, Get Over Here!, Amazing Combo, Web Cluster and ult. The press time is the
  HUD time minus the median press lag from `press-lags.json`: for team-up and Get Over Here! from the cooldown start,
  for the others from the first HUD evidence. It goes in the step holding that time.
- **The positive's uncertainty:** every other step inside the HUD interval widened by the lag's min..max is null, and so
  is every step near a flagged stretch.
- **Negatives** (0) only where a step lies wholly inside the ability's press-time coverage. Everything else is null.
- **Left null everywhere:**
  - Web-Swing and Simple Swing: a charge drop doesn't tell them apart;
  - holds, releases, movement, jump, melee, spider_power and goh_targeting;
  - camera.
- **The camera hook:** `fill_camera()` fills `yaw_deg`/`pitch_deg` from `perception/camera_motion.py` Step records.
  It sums non-abstaining pairs that tile the step, flips pitch to down-positive, and flags steps over the executor's
  per-step caps. It is not applied yet, because the camera lane's bytes are in final check.

| Action | press = 1 | press = 0 | null |
|---|---|---|---|
| web_cluster | 263 | 2 | 29,296 |
| amazing_combo | 74 | 90 | 29,397 |
| get_over_here | 60 | 335 | 29,166 |
| team_up | 22 | 344 | 29,195 |
| ultimate | 8 | 608 | 28,945 |

**Every non-flagged cast lands in a row** except 2 Amazing Combo and 1 ult, whose estimated press falls outside the
spans.

**Header:**
- `expert_context`: player DayMR; the match (Competitive Convoy, Hellfire Gala: Arakko, 2026-09-22 11:30);
  `viewer_fov_assumption: "viewer, unverified"`; the replay source.
- `calibration`: `replay_degrees`, with label sources stating the camera hook and "movement not labelled".
- `split: "replay"` (lead decision): a fourth split that `policy/range_bc/steps.py` refuses in every cohort unless
  `allow_replay` is passed, which is reserved for a pre-registered arm after the IDM trust gates. Replay rows are never
  train, val or test. (The first build wrote "train"; it is superseded.)

**Checks** (`tests/test_replay_steps.py`, 12 passed with the execution and perception groups):
- It loads through `steps.load` with intake's denylist.
- Movement, holds, releases and camera are unknown on every row.
- The known casts are exactly the counts in `build.json`.
- **Withheld spans are absent:** no row's frame is withheld (bar the forgiven misreads), off target, or in an excluded
  span.
- **The fit lane's own zero-gradient check** (its fake cache, `Batches` and loss) passes on the real run with the most
  known labels:
  - no movement or camera mask on any window;
  - exactly zero gradient on movement and camera;
  - non-zero gradient on the known cast labels.

**Caveats:**
- **Press offsets are James's lags** (n in §6), applied to DayMR. The label is "a cast began here", placed by those
  lags.
- **A 2-count ammo drop** (4 events) gives one positive: onsets are 0/1 flags.
- **Web Cluster has almost no negatives** (2), because its press-time coverage is 0.6 s: one outlier widens its lag
  range to 1.1 s.

## 8. Round-2 and step-table review fixes; one-reader pass; the rebuilt table (2026-09-23 night)

This section supersedes the §6 coverage and the §7 counts. The §6 cast counts stand.

**Reader versions (round 2, P3).**
- The §6 rows were read by two unkept readers, 6503b74b and 2da754bd.
- 6503b74b's rows equal the landed 30921c0c's rows on 3 windows: 86,400 rows, 0 differing.
- 2da754bd could not be checked. Both are superseded (the old folders are kept as `hud.v1-mixed-readers/` and
  `hud.v2-aborted-30921c0c/`).
- The fresh pass read all 54 windows with one reader, `perception/replay_hud.py` 0397e837. This reader is the landed
  logic plus the hp row. `progress.json` pins it, and the runner refuses to resume with other bytes.
- The finish step (events and coverage) ran on 40d4f968. That version changes only `floored_lag` (the clamp below).
  `manifest.json` records both hashes.
- The pass reproduces the §6 frame reasons and cast counts: swing 164, web 267, GOH 60, AC 76, team-up 22, ult 9.
  Separately, 9 team-up stretches are flagged; they are listed, never counted.

**Press coverage (P1, P2).**
- `press_coverage(coverage, events, lags)` merges adjacent read pairs into contiguous stretches. It cuts them at every
  event of the ability (flagged included), then shrinks each stretch once by the lag.
- The lag is floored by `floored_lag`:
  - with n < 3, the range is at least median ± 0.5 s;
  - any range is at least two frames wide;
  - the lower bound is clamped at 0, because a press cannot follow its own HUD evidence.
- The ult's n = 1 lag becomes [0, 0.51] s. A pair that straddles its own cast can no longer claim "no press".

**Coverage walls (step-table review R3).** Coverage never crosses:
- a withheld frame (other POV, dead, timeline, no HUD, order unknown);
- an operator seek or an EXCLUDE span;
- a read gap over 0.25 s.

Press-time coverage in seconds: team-up 607, GOH 618, ult 841, swing 106, AC 535, web 271.

**Transition window.** Every cast's press window is [t_lo − Lmax, t_hi − Lmin] (R1), for every basis.

**Step-table rules (R1, R2).**
- A cast's whole press window is null.
- A step is 1 only if a placeable window lies inside that one step.
- A step is 0 only if it overlaps no window and lies wholly inside press-time coverage.
- Deaths: an hp-0 cluster (gaps ≤ 1 s, ≥ 30 frames), widened over every adjacent frame not read alive (hp > 0 read),
  produces no rows. An hp-0 blip of ≤ 0.25 s is forgiven only between frames read alive.
- Result: 21 death spans; 55,908 dead frames excluded; 2,711 follow-blip frames forgiven; 116,565 of 191,752 frames
  included; 29,121 rows in 24 runs (970.7 s).

| action | 1 | 0 | null | casts (events) | unplaceable |
|---|---|---|---|---|---|
| team_up | 1 | 17,819 | 11,301 | 22 | 21 |
| get_over_here | 0 | 17,431 | 11,690 | 60 | 60 |
| amazing_combo | 0 | 15,458 | 13,663 | 76 | 76 |
| web_cluster | 0 | 7,912 | 21,209 | 263 | 263 |
| ultimate | 0 | 24,892 | 4,229 | 9 | 9 |

**Why there are almost no positives.** James's measured lag spreads are 0.15–1.6 s wide (the table's step is
33 ms), so no press window fits in one step. The one 1 is a team-up countdown cast: its cooldown-start lag is
[0, 14] ms and its reads are 8 ms apart.

This table is negatives-and-nulls: good for "no press here", useless for "press here". Positives need either tighter
lags (DayMR's own, or more samples), or a contract change that labels a window rather than a step. That is the fit
lane's decision.

**Transcode.** The lead's run of `2026-09-23 12-15-33.mkv` was skipped. The tool's own check refused: "obs64.exe
running" (the game was closed).

## 9. Press-label contract for the replay table (lead decision, replay-steps-3)

This supersedes the §8 rule that a window inside one step is a 1.

**Rows inside a cast's feasible press window are unknown.** For every step that overlaps
[t_lo − Lmax, t_hi − Lmin] (floored lags):
- press is null for that cast's action;
- it is never a 0;
- it is never a single-step 1.

The table holds no 1 for any action. Negatives remain only on steps that overlap no window and lie wholly inside the
ability's max-count press-time coverage (§8).

**The windows file.** The windows go to `steps/<capture>.press-windows.json` (format
`rivals-replay-press-windows-v1`). The table header and `build.json` both hash-pin it. It has one record per cast,
plus the 9 flagged team-up stretches. Each record carries:
- `action` and the HUD `ability`;
- `basis` and `count`;
- `cast`: false for a flagged stretch, where no cast is established;
- `lag_measured`;
- the window as `lo_s`/`hi_s` (capture file seconds) and `lo_ns`/`hi_ns` (the table's anchor clock);
- `evidence_s`: the HUD reads [t_lo, t_hi];
- `rows`: the first and last table row the window overlaps;
- `complete`: the overlapped rows are one run's consecutive steps covering the whole window.

**Use.** A record with `cast` true says at least one press of `action` lies in the window. That fits a window-level
loss ("at least one press in the window"), which is a pre-registered arm only. The arm should use complete records
only: an incomplete window's press may fall on rows that do not exist.

**Counts** (table `3e1acef8`):

| action | windows (casts) | complete | 0 | null |
|---|---|---|---|---|
| team_up | 22 (+9 flagged) | 22 | 17,819 | 11,302 |
| get_over_here | 60 | 60 | 17,431 | 11,690 |
| amazing_combo | 76 | 74 | 15,458 | 13,663 |
| web_cluster | 263 | 262 | 7,912 | 21,209 |
| ultimate | 9 | 8 | 24,892 | 4,229 |

Web Cluster's 263 windows hold 267 casts: 4 windows are 2-count ammo drops (`count` 2).

**Tests** (`tests/test_replay_steps.py`):
- `test_even_a_window_inside_one_step_is_null_never_a_1`;
- `test_a_window_record_is_complete_only_over_one_runs_consecutive_rows` (a missing row, a run break, a late start);
- `test_the_press_windows_file_names_every_cast_and_its_rows_are_unknown` (on the real table: hash pins, row
  spans, nulls, completeness);
- `test_known_casts_are_the_ones_counted` (no 1 anywhere; one window per cast).

The fit lane's "Replay labels" section in `docs/lanes/end-to-end-fit.md` is theirs to update.
