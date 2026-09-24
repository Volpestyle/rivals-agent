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
