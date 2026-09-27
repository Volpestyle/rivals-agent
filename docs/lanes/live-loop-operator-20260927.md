# Camera + FPS operator commands (2026-09-27)

Operator/desktop owner: herdr-lead, authorized by James to navigate and refresh
activity. No input from live-loop or its workers. Run ONE command at a time,
inspect its result, then choose the next. Do not paste all commands as a batch.
Only launch live commands through the established interactive desktop runner,
with the game already foreground. Plain SSH cannot own dxcam or pad capture.

**HOLD: startup repair is drafted, untested and awaiting pre-run review.**
The stopped yaw-01 sitting exposed fresh-pad drift during the token wait.
Current source differs from 6f3a7f7; receipt a2 (5c9da6f0) is now stale.
Do not execute this sheet until the new source has passed tests and binds-review.
Full turns need NO focal. Every short-pulse block needs an ACCEPTED focal receipt.
Offline focal remains unknown at this writing; do not wait in the range for it.
The fallback is entirely neutral on TRAIN, so there is NO learned policy block.

## 0. Operator setup

The lead may use reenter.py for setup, as James authorized. Enter Practice Range
as Spider-Man on the alt, Steam Input DISABLED, H/V 247/124.
Verify actual saved curve/assist/settings, normal cooldowns, open level bot-free
view, no idle warning. Turn monitor on, enable visible FPS counter, and start
native OBS video. Native video is required to count full turns; NPZ returns alone
are not proof. Pin the actual PID, sitting and native recording in this setup:

```powershell
Set-Location C:/Users/volpe/repos/rivals-agent
$camPython = 'C:/Users/volpe/.venvs/rivals-live-cu128/Scripts/python.exe'
$camSitting = 'REPLACE-WITH-NEW-SITTING'
$camRoot = "C:/Users/volpe/repos/rivals-agent/data/calibration/$camSitting"
$camGamePid = 12345 # REPLACE with fresh foreground Marvel game PID
$camVideo = 'C:/Users/volpe/Videos/REPLACE-WITH-CURRENT-NATIVE-OBS.mkv'
$camReceipt = 'REPLACE-WITH-ACCEPTED-STARTUP-REPAIR-RECEIPT'
$camCommon = @('--live','--review-receipt',$camReceipt,'--game-pid',"$camGamePid",'--sitting',$camSitting,'--recording-ref',$camVideo,'--scope-seconds','180')
```

The durable env receipt is commit 38bf7953. Inference imports and package checks
passed. DXCAM import failed enumerating displays in service session 0; the lead
will probe DXCAM/vgamepad through a C:\desk job in console session 1 after James
closes the game. No CUDA forward or desktop qualification is claimed yet.

Perform a guarded move-and-attack activity refresh **before the first block**,
then close that pad and restore the inspected pose. Setup alone did not prevent
the prior inactivity drop. Each --output must be a NEW directory. The driver
performs capture preflight and ready-attach inspection BEFORE constructing Live;
keyboard released and range already focused. The draft startup sequence is:

1. Inspect ready-attach.png/json: range, level, bot-free, no idle or device banner.
   Atomically write continue-attach.json. There is no pad during this wait.
2. Attach with zero settle and immediately issue the guarded M1 +.45 rx /300 ms
   prime. The motion check must pass without retry, then five seconds neutral.
3. Inspect NEW ready-0.png/json after the roughly 50-degree initialization:
   level, bot-free, banner cleared and range intact. Write a NEW continue-0.json.
   A bad pose ends the block; no automatic leveling or search.

Prime and settling are initialization_excluded; their times are retained. The
draft refuses changed/ambiguous views during token waits. No numerical focal or
camera rate is inferred from initialization.
Stop on any scope/focus/HUD/idle/key/deadline/refusal. No automatic retry.
Only after the process closes may the lead run his established guarded
move-and-attack keep-alive, restore/reinspect pose and start another block.
Never refresh activity while the measurement pad is attached.

## 1. Full-turn yaw: four commands in order, no focal

```powershell
uv run --no-project --python $camPython python scripts/measure_camera_turns.py @camCommon --deflections .45 -.45 .1 -.1 --seconds 20 --output "$camRoot/yaw-01"
```

Then, after inspection/closed state and lead's separate keep-alive:

```powershell
uv run --no-project --python $camPython python scripts/measure_camera_turns.py @camCommon --deflections .2 -.2 .3 -.3 --seconds 20 --output "$camRoot/yaw-02"
```

Then, after inspection/closed state and keep-alive:

```powershell
uv run --no-project --python $camPython python scripts/measure_camera_turns.py @camCommon --deflections .6 -.6 --seconds 20 --output "$camRoot/yaw-03"
```

Finally the >=.8 block, after inspection/closed state and keep-alive:

```powershell
uv run --no-project --python $camPython python scripts/measure_camera_turns.py @camCommon --deflections .8 -.8 1 -1 --seconds 20 --output "$camRoot/yaw-04"
```

For every segment index 0..3 (or 0..1 for yaw-03), inspect ready-N.png and
ready-N-frame.json alongside ready-N.json. Confirm range HUD, no idle banner,
level view, no bot/obstacle crossing the intended panorama, and correct signed
deflection. Pad is neutral while awaiting token. After the segment, inspect
segment-N.json and retained NPZ/native video for continuous expected rotation,
no collisions/clamps or repeated half-turn mistaken for full return. The next
ready frame is the post-segment inspection. Any analysis refusal stops the
block, retaining raw evidence; low magnitudes may lack enough turns in 20 s.
Do not infer zero or a rate from that refusal. Record unexecuted rows as unknown.

## 2. Tokens: remote/agent terminal only, for the currently inspected frame

Each command's output directory contains ready-N.png, ready-N-frame.json and
ready-N.json; write matching continue-N.json in THAT SAME directory. For a
block the first index is the string attach, then 0..3. Never preapprove
later frames or copy a prior block's token. The following performs ONE approval
only AFTER visually inspecting the named ready image:

```powershell
$tokenBlock = "$camRoot/yaw-01" # current output directory
$tokenIndex = 'attach' # pre-pad approval; then NEW tokens for 0,1,2,3
$tokenReady = Get-Content -LiteralPath "$tokenBlock/ready-$tokenIndex.json" -Raw | ConvertFrom-Json
$tokenFinal = "$tokenBlock/continue-$tokenIndex.json"
if (Test-Path -LiteralPath $tokenFinal) { throw 'Token marker already exists' }
$tokenTemp = "$tokenBlock/continue-$tokenIndex.$([guid]::NewGuid().ToString('N')).tmp"
[System.IO.File]::WriteAllText($tokenTemp, (@{token=$tokenReady.token} | ConvertTo-Json), [System.Text.UTF8Encoding]::new($false))
Move-Item -LiteralPath $tokenTemp -Destination $tokenFinal
```

The file is closed before same-directory rename. Do this via the remote/agent
shell; do not type on the game PC keyboard or steal focus. Independent monitor
stays active after attachment; pre-attach capture checks focus/keys/HUD/idle and
deadline without a pad. A wrong/stale token or changed pose stops the block.

## 3. Short pulses: ONLY after focal is accepted

The lead's new JSON must contain acceptance='accepted', a positive finite
focal_px_1280 and evidence reference. Preserve source fit/uncertainty/account
and whether it transfers to this view. No receipt exists yet; do not write an
accepted flag merely to unlock this command. Use the actual accepted path:

```powershell
$camFocal = "$camRoot/focal-accepted.json"
```

Each pulse block uses the SAME pre-attach token, M1 prime and five-second neutral
startup described above. Re-check the approximately 50-degree changed pose on
NEW ready-0, then approve a separate token. Initialization frames/reports/video
are excluded from calibration. Each signed measurement has its own token.

The following is the ordered command list for ONE repetition. Repeat it for
rep02 and rep03 only inside the sitting cap, with NEW directory names and
activity/pose refresh between blocks. These are individual operator commands,
not a loop or permission for unattended continuation:

```powershell
uv run --no-project --python $camPython python scripts/measure_camera_turns.py @camCommon --pulse-axis ry --focal-receipt $camFocal --deflections .5 -.5 1 -1 --seconds .04 --output "$camRoot/pitch40-rep01"
uv run --no-project --python $camPython python scripts/measure_camera_turns.py @camCommon --pulse-axis ry --focal-receipt $camFocal --deflections .5 -.5 1 -1 --seconds .08 --output "$camRoot/pitch80-rep01"
uv run --no-project --python $camPython python scripts/measure_camera_turns.py @camCommon --pulse-axis rx --focal-receipt $camFocal --deflections .45 -.45 1 -1 --seconds .033 --output "$camRoot/yaw33-rep01"
uv run --no-project --python $camPython python scripts/measure_camera_turns.py @camCommon --pulse-axis rx --focal-receipt $camFocal --deflections .45 -.45 1 -1 --seconds .067 --output "$camRoot/yaw67-rep01"
```

Before every pulse check ready-N for range/idle, bot-free view and distance from
pitch clamp; alternate signs as listed. Afterward inspect pulse-N-before.png,
pulse-N-after.png and segment-N.json, expected
scene direction, drift, measured duration/overrun and motion confidence. A
failure stops the block. No automatic return pulse, no guessed focal, no live
policy. Short-pulse results are displacement/mean response, not steady rates.

## 4. FPS A/B/A: 120 seconds, no focal or pad

Only after camera process closes. Perform activity refresh BEFORE starting,
then hold a fixed range view with visible FPS overlay and unchanged resolution,
settings, OBS and FPS cap. No other capture/inference/decode worker runs.
Use a fresh observed settings JSON with binding_profile, swing_mode, cooldowns
and patch matching actual sitting observations. The offline settings document
is a schema/example, not a new sitting observation. No camera map is consumed.

```powershell
$fpsSettings = "$camRoot/settings-observed.json"
$fpsOutput = "$camRoot/inference-fps-aba"
$fpsArgs = @('--checkpoint','data/diagnostics/live-loop-fallback-20260927/model_nohud-seed0.pt','--checkpoint-sha256','2d5183cba12913a36327e0a459ec0c0b2a1238d26a7df98f7823929af3129f18','--support-json','docs/evidence/live-loop-fallback-20260927/support.json','--settings-json',$fpsSettings,'--preprocessor','compact-bgr','--cpu-threads','2','--capture-hz','30','--device','cuda','--desktop-capture','--game-pid',"$camGamePid",'--sitting',$camSitting,'--native-video',$camVideo,'--output',$fpsOutput)
uv run --no-project --python $camPython python scripts/measure_inference_fps.py @fpsArgs
```

Append --fps-cap with the ACTUAL configured cap if present. Each phase has 10 s
warmup +30 s measured; A1/B/A2 complete automatically without actuator. B runs
CUDA inference and discards output. Native PNG counter samples are retained
at 1 Hz; keep pose fixed, no keep-alive during the 120 s. Refusal retains partial
evidence, not an FPS result. After closure inspect result.json and retained
frames, then copy fps-annotations.csv to fps-manual.csv, fill visible FPS values
(unreadable blank), and summarize offline:

```powershell
Copy-Item -LiteralPath "$fpsOutput/fps-annotations.csv" -Destination "$fpsOutput/fps-manual.csv"
# Fill fps-manual.csv from retained native frames before this next command.
uv run --no-project --python $camPython python scripts/measure_inference_fps.py annotate $fpsOutput "$fpsOutput/fps-manual.csv"
```

No live-loop or live-fps concurrent process is required. The CPU focal worker
has no decode running as of its latest report; it must not decode while
Marvel/OBS is active. Light existing-evidence math is the only concurrent work
permitted before FPS; stop even that for the A/B/A comparison. No input from
workers. Lead owns navigation, keep-alives, native recording and stop decisions.
