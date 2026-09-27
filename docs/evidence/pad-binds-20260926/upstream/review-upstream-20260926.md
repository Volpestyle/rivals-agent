LAND WITH FIXES

# Review: l4_measure motion guard and full pad reports (VUH-1384), binds-review (Opus 5.5), 2026-09-26

This was a read-only, independent review. I made no edits, commits or game input, and I did not import vgamepad.

**What I verified before reviewing:**
- `HANDBACK.md` has sha256 `c4538ba5…`.
- HEAD is `5817015`.
- All six working-tree files match the handback's hash table: `agent/startup.py` `79745e0f…`, `scripts/l4_measure.py` `96dac938…`, `docs/pad-bindings.md` `05d93a72…`, `tests/test_watch_pad.py` `641a8a84…`, `tests/test_l4_motion.py` `5e0f74b0…`, `tests/test_l4_scripts_close.py` `e0f2cf3c…`.

**Tests (mine):** a private perception env had no vgamepad installed (`find_spec('vgamepad')` returned None). The handback's nine-file focused command gave **187 passed**.

## The four questions

- **Can the guard be bypassed or false-pass? No bypass. No false pass on a static view.**
  - **Period:** `period` calls `require_motion` unconditionally, before any recurrence matching, and raises before computing a result.
    - The stationary evidence retained from the sitting is refused (132 confident pairs, median shift 0.003 px).
    - A static *camera* can pass only if non-camera content produces a coherent ≥1 px horizontal shift in a majority of confident pairs. The design accepts that residual ("necessary, not proof").
    - The two-turn alias still passes, as the handback states.
  - **Maps:** every map sample now goes through `checked_shift`: forward pulses, return pulses, all three equal-pulse focal pairs, negative pitch returns and the new `yawleft` return.
    - A pulse passes only if phase-correlation motion (response ≥ 0.2, ≥ 1 px) **and** a template match (score ≥ 0.8, ≥ 2 px, off-axis less than half, same sign as the phase estimate) agree.
    - A static pair gives template displacement 0 and is refused.
- **Does a pad open before argument validation? No.**
  - The order is: argparse `choices`, the focal check, `dest.open("x")` (refuses an existing path), then `live_factory()`.
  - `watch_pad` is attached only after construction.
- **Does neutral-on-close still hold? Yes.**
  - Every refusal point comes after `still()` or `sample()`, both of which run with the pad neutral (`hold` releases in `finally`; `sample` ends with a neutral send).
  - `MotionRefused` goes through the existing `finally: live.close()`.
  - The failure record keeps `report_timing`, which includes the close report, because the observer wraps `update()` inside Live's actuator lock.
  - Observer errors only set `failed`. Real update errors still propagate (`test_watch_pad.py:70-90`).
- **Are the tests synthetic only? Yes.**
  - Textures come from seeded RNG. Pads are `SimpleNamespace` / `ReportPad` fakes.
  - `test_pad_bindings` stubs `vgamepad` in `sys.modules`.
  - Nothing reads the corpus.
  - `check_retained.py` (outside pytest) reads only the calibration sitting's `sample-bands.npz`.

## Findings

**1. Medium, must fix: `full_reports` records trigger values with the wrong sign.**
`agent/startup.py:75-80`
- vgamepad 0.1.0 declares `XUSB_REPORT.bLeftTrigger` and `bRightTrigger` as signed `c_byte`. Every cached build on this PC (`vigem_commons.py:47-48`) does.
- `right_trigger_float(1.0)` stores 255, which ctypes reads back as **-1**. Any value from 128 to 255 reads back negative.
  - I reproduced this with the same ctypes layout: `255 → -1`, `128 → -128`, `0xC0 → 0xc0` for buttons.
- **Failure scenario:** `--report-timing` evidence for any trigger press records `"rt": -1` for full Spider-Power (Spider-Power, melee alias, keepalive) or `"lt": -1` for Web-Cluster.
  - An auditor or script checking `rt > 0` concludes that the trigger was never pressed.
  - The doc's claim of "raw integer lt/rt" (`docs/pad-bindings.md`) is wrong for real devices.
- The synthetic `ReportPad` stores Python ints (`int(value*255)`), so it cannot catch this.
- Buttons (`c_ushort`) and sticks (`c_short`, signed by design) are correct. The LS+RS ultimate-mask evidence is unaffected.
- **Fix:** record `int(report.bLeftTrigger) & 0xFF` and `int(report.bRightTrigger) & 0xFF`. Add a test whose fake report is a real `ctypes.Structure` with vgamepad's field types.

**2. Medium, plan before the next sitting: `yawmap` cannot complete with its current pulse schedule, and the guard will now refuse partway through.**
`scripts/l4_measure.py:286-310`
- The guard is doing the right thing here, and this is a pre-existing measurement-design limit. But the new sitting would find it only after spending the time.
- The phase check runs on the fixed 360 px `YAW_BOX` crop.
  - On ideal full-overlap white noise it accepts a shift of 160 px and refuses from 200 px up (response 0.335 → 0.115 at 290 px).
  - Real scenery will be worse (finding 3).
- `Live.hold` renews every 50 ms, so the nominal 0.06 / 0.10 / 0.12 / 0.25 s pulses actually last about 0.10 / 0.10–0.15 / 0.15 / 0.28–0.30 s.
  - The sitting's own `focal-pin-a3.json` measured 0.102 s and 0.278 s.
  - At the measured 161°/s (0.45 stick), those pulses move the patch 45° or more; it leaves the crop entirely.
  - The sitting's candidate map already showed this with the old template-only code: `short` dx -201 with score 0.28, `long` dx +97 with score 0.28 and the **wrong sign**. The new guard correctly refuses such samples. Before, they would have been recorded as data.
- **Consequence:** a new `yawmap` will very likely raise `MotionRefused` on the 0.45 stick 0.25 s pulse at the latest, and probably at 0.3 or even 0.2. It will not reach the higher deflections, and it ends the whole run.
- **Fix before the sitting (owner's choice):**
  - shorten the pulses, or stop `hold` from overrunning, so the patch stays inside the crop;
  - or search phase over a wider strip, or at the template-matched location;
  - or measure large deflections by timing, as `period` does.
- A refusal is unknown, never data, so this is fail-safe. It is a scheduling risk, not a safety risk.

**3. Low: unwindowed phase correlation can falsely refuse smooth scenery, and the tests hide it.**
`scripts/l4_measure.py:47-52`
- `cv2.phaseCorrelate(a, b)` runs without a window. On a Gaussian-blurred texture (sigma 3, standing in for low-texture scenery), an **8 px** shift with no wraparound gives a response of -0.002, so it is refused. With `cv2.createHanningWindow` it gives the correct -8.0 px with a strong peak.
- The real period bands passed with only 37–48 usable pairs out of roughly 160, which is consistent with this.
- The tests build every moving case with `np.roll` of white noise. Wraparound keeps full overlap, and white noise has no low-frequency edge energy, so neither this nor finding 2 can show up.
- **Fix:**
  - pass a Hanning window (it does not weaken static refusal: a static pair still has |shift| < 1);
  - add a non-wrapping, band-limited synthetic control, plus a partial-overlap control at the largest planned shift.

**4. Low: map samples are not checked against the commanded direction.**
`scripts/l4_measure.py:238-241`
- `checked_shift` requires phase and template to agree in sign with *each other*, not with the stick direction. A right pulse whose scenery moves right would pass and record a negative angle.
- Two independent estimators both flipping is unlikely, but it would be one line to require `along * sign(command) < 0` for yaw (the scene moves opposite to the turn) and the matching rule for pitch.

**5. Nit: the audit JSON may not be strict JSON.**
- Audit `pairs` keep raw phase values, and `json.dumps` defaults to `allow_nan=True`, so a nonfinite phase result would be written as `NaN`.
- I did not observe it: flat frames gave finite values. Consider `allow_nan=False` with `None` for nonfinite values.

## Disposition

**LAND WITH FIXES:**
- Finding 1 is a one-line fix plus a test. Land it before any `--report-timing` evidence is relied on.
- Finding 2 needs a decision on the pulse schedule before the next sitting. It is not a blocker for landing the guard itself, which is fail-safe.
- Findings 3–5 are recommended.
- Nothing here re-approves Cal values, focal or a pilot. No live acceptance or false-rejection rate is established.

## Delta re-review (fixes-1), 2026-09-26: LAND

**Inputs.** The fixes-1 `HANDBACK.md` is `6843e983…`. All six working-tree files match its hash table: `startup.py` `d2382fb5…`, `l4_measure.py` `4045f76c…`, `pad-bindings.md` `4f2e6946…`, `test_watch_pad.py` `1bed7175…`, `test_l4_motion.py` `e0df194d…`, `test_l4_scripts_close.py` `5240fbcc…`. I diffed them against the `upstream/snapshot/` copies of the version reviewed above.

**Tests.** In a private perception env with **no vgamepad installed** (`find_spec` returned None), the nine-file focused run gave **209 passed**.

**F1: retracted. It was my error. The fix is harmless and kept.**
- Every cached vgamepad 0.1.0 build defines `c_byte = c_ubyte  # because BYTE is actually unsigned char` at `vigem_commons.py:9`.
- My original check grepped only the field declarations and reproduced the bug with the real `ctypes.c_byte`. Real trigger reads were never negative.
- The author's `int(...) & 0xFF` is correct for either type. The new test uses real `ctypes.Structure` layouts with both `c_byte` and `c_ubyte` triggers (values 0/127/128/255), signed stick endpoints and the 0xC0 chord.

**F2: closed.**
- Map pulses no longer use `Live.hold`'s 50 ms loop. `pulse` does a fresh `send_guarded` with `not_after = release_at = deadline`, sleeps, and releases in `finally`. It refuses pulses over 80 ms and any overrun greater than 10 ms, and never retries.
- Measured `hold_s` replaces the nominal durations in the rate calculations.
- Durations are 0.04/0.08 s up to 0.45 stick, 0.02/0.04 s above that, and 0.04/0.08 s for pitch.
- Patches are centred (yaw `(520,100)-(760,260)`, pitch `(920,280)-(1160,440)`). The template is located in the whole frame, then phase-checked at the matched location. Shifts are capped at 512/256 px.
- My probe, rerun on white noise and on σ=3 and σ=6 Gaussian scenes without wraparound:

| Direction | Accepted | Refused |
|---|---|---|
| Yaw | every shift 8–512 px, including 217 and 466 | 560 px (beyond the envelope) |
| Pitch | every shift 8–256 px | 300 px |

- Before this fix, yaw was refused from about 200 px. At the measured 161°/s, the longest 0.45 pulse (0.09 s) turns about 14.5°, roughly 120 px at f=465, well inside the envelope.

**F3: closed.**
- `phase_shift` uses `cv2.createHanningWindow` on copies, so retained evidence is untouched.
- The tests build non-wrapping σ=3 scenes. My earlier σ=3 case of 8 px (refused without the window) is now accepted. Static, and static plus ±2 grey-level noise, are refused.
- The retained stationary period is still refused (median 0.003 px). The moving a3-1/2/3 periods have 71/92/84 usable correct-sign pairs, up from 37/39/48.

**F4: closed.**
- Every forward, cumulative and return `checked_shift` passes the commanded scene sign: yaw opposite to rx, pitch the same as ry. The `yawleft` signs are correct too.
- `period` requires `direction=-1` both per pair and in the median of the signed shift.
- My wrong-sign probe (a perfect match moving the wrong way) is refused. The tests cover both axes and both signs.

**Nit 5: closed.** Nonfinite values become null, and both writes use `allow_nan=False`.

**Safety, rechecked.**
- `main` still orders things as argparse, then focal validation, then exclusive output reservation, then `live_factory()`. Close-in-`finally` and retained failure records are unchanged.
- I ran `pulse` against a fake Live for the normal case, an `InputExpired` send, `KeyboardInterrupt` and a timing overrun. Each ended with `release()` as the last call. A pulse longer than 80 ms raises `ValueError` before any send.
- Only the map functions call `pulse`; `yaw` and `period` still use `sample`.

**Residual notes (not blocking):**
1. **Equal-pulse focal is unreliable without `--focal`.** With the yaw patch now centred (xa=0), the equal-pulse focal candidate is decided by integer pixel rounding. At 161°/s, a true f of 465 gave candidates 379 or 540. `yawmap` without `--focal` silently uses that median, and `yawleft` without `--focal` still uses the known-wrong 760. The procedure already requires a period-pinned `--focal`. Making `--focal` mandatory for both, or dropping the candidate, would enforce that. Focal pinned from the period rate and pulse differences is well conditioned at the centre.
2. **A low-deflection refusal ends the whole map.** The 0.1 stick pulses (0.04/0.08 s) give only about 6–12 px at the old rates. If the alt's collapsed Advanced deadzone swallows 0.1, the first sample is refused and the whole `yawmap` ends. That is fail-safe, but consider running high deflections first or recording that deflection as unknown and continuing.

Neither affects safety or false acceptance. This review established nothing about live behaviour: real completion rates, ramp/response-time effects and native-frame turn counts remain for the supervised sitting.
