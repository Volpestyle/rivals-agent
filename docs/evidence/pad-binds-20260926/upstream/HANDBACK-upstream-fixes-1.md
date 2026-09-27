# VUH-1384 upstream review fixes, revision 1

pad-binds (Codex), 2026-09-26. Offline, uncommitted and unstaged. No game input,
desktop jobs, device construction, deployment or Cal change in this task.
Ready for binds-review's delta review; not live-approved by this handback.

Read the complete `../review-upstream-20260926.md`, SHA-256
`69cf40467155e05d9bf819e9ae8c0d4cc095f0c44258c4dda427138143bbe10c`.
This revised handback supersedes the implementation details/hashes in
`../HANDBACK.md`; that pinned original and its snapshot remain intact.

## Fixes

**F1: unsigned trigger bytes.** `watch_pad` records both triggers using
`int(field) & 0xFF`. Sticks remain signed and buttons remain the unsigned mask.
The regression uses real ctypes.Structure layouts with c_ushort buttons,
c_short sticks, and both c_byte and c_ubyte trigger variants. Values
0/127/128/255, full signed stick endpoints and the atomic 0xc0 chord are covered.
The cache build inspected at `archive-v0/3NLoTmeaqiVZFyr8iMcJo/vgamepad/win/vigem_commons.py`
actually aliases c_byte to c_ubyte on line 9; unlike the review's reproduction,
that alias reads 255 as positive. No vgamepad was imported. The requested mask
is correct for either representation, and both are tested.

**F2: change the pulse schedule and matching geometry.** The old .25-second
map pulse and Live.hold's 50 ms loop rounding are removed from map measurements.
`pulse` uses an existing fresh `Live.send_guarded` path with identical send/release
deadlines, then finally-neutral. It never retries a refused/expired send. A caller
timing interval more than 10 ms over nominal refuses the measurement. The existing
watchdog still caps the lease if the caller stalls (20 ms watchdog resolution;
this is not a hard real-time/device-arrival guarantee).

| Measurement | Nominal durations |
|---|---|
| Positive/negative yaw through .45 | .04 / .08 seconds |
| Positive/negative yaw above .45 | .02 / .04 seconds |
| Pitch .5 / 1 and their returns | .04 / .08 seconds |
| Equal-pulse candidate | Two .04-second +.45 pulses and checked returns |

Yaw uses the upper-center patch `(520,100)-(760,260)` instead of a patch near
the right edge. Negative yaw uses the same patch. Pitch uses the right-side,
vertically centered patch `(920,280)-(1160,440)`. Template search locates the
source patch in the whole destination image; windowed phase correlation then
verifies the matched patch has response >=.2 and residual <=1.5 px on each axis.
This replaces phase correlation between fixed crops that lose overlap. The
movement still comes from the nonzero template displacement, never from a
near-zero phase residual. Identical/flat patches, template score <.8, displacement
<2 px, excessive off-axis motion or motion beyond the tested envelope are refused.

At measured 161 deg/s, the longest .45 pulse including 10 ms allowance turns
14.49 degrees. The projection test checks every patch edge in both directions,
using focal 250/465/760/1000 and planning ceilings of 500 deg/s high yaw and
150 deg/s pitch. Edges remain inside the 1280x720 image. These ceilings/focals
are planning assumptions, not measured Cal values. The largest tested partial
overlap is +/-512 px horizontally and +/-256 vertically, with non-wrapping,
Gaussian-band-limited scenes; larger template displacements are refused.
Synthetic complete yawmap/yawleft runs use translation magnitudes scaled to
the measured .45 rate and planned pitch rate, not constant 8 px per pulse.

`hold_s` records each forward pulse's update-return interval estimate. Map rate
differences use that interval rather than nominal duration; full report observer
stamps remain the authoritative outgoing timing evidence. The changed yaw patch
has x=0 at its center; docs now give `angle(f,dx)=-degrees(atan(dx/f))` for focal
pinning. Do not reuse the old x=360 formula or old candidate timing schedule.

**F3: Hanning and realistic controls.** The shared phase helper uses
`cv2.createHanningWindow` and copies both inputs before correlation so OpenCV
cannot alter retained evidence. Motion controls now take moving windows from a
larger Gaussian-blurred scene (sigma 3); no np.roll/wraparound. The suite covers
smooth small translations, both signs/axes and large partial overlap. A test
verifies the evidence arrays stay byte-identical after phase evaluation.

**F4: commanded sign.** Each forward, cumulative candidate and return match
must have the commanded scene sign: yaw opposite rx, pitch same sign as ry.
Opposite motion is refused even with a perfect template match. Period's +.45
check also requires negative scene dx and a positive median displacement in
that expected direction; eight correct-sign outliers cannot outweigh a majority
moving the wrong way.

**Review nit 5 also fixed.** Nonfinite phase/match audit values become null,
and success/failure JSON serialization uses allow_nan=False. Synthetic nonfinite
phase output is refused and serializes as strict JSON.

## Validation

Final focused runs, all offline, exit 0:

- Private stdlib env `C:/Users/volpe/AppData/Local/Temp/rivals-pad-upstream-stdlib`:
  `uv run --offline pytest -q tests/test_watch_pad.py tests/test_startup.py tests/test_padprime_m1.py tests/test_live_pad.py tests/test_controller.py tests/test_pad_bindings.py`
  -> **126 passed, 1 skipped**, the existing numpy/cv2-dependent startup case.
- Private perception env `C:/Users/volpe/AppData/Local/Temp/rivals-pad-calibration`:
  `uv run --offline --group perception pytest -q tests/test_l4_motion.py tests/test_l4_scripts_close.py tests/test_watch_pad.py tests/test_startup.py tests/test_padprime_m1.py tests/test_live_pad.py tests/test_controller.py tests/test_pad_bindings.py tests/test_record_pad_bindings.py`
  -> **209 passed**. Logs are `stdlib-tests.txt` and `perception-tests.txt` here.
- `uv tool run --offline ruff check agent/startup.py scripts/l4_measure.py tests/test_watch_pad.py tests/test_l4_motion.py tests/test_l4_scripts_close.py`
  and `git diff --check` -> passed.
- `uv run --offline --group perception python <this folder>/check_retained.py`
  -> passed. The original stationary failure still has zero shifted pairs and
  median .003367 px. Moving a3-1/2/3 have 71/92/84 usable, correct-sign pairs
  respectively, up from 37/39/48 unwindowed usable pairs. Results retained in
  `retained-motion-results.json`. Only calibration evidence was read.

During development, one old synthetic period assertion expected >1.5 seconds;
the new non-wrapping control selected the existing inclusive 1.5-second boundary.
The assertion was corrected to >=1.5. This test checks motion acceptance only,
not that a random translating scene proves a revolution. Final suites pass.

## Review limits and next consumer

F2 now has a schedule/geometry that completes synthetic map controls and avoids
the known overlap failure at the measured rate. It is not a claim of verified
live completion at 247/124: real perspective distortion, motion blur, scenery,
input latency/ramp (configured response time 35), host scheduling and rates
outside the planning envelope can still refuse a sample. Refusal stays unknown,
never zero or calibration data. Actual output timing and one-turn/native-frame
inspection remain required. The two-turn alias remains outside this change.

Review the shortened pulse path, template-located phase semantics and patch/
focal geometry delta before a supervised sitting. No pilot or freeze is approved.
All six owned working-tree files and snapshot copies match the hashes below;
other lanes' edits (including AGENTS.md) were preserved.

## Changed paths and working-tree SHA-256

Exact copies are under `snapshot/`; machine-readable hashes: `source-hashes.json`.

| Path | SHA-256 |
|---|---|
| agent/startup.py | d2382fb5d9e0cc4fcb865f97eb43060ca223dbf7982375fc9fdc8a1352d7737a |
| scripts/l4_measure.py | 4045f76c752a6a8ee73f67de114e8939c801e27b580e815c6932ffa568e8075b |
| docs/pad-bindings.md | 4f2e6946b1d13f69e5108a48d340ccd27f40f50754d97713f4d3243a4a818103 |
| tests/test_watch_pad.py | 1bed7175a7a38347b8aeb39f758e75411108c09f5997deb401168eefe72c2854 |
| tests/test_l4_motion.py | e0df194da7dd3c909e390c410ea909ba9741599f8f174bccaa5fbcd6cfac864b |
| tests/test_l4_scripts_close.py | 5240fbcc093a64263a7feb5c6decca94ef7db22146cb0d59d0cc5bb98439f7c8 |
