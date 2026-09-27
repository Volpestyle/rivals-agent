LAND

# Pre-run review: camera-turn driver (VUH-1384), binds-review (Opus 5.5), 2026-09-27

Read-only and independent. I sent no input, did not drive the desktop, and used no GPU (CUDA hidden in every run of mine).

## Inputs

- `HANDBACK.md` is `3e5191ee…`.
- All 11 entries of `source-hashes.json` match the working tree. The new files are `scripts/measure_camera_turns.py` (`96752b7f…`) and `tests/test_measure_camera_turns.py` (`942c78d2…`), both uncommitted. The existing dependencies are `controller`, `startup`, `l4_measure`, `record`, `pad_bindings`, `loop`, `run_range_bc_live`, `live_range_bc` and `capture`.
- **Tests:** 16 passed in the live-loop private env with CUDA hidden.

**Verdict.** **LAND** for live-game input, the part in review scope under James's rule (`2e00d3f`: pre-run review only for live input, spend guards and sealed-data access). The input path is safe and may run under the receipt below, within the stated block limits.

The turn-rate and focal **analysis** is exploratory. Under `2e00d3f` it is not reviewed, and the owner's tests are the check. My findings on it (A–C, the sweep and the l4 pitch records) are **advisory to the owner**, not review gates. They matter for the owner, though: the current candidate output can be a repeatable wrong rate. The raw bands, reports and native video are retained, so the analysis can be redone offline.

## Input safety: sound

**Bounded input.**
- The only non-neutral command is `{**NEUTRAL, "rx": d}`, with `d` from a fixed signed set (±.1, .2, .3, .45, .6, .8, 1). No buttons, so no X hold.
- At most 4 distinct deflections, segments of 0.5–20 s each, and a block of 180 s or less that must leave time for inspection.

**Per renewal.**
- A fresh proof checks focus, keyboard, report-capture health, a fresh frame, the range HUD, **no idle banner**, and the attach deadline.
- `Live._commit` then re-proves the frame.
- The lease is at most 100 ms and capped at the segment end, with `scope_not_after` at the block end.

**Independent stop.** A 10 ms monitor closes the pad on block deadline, keypress or focus loss even if capture blocks. `finally` releases and closes, and exceptions are recorded, then re-raised.

**Ready-token gate.**
- The pad stays neutral while the ready frame is saved and the lead inspects it.
- The wait still re-proves the scene about every 50 ms.
- A wrong token, a stale file from another run (every run creates a new output directory) or a block timeout ends the block.
- Any keypress during the wait also stops it, so `continue-N.json` must be written without keyboard input on the PC: remotely or by an agent, as the hand-back says.
- **Recommendation:** write the marker atomically (temporary file, then rename). A partially written JSON currently ends the block, which is fail-closed but wasteful.

**Other checks.**
- A motion refusal stops before the next segment.
- Setup follows the reviewed pattern: a 3 s neutral settle, and a receipt checked against both import-time and current bytes, before preparation and before Live.
- Prepare-only never opens a pad.

## Analysis: defects I measured on synthetic panoramas

I drove `return_candidates` with bands from a smoothly rotating synthetic panorama, with sub-pixel motion and known periods:

| Case | Candidate | Truth | Repeatability gate |
|---|---|---|---|
| **Two identical halves** (a scene repeating every half turn), 2.0 s period | **360°/s** | 180°/s | **passes** |
| 0.87 s period (about 1.0 stick) at 60 Hz sampling | **82.8°/s**; every 5th return detected, intervals 4.35 s = 5 turns | 413.8°/s | **passes** |
| 0.87 s period at 30 Hz sampling | `MotionRefused` (about 77 px per sample) | — | the block stops |
| 2.23 s period at 30 Hz, fine texture | no returns; the 0.85 peak threshold missed by sample phase | — | unknown |
| 2.23 s period at 30 Hz, smoother texture | missed returns, intervals 2.23 s then 13.4 s | — | fails (safe) |
| 2.23 s period at 60 Hz, smoother texture | 161.2°/s | 161.4°/s | passes |

The ≤5% spread gate cannot detect **consistent** aliasing, whether fractional (a symmetric scene) or integer multiples (missed returns in resonance with the sample rate).

**Advisory A (before trusting any candidate): an independent coarse angle per interval.**
- Integrate the frame-to-frame horizontal shifts, which the motion audit already computes, between successive returns.
- Convert to degrees with a bracketed focal: any f from 465 to 760 px gives a revolution within about ±25% of 360°.
- Refuse intervals whose integrated angle is not about one turn. This separates the 180°, 360°, 720° and 1800° aliases.

**Advisory B**: report timing uncertainty.**
- Estimate each return's time below one sample, for example by parabolic interpolation of the correlation around the peak, or from the residual shift at the nearest sample divided by the local image velocity.
- Record the per-return timing uncertainty and enforce the proposal's own gate: crossing uncertainty at most 5% of the interval.
- The fixed 0.85 peak threshold is sensitive to sample phase; phase-independent timing removes that.

**Advisory C (before running ≥0.8; this one touches the input loop): sample bands at the capture rate.**
- `collect_segment` records one band per renewal and sleeps 20 ms, so a fast turn exceeds the motion guard's phase-correlation range, which then stops the block.
- Record every fresh frame. Keep proof and renewal cadence independent of band retention.
- Until then, run the ≥0.8 deflections last in their own block, because a refusal ends that block.

In every case the native video still has to confirm one turn per interval, a level camera and no bots, as the hand-back already requires. The code correctly never marks a map accepted.

## Far-landmark sweep: sound in principle; the timing gate is likely infeasible as written

- `hfov = |rate| × (t_exit − t_enter)`.
- The error bound `|rate|·δt + σ_rate·(T + δt) ≤ 0.5°` and the 1° repeat agreement are correct and conservative.
- At the measured 161°/s, however, the bound needs δt ≤ **3.1 ms** even with zero rate error, which is sub-frame at 60 or 120 fps. Slow deflections that would relax it cannot complete three full turns in 20 s.
- **Better options, in order:**
  1. **Mouse-count sweep.** FOV = counts × 0.0330738°/count (a 360° closure gain, 0.02%). This is timing-free, so frame rate does not limit it. The projection does not depend on input device, and this is the method in my focal review.
  2. **Track fit.** Fit `x(t) = 640 + f·tan(ω(t − t_c))` to the far landmark's position over every frame of one sweep, with ω from the full-turn rate. That uses all frames instead of two edge instants.
- Keep the near-landmark parallax control as a diagnostic only, as proposed.

## Existing l4 yawmap pitch and back records (the question from live-loop)

I agree: **do not present the `back` records as a calibrated negative-pitch rate.**
- `yawmap` stores forward pitch rows with `hold_s` durations, but the `back` entries hold only dx, dy and score from a checked shift. The return value of `pulse(live, secs, ry=-d)` is discarded.
- Those records establish sign and motion only.

Two further points:
1. **Forward pitch "rates" are also focal-conditional.** With `PITCH_BOX` centred (ya = 0), degrees = `atan(dy/f)`. So forward pitch rows are not calibrated rates until focal is accepted; they are pixel displacements over measured holds.
2. **Durations for the back pulses can be recovered without changing code.** If the sitting runs `l4_measure yawmap --report-timing`, the `full_reports` observer records every outgoing report with its return time. The actual hold of each back pulse is recoverable there: the report-return interval, which is not device acknowledgement. Recording `hold_s` for back pulses in code would change `l4_measure.py`, which is pinned by `5c3f74e` and this receipt, and so would need a new review.

## Receipt (`camera-turns-review-v1`), exact bytes

Also saved as `camera-turns-review-v1.json` beside this file. It covers code identity for input safety. It does **not** accept any turn rate, focal length or map, and the lead owns scheduling.

```json
{
  "format": "camera-turns-review-v1",
  "files": {
    "scripts/measure_camera_turns.py": "96752b7f00ebed1db871e6e879f692af3a6abc44648e38da29b13ab37028f9cc",
    "tests/test_measure_camera_turns.py": "942c78d201f3cf1552f730525cb9f9cb1fce5986c9ea568f3c1a559647ba0464",
    "agent/controller.py": "4e5bb70fca797ab17a25a8699d1ad111f0b7cd561f59d2b308a52c10b44da060",
    "agent/startup.py": "d2382fb5d9e0cc4fcb865f97eb43060ca223dbf7982375fc9fdc8a1352d7737a",
    "scripts/l4_measure.py": "4045f76c752a6a8ee73f67de114e8939c801e27b580e815c6932ffa568e8075b",
    "scripts/record.py": "d6aa320beb99a96953cccec2be81abbc9f65b026abade86fb34bff31babadead",
    "agent/pad_bindings.py": "e71558625b1f35d0203958d383134fa98cdee55ecc94d65c2ea27eff87cdefc1",
    "agent/loop.py": "040c77c2c4ed0fff5a893e6e00991c8df7bad1e87267bf6d416964911b1e596f",
    "scripts/run_range_bc_live.py": "446ef0bb2dc74c615f8c445dfac043ec0be4bfbd3c36195e9dfc727c8a9f7823",
    "agent/live_range_bc.py": "d4c109e7c7c503728df2ea82d021154f40a90b05a54bd37bdae64be41b2baa46",
    "scripts/capture.py": "b98f310616cf0569375d3e24cbb564d7702872c4ffaa888523ac6b52f96fb547"
  }
}
```

## Disposition

**LAND** (live input, in scope under `2e00d3f`).
- The input path may run under this receipt, for blocks of 4 deflections or fewer, with ≥0.8 run last or in its own block.
- Advisories A–C and the sweep method are exploratory analysis: the owner's check, not review gates. Until A and B exist, treat every candidate rate as unverified and rely on native-video turn counts.
- Any edit to `scripts/measure_camera_turns.py` changes its pinned hash. Only a change to the **input path** (for example C, in `collect_segment`) needs a new pre-run check and receipt. For an analysis-only edit, the lead may ask me to re-pin after a diff shows the input path is unchanged.
