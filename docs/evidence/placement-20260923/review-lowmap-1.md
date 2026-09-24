# Review: `--lowmap` measurement mode (input-path review under AGENTS.md)

Reviewer `admission-review` (Claude Opus 5.5), 2026-09-23. The review is read-only: no pad was opened, no game input
sent, nothing committed.

**Bytes reviewed:**

- `scripts/place.py` `ebe97830`: working tree, +181/−6 against HEAD `d11dc634`
- `tests/test_place_lowmap.py` `8d550171`
- `docs/next-pc-session.md` `a076bb18`

**Context:** `agent/controller.py` `55730a7a` (clean), and `perception/camera_motion.py` (`Estimator.compare`,
`focal_for`).

**Tests:**

- `tests/test_place_lowmap.py`: **11 passed**, under a venv with cv2. In the shared `.venv` the whole module is
  *skipped* (no cv2), so run it with `--group perception`.
- `tests/test_place.py`: **92 passed**.

## Verdict: safe to run in James's session as written. Fix the file before any number reaches Cal

The input path is sound, and the session page is right. The judging step (`lowmap_fit`) has three gaps (L1-L3), and
the brief's physical-input kill switch doesn't exist (L4).

- **No gap sends input.** Each could let a wrong measurement say `ok`, or a not-ok file carry Cal-shaped numbers.
- **The file stores the raw rows,** so the fit can be re-judged after the session with corrected code. That is why
  none of these blocks step 5b.

## Answers

**1. No pad opens without the declaration: holds.**

- `--lowmap` shares the measurement branch. `check_measurement_declaration(a.declaration, "lowmap", …)` and
  `_open_game` run before `_pad_side()` is imported and before `Live(...)` exists.
- The declaration's `modes` must include `lowmap` and name only `MEASURE_MODES`.
- `pad_settings` must equal `LOWMAP_PAD_SETTINGS` exactly.
- `check_entry` binds the PID, the range entry, the window and a structured authorization for the mode.
- `test_main_lowmap_refuses_before_any_pad_opens` and `test_lowmap_needs_its_own_mode_and_the_pad_settings` cover
  this.
- **`pad_settings` is an attestation**, not read from the game. The page's step 3 (show the pad settings) is what
  backs it, and `lowmap_fit`'s top-rate check against Cal catches gross mismatches.

**2. Nothing but rx/ry is written: holds.**

- Every `lowmap` hold is `_hold(..., allowed=frozenset({key}))` with `key` either `rx` or `ry`, one axis per hold.
- `_hold` refuses any key outside the set before writing.
- `Live.send` merges into `self.sent`, which `release()` has just made neutral. So each write is one stick axis with
  everything else at 0.
- The prime is the reviewed `rx ±0.45` and nothing else.
- No button, trigger or left-stick path exists in the mode.
- The test asserts right-stick-only sends and a neutral end.

**3. Per-write kill switch: foreground and range proof hold; physical input does not exist (L4).**

- Each write is preceded by `proof(live.fresh())`: focus, the range HUD, no idle banner.
- `Live`'s own guard (`in_range and focused()`) is re-checked at commit, with a frame-age check, inside the pad lock.
- `still()` proves every measurement frame.
- A failed proof raises `Stopped`; `_hold`'s `finally` releases, and `main`'s `finally` closes `Live`. Ctrl-C is
  handled.
- **Nothing in `place.py` or `Live` detects physical keyboard or mouse input.** See L4.

**4. Overruns cannot compound into a sustained turn: holds.**

- **The overrun per hold is larger than the brief's +50 ms.** The last loop iteration starts before `end`, then runs
  `proof(fresh())` (up to `FRESH_S`, plus the HUD check), the send and a 50 ms sleep. So the overrun is roughly
  50-150 ms.
- **It still cannot compound:**
  - every hold ends in `live.release()`;
  - between holds there are only `still()` sleeps, with no writes;
  - the real-time lease (0.25 s) neutralises the pad if the loop stalls anywhere.
- **The worst net drift** is the sum of the forward/back overrun differences: at most about 1-2° per hold pair, over
  30 pairs. It is camera-only, and pitch is bounded by the game's clamp.
- **The rate uses the measured `held_s`,** not the nominal time. That `held_s` spans `t0..t1` around `_hold`, so it
  also includes the first proof before the first write: about 2-3 % on a 1.0 s hold and 5 % on 0.5 s. Minor: stamp
  the first send and the release instead.

**5. Abstention or a wrong sign makes the file not ok: holds, but not ok still carries Cal's fields (L3).**

These each give `ok: false` with a reason:

- an abstaining noise pair;
- any abstaining hold;
- a wrong sign above the still threshold;
- a mixed deflection;
- a non-monotone map;
- no movement up to the top deflection;
- a top rate more than 25 % off Cal.

The tests cover each case, and I reproduced abstention and wrong sign directly. A `Stopped` run writes
`{ok: false, why: "stopped: …"}` with no `cal`.

**6. The session page: order and times are right.**

- **Order:** step 5b runs in recording C after the settings check (step 3), and step 3 explicitly shows the pad
  settings.
- **Content:** the grid, the hold times and the directions (right then left; up then down) match the code.
- **Time:** my sum for 5b is about 1.6-2 min. That is 16 yaw pairs at about 3.15 s, 14 pitch pairs at about 2.15 s,
  the prime and its 5 s settle, and the rotation fits, against "~2 min".
- "James parks, lets go, and watches" is the right instruction, and the kill switch text is accurate.
- The "Without that review, skip 5b" line is satisfied by this review.

## Findings

**L1 (required before the numbers reach Cal): forward/back and repeat agreement is not checked.**

The only rate check is the top deflection against Cal, within 25 %.

- **Constructed:** every hold's forward rotation at 1.6× and back at 0.9× the true value gives **`ok: true`**, with a
  yaw top rate of 23.12 against 18.5.
- **Causes of such asymmetry:** a pitch hold that clamps, a hand on the mouse, or a disturbed settled frame.
- **Below the top deflection, nothing compares the holds at all.** A disturbed low deflection that still "moves"
  enters the map as a wrong point, which is exactly the low end K3 is about.
- **Required:** per deflection, the forward and back magnitudes, and the two repeats, must agree (for example within
  25 % or 0.5°, whichever is larger); otherwise the deflection is `mixed`.

**L2 (should fix): off-axis rotation is recorded but never judged.**

- **Constructed:** 15° off-axis on every hold still gives `ok: true`.
- **Required:** each hold's `off_axis_deg` must stay under a bound, for example the larger of 3× noise or 20 % of the
  on-axis value, so that a swapped or cross-coupled axis, or interference, shows up.

**L3 (should fix): a not-ok result still carries `cal.yaw_map`, `cal.pitch_map` and the deadzones.**

- Verified for both an abstained hold and a wrong sign. `main` also prints `cal` on a not-ok run.
- **The risk:** a reader who takes `cal` without `ok` gets a wrong Cal.
- **Required:** write `cal` only when `ok`, or name it `cal_candidate` when not ok, and leave `cal` out of the printed
  summary when not ok.

**L4 (the brief's "physical input" kill switch): not implemented anywhere.**

- **What exists:** focus, the range HUD and the idle banner.
- **Input safety needs no physical-input check.** James taking the mouse doesn't make the pad unsafe, and Alt-Tab
  still stops it.
- **Measurement integrity does.** A mouse nudge during a hold is added to the measured rotation, and only L1 and L2
  would catch it.
- **Cheapest fix, since 5b runs inside recording C:** before any lowmap file is used, require zero keyboard and mouse
  events in the Rivals Input Logger's `inputs.jsonl` over the run's window.
  - The run's window is the `declaration.json` to `result.json` times, or better, stamps written by `lowmap`.
  - Alternatively, add a `GetLastInputInfo` check to `proof`.
- **Either way, correct the brief and the page wording:** the kill switch is focus, the range HUD and the idle
  banner.

## Also noted

- **`Estimator` uses a fixed focal length,** pinned by a timed 360° turn at the September 23 FOV.
  - Degrees scale with that FOV, so a changed FOV would bias every rate.
  - The Cal cross-check catches only errors over 25 %.
  - Step 3 of the page should also show the FOV setting, if it is not already among the Controls pages.
- **Camera acceleration:** if the game ramps camera speed, a 0.5-1.0 s hold under-reads the steady rate. Cal's maps
  should say whether they were measured at comparable hold lengths.

## What is sound

- **One door to the pad,** with one axis per write, per-write proofs, the lease, release on every exit, and close on
  every exit.
- **The declaration gate runs before any pad code is imported.**
- **The raw rows and frames are kept,** so every judgement can be redone.
- **The page is accurate** and in the right order.
