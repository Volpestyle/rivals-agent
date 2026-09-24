# pilot-prep: casts and resources from the replay HUD (VUH-1306), first pass (offline, no commit)

The lane doc is `docs/lanes/replay-hud.md` (single writer: me). This note is the summary.

## The five deliverables

1. **Geometry.** The replay HUD is James's first-person M&K HUD **to the pixel**:
   - the ammo box, hp text and hp bar sit within 0.5 px and 1 % scale;
   - the column underline bars are pixel-identical;
   - the medians and frame hashes are in `docs/evidence/replay-hud-20260923/layout.json`.

   **Two findings:**
   - **Ability columns follow each player's bindings.** DayMR has R = Get Over Here! and F = Amazing Combo; James has
     E = Amazing Combo and F = Get Over Here!. So `hud.MK.slot_cx`'s names for columns 3 and 4 are DayMR's order and
     are swapped on James's HUD. The fit's `hudparity.MK_AT` already maps this; any other `hud.MK` reader of James's
     sessions needs it.
   - **`SLOT_CX["uppercut"]` sits 5.4 px left of its column centre.** This is harmless, inside the reader window, and
     left unchanged.
2. **The wrapper** (`perception/replay_hud.py`, `hud.py` untouched):
   - **`identify_order`:** hud's own icon templates plus charge badges, which must agree, or it abstains.
   - **Abstention:** for the replay timeline (template-free: 63/63 caught, 0 false on the followed POV), a POV other
     than the requested player, no HUD, or dead.
   - **Confidence** is each field's measured precision from the intake truth set.
3. **Cast events.**
   - **Countdown casts:** the cooldown start comes from intersecting each numeral's ceil window. The ceil rule is
     verified: 1.000 s steps, ready exactly 8.00 s after the start.
   - **Charge and ammo drops** are lower bounds. **Ult:** ready → charging.
   - **"Not ready" without a numeral is not a cast;** that removed about 20 false casts at 120 fps. Frame flicker is
     filtered with `min_run`.
   - **Validation on 20 s of 051828,** with a decode-gated HUD-strip decode and intake's anchored frame times.
     **Every HUD event matched a press**, with no false casts:

     | Ability | Match | Press → HUD change |
     |---|---|---|
     | Web Cluster | 10 of 12 presses (2 abstained) | +0.085 to +0.107 s |
     | Amazing Combo | 3 of 3 | +0.15 to +0.47 s |
     | Get Over Here! | 1 | cooldown start +0.90 to +0.94 s |
     | Team-up | 1 of 2 (the other was pressed during the cooldown) | -0.02 to +0.03 s |

   - **James's team-up measures 10 s.**
4. **Output contract:** `rows.jsonl` (t, ability, state, numeral, confidence, reason) and `events.json` (t, t_lo, t_hi,
   precision, ability, count, basis), plus per-ability `coverage`: only inside coverage does "no event" mean "no
   cast". **DayMR's replay:**
   - Get Over Here! ×56 from countdowns (±0.40 s) and team-up ×27 (±0.31 s);
   - swing ×116, Amazing Combo ×58 and Web Cluster ×124 (lower bound), each ±1.04 s at 2.08 s keyframes;
   - ult ×6.

   The files are in `data/replay-hud/daymr-20260923-004325/` (derived from third-party footage).
5. **What the HUD cannot say** is listed in the doc §5 and in `replay_hud.NOT_FROM_HUD`: aim and target, swing hold and
   direction and simple versus normal swing, movement, melee, casts hidden by regen between reads, presses that did
   not cast, and team-up identity.

## Open

- **One 20 s validation window,** with no ult.
- **Precision on DayMR is keyframe-bound.** A 60-120 fps HUD-strip decode of his alive stretches, under the gate, gives
  one-frame transitions.
- **Press offsets for replay sources** need James's replay of himself.
- **Team-up durations are per source.**

## Checks

- `tests/test_replay_hud.py`: **26 passed** (perception group). It uses synthetic rows, plus the replay keyframes and
  review frames when present.
- `test_hud`'s latency flake fails as on main.
- No trailing whitespace. Nothing committed.

## Bytes

| File | sha256 |
|---|---|
| `perception/replay_hud.py` | `f88a34bfa30909cf0846f471613237eef7a70ccb456e761a8af8871920acba1c` |
| `scripts/measure_replay_hud.py` | `805aae72019c5bfa996d5d37f009bc409136e0b2d7e2c0dfc1167d59d697ceb6` |
| `scripts/replay_hud_validate.py` | `9690fd9baf331f04a503a158c15374e9a9f2a317699217660b25ffc66212ae2b` |
| `scripts/replay_hud_run.py` | `da57a3228016cf47ca6e0fca01c797bf1d8e31535b0cbe7a87459390e29a95e6` |
| `tests/test_replay_hud.py` | `c84aee3f89d7a8bb32be6a79d32debf89a208d4ee559d260112409af691d9e40` |
| `docs/lanes/replay-hud.md` | `23b50d110acd051ced54dcc7cd63a732936465d45500f46c67f26c3d3e2c58d9` |
| `docs/evidence/replay-hud-20260923/layout.json` | `be02dc68899498414c49cfbb0ea9be4b847f7c0ec69e0e987da3529d8a01a8fc` |
| `docs/evidence/replay-hud-20260923/validation-051828.json` | `d5b509445d2007fa32aae90e33f85c3882ffd70b8fe14e9bee40e8488dd0fa6a` |

**Not for commit** (under gitignored `data/`):
- `data/replay-hud/051828-validation/` (the decoded HUD strips, James's own);
- `data/replay-hud/daymr-20260923-004325/` (derived from third-party footage);
- `data/demos/replays/daymr-20260923-004325/replay-hud/` (the median strips).
