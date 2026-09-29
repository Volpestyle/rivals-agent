# Bounded camera compatibility sitting ? 2026-09-29

**Procedure only; not a record of an executed sitting.** Lead owns the grant,
desktop launch and result. Code landed in
`6f59736ffc704b6f6fd5fcb4e8dec2911bd8c202`.
[Independent v2 LAND receipt](../../../docs/evidence/live-loop-compat-20260929-v2/review-v2-receipt.json):
SHA256 `6873541ec9607368faa7707d049d52d74b59ab5f5a10166dde3efa3412994b02`.
The receipt covers code only. Obtain the lead's explicit sitting grant before
launch. No whole-map acceptance, combat trial or live success is implied.

## What James does

1. On supedupsilly, enter the **Practice Range** as Spider-Man on the alt
   profile. Keep the monitor on and Steam Input disabled for Marvel Rivals.
   Confirm controller sensitivity H/V **247/124**, with the measured profile's
   other settings unchanged. Tell the lead if any settings changed; do not
   silently declare a match. This tool neither navigates menus nor changes settings.
2. Put bots in view. The actual sequence needs a visible bot left of the
   crosshair, then a visible bot to the right after the first alignment.
   A stationary pair, initially straddling the crosshair, is the useful setup;
   keep offsets modest. Each acquisition needs more than 24 horizontal pixels
   at 1280-width scale (48 pixels at 2560). A single centered bot cannot pass
   both phases. If the needed targets are absent, fix the setup before launch.
   There is no blind search or automatic repositioning.
3. Start OBS recording with the existing native 2560x1440/120 fps profile and
   input logger. Confirm recording is active; tell the lead the exact MKV path.
   Return focus to the game, release all keys/buttons, and say ready. Keep
   hands off the keyboard and mouse during the check. Do not press a key to
   acknowledge a running check. Any key or mouse button deliberately stops it.
4. Wait for the lead to confirm that the process ended and input is released.
   Then stop OBS. Keep the original video and logger files. If something looks
   wrong, take over immediately; the attempt is a stop, not an automatic retry.

## Lead preflight and exact launch

One operator controls the desktop. Execute the following in the PC's existing
**desktop-session** job route (C:/desk), with the game already foreground and
James hands-off. Do not run capture/pad code in plain SSH or by focusing a
terminal over the game. This block is a procedure to execute only after the
grant; it was not executed when this README was written.

Use the existing live interpreter; --no-project avoids changing its installed
capture/pad dependencies. Read-only hash preflight, immediately before launch:

```powershell
Set-Location C:/Users/volpe/repos/rivals-agent
$compatUv = 'C:/Users/volpe/AppData/Local/Programs/Python/Python311/Scripts/uv.exe'
$compatPython = 'C:/Users/volpe/.venvs/rivals-live-cu128/Scripts/python.exe'
& $compatUv run --no-project --python $compatPython python docs/evidence/live-loop-compat-20260929-v2/preflight_hashes.py
if ($LASTEXITCODE -ne 0) { throw 'Hash preflight refused; do not launch' }
```

Expected map hash:
`0e062286bd942aad776d719cd5841321b83773ae5b9e4b74ae8443b8795709d9`.
Expected scoped acceptance-record hash:
`a55979781567808b2b490032759d76e64e6b34fccb4594594c4e50c81a5df7df`.
The loader also verifies four evidence pins. These identify actual CRLF runtime
bytes. A mismatch is a STOP: report it, without reformatting or repinning to
make the check pass. Repeat preflight if any relevant file changes afterwards.
Git stores LF for some dependencies; their reviewed Windows checkout bytes
were verified at landing. Do not substitute a Git blob hash for a runtime pin.

In that same desktop session, confirm capture and select the current game PID;
never reuse a PID from a previous sitting. Then launch the exact compatibility
command below as a hidden process so the game retains focus:

```powershell
& $compatUv run --no-project --python $compatPython python scripts/capture.py preflight
if ($LASTEXITCODE -ne 0) { throw 'Capture preflight refused; do not launch' }
$compatGames = @(Get-Process -Name 'Marvel-Win64-Shipping' -ErrorAction Stop)
if ($compatGames.Count -ne 1) { throw 'Expected exactly one game process; inspect before launch' }
$compatGamePid = [int]$compatGames[0].Id
$compatSitting = 'C:/Users/volpe/repos/rivals-agent/data/calibration/compat-check-20260929'
$compatOut = Join-Path $compatSitting 'run-01'
$compatStdout = Join-Path $compatSitting 'run-01.stdout.log'
$compatStderr = Join-Path $compatSitting 'run-01.stderr.log'
if ((Test-Path -LiteralPath $compatOut) -or (Test-Path -LiteralPath $compatStdout) -or (Test-Path -LiteralPath $compatStderr)) {
    throw 'Attempt paths already exist; preserve them and return to the lead'
}
# Exact child invocation: python -m agent.loop --compat --live --camera-map alt-247-124 --camera-settings-match alt-247-124 --game-pid CURRENT_PID --max-s 60 --out RUN_01
$compatArguments = @(
    'run', '--no-project', '--python', $compatPython, 'python', '-m', 'agent.loop',
    '--compat', '--live', '--camera-map', 'alt-247-124',
    '--camera-settings-match', 'alt-247-124', '--game-pid', "$compatGamePid",
    '--max-s', '60', '--out', $compatOut
)
$compatProcess = Start-Process -FilePath $compatUv -ArgumentList $compatArguments -WorkingDirectory 'C:/Users/volpe/repos/rivals-agent' -WindowStyle Hidden -PassThru -RedirectStandardOutput $compatStdout -RedirectStandardError $compatStderr
"compat process=$($compatProcess.Id) game=$compatGamePid output=$compatOut"
```

The profile/settings declaration is explicit and operator supplied; hash
preflight alone does not verify the in-game settings. The launch arguments
contain no startup, brain, attack, movement, scoreboard or collection mode.
Do not add throwaway movement or a different input path if attach or response
fails. Observe the owned process/logs without changing game focus. Record the
actual game PID, build, OBS path, settings declaration, start/end times and
exit code in a new sitting result record beside this procedure. Do not rewrite
this procedure to masquerade as the execution record.

## Expected duration and outcome

One attempt: **at most 60 seconds of live scope**, often shorter if alignment
succeeds or a guard refuses. Allow roughly 2-3 minutes including human setup
and the lead's result inspection. This is not a repeated-trial campaign.
Each side has up to 10 seconds to acquire and 15 seconds to converge. The
entire attempt permits at most 40 pulses / 2 seconds of reserved input. Each
single-axis +/-0.1 pulse has a 50 ms window followed by neutral observation;
observed response must arrive within 750 ms. Native actuator release timing
remains subject to scheduling/device behavior; a blocked call can delay process
exit, so do not infer completion merely from elapsed wall time.

**Pass:** run-01/result.json reports result="passed", completed_sides=[-1,1],
no safety stop, and confirmed close_returned. Both locked targets converged
within +/-12 pixels per axis at 1280-width scale (24 at 2560) on three fresh
observations, within every budget. The lead also inspects retained native PNGs
and video for the intended targets and behavior before accepting compatibility.

**Stop:** hash/settings/focus/attachment refusal; missing or ambiguous target;
stale/invalid frame; range HUD loss; idle warning; any key or mouse button;
missing or opposite pulse response; phase/input/deadline budget; or IO failure.
A nonzero exit, missing result, unexpected exception or unconfirmed release is
not a pass. Stop input, preserve all artifacts and return to the lead. No retry,
menu navigation, fallback or fresh output name is automatic.

Retain run-01/result.json, native acquisition/pre-pulse/response/convergence
PNGs, stdout/stderr, original OBS video and logger. The PNG labeled before is
retained before a new command-authorizing observation; proof_t in the pulse
trace identifies that newer frame. Report observed response delays as evidence,
not guaranteed latency or pitch degrees. Focal, pitch angular rates, latency
and interpolation remain holes; passing this bounded check does not accept
an ordinary whole-camera controller map.
