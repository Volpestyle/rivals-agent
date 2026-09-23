# Review: the replay HUD reader (VUH-1306)

Reviewer `fit-review` (Claude Opus 5.5), 2026-09-23. Read-only.

**Read:**
- `perception/replay_hud.py` (`f88a34bf…`, matching the hand-back);
- `tests/test_replay_hud.py` (`c84aee3f…`);
- `docs/lanes/replay-hud.md` (`23b50d11…`) and `handoff/replay-hud.md`;
- `scripts/replay_hud_run.py` (the follow filter only).

**Ran:**
- **Tests.** `tests/test_replay_hud.py` in my own environment made from the lockfile (perception group):
  **26 passed**.
- **`perception/hud.py`** against HEAD, and a search for runtime patching.
- **A coverage check** on the tool's own DayMR output, `data/replay-hud/daymr-20260923-004325/rows.jsonl` and
  `events.json` (derived rows; no footage decoded).

**Not done:** no decode, no edits, no commits. 053616 not touched.

## Verdict: approve the reader as offline code. Fix `coverage` before anything uses it as negatives

- The per-frame reads, the abstentions and the cast *events* are sound.
- The `coverage` output, the part that licenses "no cast", overclaims in two ways:
  - for charged abilities, a regen can hide a cast (R1);
  - and it is in HUD time, not press time (R2).
- Coverage is exactly what the inverse-dynamics lane would use for negative labels.

## The four questions, settled

### 1. Is the binding-order mapping safe when DayMR's columns 3 and 4 are swapped relative to James's?

**Yes, for the swap it was built for.**
- `identify_order` needs two independent votes over columns 3 and 4 to agree:
  - hud's own icon templates, at hud's floor of 3 votes and 60% share;
  - the Amazing Combo charge badge, ≥ 10 reads while the other column stays ≤ 2%.
- Otherwise it abstains, and every row becomes `unknown` ("column order unknown").
- `layout_for` remaps the ability names to columns through `dataclasses.replace(hud.MK, slot_cx=…)`, so hud's by-name
  charge logic follows the ability, not the column.
- The run script identifies the order only on frames whose POV label is the requested follow.

**Two gaps (R4):**
- **Columns 1 and 2 are assumed, not verified.** `layout_for` requires `("teamup", "swing")` first but never checks
  their icons. A source whose first two columns differ (another expert's bindings) is read with the wrong ability
  names. Verify all four columns by icon, and abstain otherwise.
- **The follow filter lives in the script, not the library.** `identify_order(frames)` accepts any frames. In a match
  where both teams have a Spider-Man, frames of the enemy's POV (different bindings) could mix in. Take `follow` as a
  parameter and filter inside.

### 2. Can an abstention ever be read as "no cast"?

**Not directly.**
- `unknown` rows are dropped before runs are built, so they never create or suppress an event.
- For cooldown abilities, two known reads closer than the cooldown with no countdown between them do prove no cast.
  That logic is sound.

**But `coverage`, which the doc says is "where no event means no cast", overclaims in two places.**

**R1 (serious): for charges and ammo, a regen can hide a cast inside "coverage".**
- `coverage` for `swing.charges` and `uppercut.charges` is every pair of reads closer than the 6 s recharge.
- If the count is below its maximum, a recharge can complete *and* a cast can spend it between the two reads. The count
  is then equal at both ends: no event, but a cast happened.
- The lane doc says exactly this about events ("a lower bound: a charge regained in the same interval hides a cast",
  `replay-hud.md:107`). But `coverage` still counts those spans.
- **On DayMR's output:**

  | Ability | Coverage claimed | Both reads at maximum | Unsound share |
  |---|---|---|---|
  | Swing | 896 s | 104 s (at 3) | **88%** |
  | Amazing Combo | 910 s | 477 s (at 2) | **48%** |

- **Required:** for charged and ammo abilities, a span is covered only when both reads show the maximum count. Only
  then must a cast leave the second read lower. Re-state the doc's "about 900 s" as the corrected figures.

**R2 (serious for press-time labels): coverage is in HUD time.**
- Get Over Here!'s HUD "kept showing ready until the first numeral, 1.87 s after the press", and its cooldown starts
  about 0.92 s after the press (`replay-hud.md:140`).
- So two "ready" reads spanning the press are a covered span with no event, although the press is inside it.
- The event exists, but it is placed at the cooldown start.
- A consumer that turns coverage into press-time negatives (as an inverse-dynamics edge head would) labels a true press
  as "no cast".
- **Required:** the output contract says coverage and events are in HUD-change time. Any press-time use must drop
  `[t_lo − max_offset(ability), t_hi]` around every event from coverage.
- **For replay sources, where the offset is unknown until James's replay of himself is measured,** coverage within a few
  seconds before an event cannot license a press-time negative.

### 3. Are the offsets explained and stated as label precision?

**Partly explained, and stated honestly as HUD-time, James-specific numbers. They are not established as label
precision (R3).**
- **Web Cluster (+0.085 to +0.107 s):** the ammo digit decrements on the frame after the shot. Consistent across 9
  events, and not explained beyond that.
- **Amazing Combo (+0.15 to +0.47 s):** a 0.32 s spread over only 3 events. No mechanism is given. A charge taken at a
  point in the animation that depends on distance to the target is a likely one, and it is untested.
- **Get Over Here! (+0.90 to +0.94 s): one sample.** The doc's hypothesis (projectile travel at 80 m/s plus the pull
  resolving) implies a distance-dependent offset, which one sample cannot bound. `Cal.pull_s = 0.8` is consistent with
  it.
- **Team-up (about 0 s): one sample.**
- **The match claim is in-sample.** "Every HUD event matched a press within stated offsets" uses offsets read off the
  same 20 s window.

**Required:**
- Label the offsets "James, 051828, in-sample, n = 9 / 3 / 1 / 1".
- Validate them on a second, held-out window of James's play with Get Over Here! at several distances before they are
  used to convert HUD time to press time.
- Keep the event `precision` field described as HUD-time interval precision only, which the doc does (`:154-165`).

### 4. Does anything touch the pinned `hud.py` bytes?

**No.**
- `perception/hud.py`'s blob is `16b8530b…`, equal to `HEAD:perception/hud.py`, and the diff is empty.
- `replay_hud.py` uses `hud.read`, `hud.read_charges`, `hud.identify_slot` and `hud.MK`, and builds its layout with
  `dataclasses.replace`.
- There is no assignment to `hud` attributes and no monkeypatching of `perception.hud`, in the module, the scripts or
  the tests.
- The request-fit driver's perception pin (hud, outline, loop) is unaffected.

## Smaller findings

- **R5. Precision is keyed by ability, not column.**
  - The `PRECISION` values were measured on DayMR's order. But column 4 has the ult-glow occlusion guard, which
    abstains 64% of the time on James's genuine frames (fit lane's parity work). On James's order, Get Over Here! sits
    in column 4.
  - Precision-when-read may transfer, but coverage and abstention do not. Key `PRECISION` by (ability, column), or
    re-measure it per order.
- **R6. Default `hud.MK` swaps James's abilities.**
  - `hud.MK` names column 3 Get Over Here! and column 4 uppercut, which is DayMR's order.
  - Any `hud.read(frame, hud.MK)` on James's own frames swaps the two. That includes a HUD cross-check in the
    inverse-dynamics lane, or resource stratification in the fit.
  - The fit's `hudparity.MK_AT` and intake's per-session `slot-mapping.json` already handle it. Say so in `hud.py`'s
    lane doc, or give `hud` a `JAMES_MK` layout, so the next consumer does not fall into it.
  - This also corroborates the E/F binding question: James's E is the combo fist, F is Get Over Here!.

## What is sound

- **The geometry is measured, not assumed.** The replay HUD coincides with James's M&K HUD to the pixel (hashes in
  `layout.json`).
- **Frame abstention ordering.** The viewer's own controls detect the timeline (63/63, 0 false), then the POV bar, then
  no HUD, then dead at hp 0. Each is a reason on the row, never a zero.
- **"Not ready" without a numeral is not a cast.** The countdown-window intersection uses the verified ceil display rule
  (1.000 s steps, ready at 8.00 s). Numerals above the duration, disjoint windows and out-of-order starts are flagged,
  and flicker is filtered with `min_run`.
- **Charge and ammo drops are reported as lower bounds**, and Web Cluster gets no coverage at 2.08 s keyframes. Team-up
  duration is per source and never assumed.
- **Validation used intake's independently anchored frame times,** and James's second C, pressed during the cooldown, is
  correctly not a cast.
