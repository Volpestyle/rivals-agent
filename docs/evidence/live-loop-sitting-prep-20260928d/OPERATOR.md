# alt-cam-20260928d: lead-operated yaw first, then optional FPS

Ready for the lead to schedule. Source and independent v3 receipt are in
`6e3b7b0`, re-verified after commit on `C:/Users/volpe/repos/rivals-agent`. Run from that
checkout using the durable interpreter below. No mirror deployment is needed.
The old `C:/desk/out/yaw.ps1` and `fps.ps1` still name sitting **b** and the old
receipt; do not run those unchanged. This sheet supersedes their parameters.

Receipt: `docs/evidence/camera-ready-fractional-20260928/review-v3.json`, SHA256
`3e9bea22084523b8b11f5908b32094e9e716d3f202ba12591bd335e77cca8ec6`.
`freeze.json` pins the sitting-checkout source and unchanged completed FPS
runtime. Sitting c's game-absent desktop-session preflight reached the focus
gate and refused before capture/pad construction; that unchanged driver-path
evidence is reused, not rerun for d. It does not qualify live capture/HUD.
V3 has 95 owner and 95 reviewer tests, plus the reviewer's 468-case probe with
no beyond-bound move accepted. V2 and earlier receipts are stale.

Only the lead operates the desktop. No worker needs to run concurrently. No
training, decoding or competing inference during the sitting; stop even light
analysis for FPS. No learned-policy block. Focal is unknown, so no pitch or
short-pulse blocks. Native video must count turns before a yaw candidate is
accepted. A refusal is a result, not permission to lower thresholds or retry.

## 1. Arrival and actual sitting values

James opens the game; monitor on, Steam Input disabled. Lead arrives using
`reenter.py`, with no hand-posing. Run these **in the interactive desktop
session through the existing C:/desk job bridge**, never in session 0:

```powershell
Set-Location C:/Users/volpe/repos/rivals-agent
$camPython = 'C:/Users/volpe/.venvs/rivals-live-cu128/Scripts/python.exe'
uv run --no-project --python $camPython python scripts/capture.py preflight
uv run --no-project --python $camPython python scripts/reenter.py
# Inspect the arrival result; stop if reenter exits nonzero.
uv run --no-project --python $camPython python scripts/l4_practice_settings.py cooldowns-off
```

Execute one command and inspect its result before the next. Confirm alt account,
Spider-Man, H/V 247/124, actual curve/assist settings, normal cooldowns, visible
FPS counter, and the actual build. The arrival view must have **textured scenery
to the right, throughout the approximately 50-degree prime turn**. A flat wall
in that direction is unsuitable: the unchanged prime analyzer still refuses
the sitting-c yaw-01s pair. Do not infer suitability merely because the initial
view is textured. Do not hand-steer a better pose; if arrival is unsuitable,
end the attempt and report it.

After settings/recording setup, perform the established guarded **move-and-attack
refresh immediately before launching yaw-01** (and each later closed block),
then close that pad. Arrival's earlier movement does not replace this step.
The refresh can change the view; re-check that the post-refresh view and the
prime's rightward path remain textured, level and bot-free. Do not refresh while
the measurement process owns the pad. Sitting c's first attempt dropped for
inactivity after this step was skipped.

Start native OBS recording. Set `$camVideo` to that exact new recording path
(do not select the newest file automatically or reuse yesterday's path).
Use this setup prefix in **each desktop launch job**; C:/desk jobs do not share
PowerShell variables:

```powershell
$ErrorActionPreference = 'Stop'
Set-Location C:/Users/volpe/repos/rivals-agent
$camPython = 'C:/Users/volpe/.venvs/rivals-live-cu128/Scripts/python.exe'
$uv = 'C:/Users/volpe/AppData/Local/Programs/Python/Python311/Scripts/uv.exe'
$camSitting = 'alt-cam-20260928d'
$camRoot = "C:/Users/volpe/repos/rivals-agent/data/calibration/$camSitting"
New-Item -ItemType Directory -Force $camRoot | Out-Null
$game = @(Get-Process Marvel-Win64-Shipping -ErrorAction Stop)
if ($game.Count -ne 1) { throw 'Need exactly one actual game PID' }
$camGamePid = $game[0].Id
$camVideo = 'REPLACE_WITH_CURRENT_NATIVE_OBS_PATH'
if ($camVideo -eq 'REPLACE_WITH_CURRENT_NATIVE_OBS_PATH') { throw 'Set actual recording reference first' }
$camReceipt = 'docs/evidence/camera-ready-fractional-20260928/review-v3.json'
$common = @('run','--no-project','--python',$camPython,'python','scripts/measure_camera_turns.py',
    '--live','--review-receipt',$camReceipt,'--game-pid',"$camGamePid",'--sitting',$camSitting,
    '--recording-ref',('"' + $camVideo + '"'),'--scope-seconds','180','--seconds','20')
```

Do not run the launch below until the game is foreground and all keys released.
`Start-Process` must stay hidden, so it does not steal game focus.

## 2. First yaw block, then conditional continuation

Append this to the setup prefix for **yaw-01 only**:

```powershell
$block = 'yaw-01'
$deflections = @('.45','-.45','.1','-.1')
if (Test-Path -LiteralPath "$camRoot/$block") { throw 'Output exists; no overwrite/retry' }
$camArgs = $common + @('--deflections') + $deflections + @('--output',"$camRoot/$block")
$camJob = Start-Process -FilePath $uv -ArgumentList $camArgs -WorkingDirectory C:/Users/volpe/repos/rivals-agent -WindowStyle Hidden -PassThru -RedirectStandardOutput "$camRoot/$block.stdout.log" -RedirectStandardError "$camRoot/$block.stderr.log"
"camera pid=$($camJob.Id), game pid=$camGamePid, output=$camRoot/$block"
```

1. Inspect `yaw-01/ready-attach.png`, its `-frame.json`, and `ready-attach.json`:
   level, bot-free range view with texture to the right of the prime turn,
   no idle banner or device toast. There is no pad
   during this gate. Approve only this inspected token.
2. Attach performs the reviewed +.45 rx /300 ms prime immediately, checks its
   response, then holds neutral for five seconds. Prime/settle are excluded.
3. Inspect the **new** `ready-0` image after the approximately 50-degree turn:
   still level and bot-free, no Switching Devices or Controller Connected
   toast, no idle warning. A fading toast is not accepted. Approve the new token.
4. For each next `ready-N`, inspect the new image and previous segment record
   before approving. Check expected continuous rotation in native video,
   unobstructed panorama, no pitch clamp/collision, no repeated half-turn alias.

If yaw-01 refuses, **stop camera work; do not run yaw-02..04**. Keep the exact
refusal evidence. Otherwise the lead may continue one block at a time, using
the same setup/launch code and these exact two replacement assignments:

```powershell
# yaw-02, only after yaw-01 succeeds and its pad is closed:
$block = 'yaw-02'; $deflections = @('.2','-.2','.3','-.3')
# yaw-03, only after yaw-02 succeeds and its pad is closed:
$block = 'yaw-03'; $deflections = @('.6','-.6')
# yaw-04 LAST, only after yaw-03 succeeds and its pad is closed:
$block = 'yaw-04'; $deflections = @('.8','-.8','1','-1')
```

These are alternatives for separate jobs, not a batch. Perform the established
move-and-attack activity refresh between closed blocks, then re-inspect the
new arrival view without hand-posing. Never keep alive while measurement owns
the pad. Each block caps at 180 s. Stop on focus/HUD/idle/key/deadline refusal.

## 3. Token write, from remote/agent shell without PC keypresses

After inspecting the current image, run this once per approval. First index is
`attach`, then `0`, `1`, `2`, `3` (yaw-03 ends at `1`). Never preapprove:

```powershell
$tokenBlock = 'C:/Users/volpe/repos/rivals-agent/data/calibration/alt-cam-20260928d/yaw-01'
$tokenIndex = 'attach' # replace only with the image just inspected
$ready = Get-Content -LiteralPath "$tokenBlock/ready-$tokenIndex.json" -Raw | ConvertFrom-Json
$final = "$tokenBlock/continue-$tokenIndex.json"
if (Test-Path -LiteralPath $final) { throw 'Token marker already exists' }
$temporary = "$tokenBlock/continue-$tokenIndex.$([guid]::NewGuid().ToString('N')).tmp"
[IO.File]::WriteAllText($temporary, (@{token=$ready.token} | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
Move-Item -LiteralPath $temporary -Destination $final
```

## 4. Optional FPS A/B/A after camera closure

The previous sitting completed FPS A/B/A: median 240/240/240 at cap 240, so the
median visible loss was 0% but uncapped headroom cost remains unknown. A repeat
is at the lead's discretion. It uses no pad or camera map, and lasts 120 s plus
at most 10 s bounded startup. Refresh activity beforehand and hold one fixed
view throughout. Keep resolution, OBS and cap unchanged.

Create `data/calibration/alt-cam-20260928d/settings-observed.json` from actual
observations. Required header is `binding_profile: james-alt-spiderman-20260926`,
`swing_mode: {automatic_swing:false, hold_to_swing:true}`, `cooldowns: normal`,
and the exact applicable `patch` line from `docs/spiderman-kit.md`. Record
observed versus carried-forward provenance and build. Do not blindly promote
sitting b's settings to new observations. The FPS loader validates this header
but consumes no calibration maps.

In a new desktop launch job, use the same setup prefix, then:

```powershell
$fpsCap = 240 # replace with ACTUAL configured cap; omit --fps-cap if uncapped
$fpsOutput = "$camRoot/inference-fps-aba"
if (Test-Path -LiteralPath $fpsOutput) { throw 'FPS output exists' }
$fpsArgs = @('run','--no-project','--python',$camPython,'python','scripts/measure_inference_fps.py',
    '--checkpoint','data/diagnostics/live-loop-fallback-20260927/model_nohud-seed0.pt',
    '--checkpoint-sha256','2d5183cba12913a36327e0a459ec0c0b2a1238d26a7df98f7823929af3129f18',
    '--support-json','docs/evidence/live-loop-fallback-20260927/support.json',
    '--settings-json',"$camRoot/settings-observed.json",'--preprocessor','compact-bgr',
    '--cpu-threads','2','--capture-hz','30','--device','cuda','--desktop-capture',
    '--game-pid',"$camGamePid",'--sitting',$camSitting,'--native-video',('"' + $camVideo + '"'),
    '--fps-cap',"$fpsCap",'--output',$fpsOutput)
$fpsJob = Start-Process -FilePath $uv -ArgumentList $fpsArgs -WorkingDirectory C:/Users/volpe/repos/rivals-agent -WindowStyle Hidden -PassThru -RedirectStandardOutput "$camRoot/fps.stdout.log" -RedirectStandardError "$camRoot/fps.stderr.log"
"FPS pid=$($fpsJob.Id), output=$fpsOutput"
```

No keep-alive, settings changes, GDI switch or other compute during A/B/A.
After closure inspect `result.json`; a partial run is not a complete comparison.
Retained 1 Hz overlay samples need offline manual annotation as before.

## Refusal evidence and accepted limits

Keep `failure.json`, `pose-refusal.json`, all named `refusal-*.png` and their
`*-frame.json`, events, and native video. `current` is now the **last analyzed**
frame; `terminal-unanalyzed` is separate if capture overran or analysis failed.
The metadata and failure record name which image belongs to the audit and which
triggered refusal. Encoding occurs after pad closure. For FPS keep
`startup-refusal.json` and its named images when present.

Row-1 support remains fragile and can safely refuse; recurring refusals are the
next liveness investigation. Unmeasurable motion may take a bounded neutral
quality wait. Whole-band correlation misses some local changes, so the lead's
bot-free inspection is still necessary. No threshold changes during this run.
V3 scores confidence at fractional alignment without changing raw displacement
bounds. Extra accepted patches can make near-boundary shifts refuse more
conservatively. The prime-response analyzer is unchanged; texture/coherence
refusals there remain valid stops.
No yaw-rate, focal or complete camera-map acceptance is implied by the freeze.

Planned time: arrival/settings/recording about 5 minutes, yaw-01 up to 3 minutes;
only if successful, up to 9 more minutes for yaw-02..04 plus brief closed-pad
activity checks, then optional FPS about 2 minutes. Refusal ends that attempt.
