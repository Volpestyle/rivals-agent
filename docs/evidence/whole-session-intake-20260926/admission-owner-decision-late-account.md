# admission-owner decision request: the late take ran on another account whose Spider-Man profile differs

**Take:** `20260926T035932-508Z-63684-14` (22:59, 30.8 min, registered train). Your revised rule asked me to check
whether the saved settings record a sensitivity value. They do, and the answer changes the question.

## What the saved settings show

The game keeps one settings file per account under `…/Marvel/Saved/Saved/Config/<account id>/MarvelUserSetting.json`.
The intake (and my inventory) reads only **`1295996384`**, the campaign account whose 1036 (Spider-Man) controls equal
the 2026-09-22 receipt. Two accounts were written tonight:

| Account | File sha256 | Written (CDT) | 1036 sensitivity | 1036 mouse acceleration | 1036 vs the 09-22 receipt |
|---|---|---|---|---|---|
| `1295996384` (campaign; the intake's) | `3cb422eb…` | 23:37:39 | 1.89 / 1.89 | **on**, threshold 1.0, smoothing on, align on | equal (0 differences) |
| `1859995554` (33.8 KB, many heroes: very likely James's main) | `29133be3…` | 23:35:11 | **1.89 / 1.89** | **off**; smoothing and align keys absent | **29 differences** |

- **Sensitivity is recorded:** `MouseHorizontalSensitivity` and `MouseVerticalSensitivity` per hero.
- **On the main account,** Spider-Man is at 1.89/1.89, which fits "changing the mouse sens to match … (1.89)". Hero 0
  (the account default) is 3.83/3.67 with acceleration on, factor 1.22, threshold 15. Spider-Man's own entry overrides
  that.
- **Both files were written after the take ended** (23:30). They are later local state, not a recording-time attestation.
  `NoCDSaved` is 0 on both.

**Spider-Man's differences on the main account from the receipt (non-gamepad):**
- **Mouse acceleration off**, where the receipt has it on at threshold 1.0. Smoothing and align are unset, where the
  receipt has both on.
- **Action 16:** the receipt binds it explicitly to LeftShift (web swing in `BINDINGS`, `key:42`). On the main account its
  keyboard key is unset, so it falls to a default I can't read from the file.
- **Action 133** (Simple Swing): primary and secondary are swapped (MouseScrollUp primary, Caps Lock secondary). The keys
  are the same.
- **Actions 7, 15, 22, 36 and 143–148:** added, removed or remapped. Examples: 15 gains R; 22 = Tilde; 36 = B; the
  One–Four / Five–Six number-row slots shift.

So the recording-log line's "DPI and bindings unchanged" is **not what the main account's saved profile shows**. The
take's settings identity cannot be assumed to be `a8dea3ba…`. That identity has acceleration on, smoothing on and
the receipt's binding table. `load_cohort` refuses mixed identities by design.

## What is unaffected

- **The regime and gain checks you set** remain the right tests of cooldowns and sensitivity.
- **Acceleration:** the 030045 record found acceleration at factor 1.00 had no measurable effect. With acceleration off,
  the gain should equal the calibration if the sensitivity is 1.89. The gain check tests this directly.
- **Bindings for keys James actually pressed:**
  - Shift ×401: web swing, if action 16's default is still Shift.
  - Caps Lock ×1: the same key either way.
  - V ×1, Mouse 5 ×23: melee.
  - The number keys: not pressed.

  These can be checked on frames (Shift should produce web swings).

## Options

- **A. Hold the take.** Nothing further is built. It is 30.6 min, and a different account and profile.
- **B. Admit only under proven effective equivalence.** On top of your two conditions (regime normal across accepted
  spans; yaw gain equal to 0.0330738 within tolerance), add:
  - (c) every key or button James pressed in the take has the same meaning under the main profile. Shift must be shown
    to swing on the frames, and every other pressed key must be unchanged between the two tables.
  - Record the take's actual profile (the main account's file hash, acceleration off) in its own motor record. The
    step header keeps `a8dea3ba…` only if you rule that an equivalent-in-effect profile shares the identity. That is a
    contract question for you and the fit's owner, not mine.
- **C. Separate identity.** Build the take's own motor record and binding table from the main account's profile. It
  gets its own settings identity and stays out of the current cohort until the fit supports more than one identity.

**My recommendation is B if the gain and Shift checks pass, otherwise A.** James could also confirm which account ID is
his main one, and whether the earlier range takes were all on the campaign account (the intake's check assumes so).

## Done meanwhile (no decode)

- **The generic "closed Esc pair" code I had started for your first option B is reverted.**
  `agent/human_intake.py` and `intake_session.py` are back to final-23's bytes (LF `f94a7c37…`, `fe8e3f6b…`).
- **`MOTOR_STATEMENTS["2026-09-25"]`:** the late quote is now the `83c05f1` line (its first two sentences, verbatim),
  replacing the `0072df5` one. It resolves for both takes, and the tests pass (158 passed, 3 skipped).
  - The date-level `settings` and `bindings` strings still describe the afternoon takes. Whichever option you pick, the
    late take needs its own per-session source text. The entry has no per-session override yet, and adding one is a
    small change.
- **Nothing decoded.** The settings-change cut and the gain check wait for your answer here, and the decode waits for
  the game and OBS to close.
