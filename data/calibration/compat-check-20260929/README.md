# Bounded camera compatibility sitting ? 2026-09-29

**Procedure only; not a record of an executed sitting.** Lead owns the grant,
desktop launch and result. Current v4/v5 runtime landed in
`29f38730e836eb48782d5054e1ccf9aee1fe86cf`.
[Independent v5 LAND receipt](../../../docs/evidence/live-loop-compat-20260930-v5/review-v5-receipt.json):
SHA256 `0090dba729aef7a3be6f66146a9d6a03643b75517f3230172ad86fc38dcc7150`.
The receipt covers code only. Obtain the lead's explicit sitting grant before
launch. No whole-map acceptance, combat trial or live success is implied.

## Run-03 (procedure only, 2026-09-30)

Repeat the run-02 arrangement whose **placement preflight passed**, not a
completed compatibility result: crosshair halfway between the two Galacta bots,
with a slight downward look. Keep the left bot above y=0.39 of frame height as
preferred in step 2 below, both bots visible, and each more than 48 native px
to its side of the crosshair at 2560 width. James makes this setup before saying
ready; no agent repositioning is added. Confirm the intended bots on the saved
fresh placement screenshot, then keep hands off and preserve game focus.

The common hash, capture, current-PID, settings, OBS and placement preflights
below apply immediately before the lead's hidden run-03 launch. Use fresh
run-03, run-03-placement and stdout/stderr names. Preserve run-01/run-02 and their
recordings; if any run-03 artifact already exists, stop rather than overwriting
it or automatically selecting a retry name. This procedure is not a sitting grant.

Current commands use exact measured yaw knots 0.1/0.2/0.3 for 50 ms, and pitch
0.2 for 100 ms above 39 px vertical error at 1280 scale, returning to 0.1/50 ms
near the deadband. Freshness and total bounds are unchanged. The larger pitch
response is **not measured yet**; the 2x/4x gains in the v4 replay are hypotheses.
Run-03 must retain and report its actual coarse-pitch response:

- For every coarse pitch pulse, identify its target and fresh proof_t observation,
  sign, scheduled hold, and subsequent response observation for that same id.
  Report the signed vertical pixel reduction at 1280 scale and observed delay,
  with native proof/response boxes and retained-image links. The earlier before
  PNG is contextual evidence; it is not necessarily the proof_t frame.
- Summarize coarse/fine pitch pulse counts, observed pixel changes and delays,
  per-side convergence times, actual reserved input and retention/alias timings.
  If no coarse pulse was sent, explicitly report that its response remains unmeasured.
  Do not convert pixel response into a pitch angular rate or guaranteed latency.

**Run-03 pass:** apply the complete pass criteria below to run-03/result.json,
including both axes and both sides. The lead verifies that observed coarse-pitch
responses, if used, reduce the intended target's vertical error and meet the
existing response rule (at least 2 px at 1280 scale within its 750 ms response
window after the required neutral wait). There is no new required 2x/4x gain;
measure the actual value. Missing/opposite response, failure to finish either
axis/side within budget, missing evidence or unconfirmed release is a stop.
No automatic retry follows a stop. The lead records the outcome in the sitting
record and VUH-1319, linking the retained run evidence.

## What James does

1. On supedupsilly, enter the **Practice Range** as Spider-Man on the alt
   profile. Keep the monitor on and Steam Input disabled for Marvel Rivals.
   Confirm controller sensitivity H/V **247/124**, with the measured profile's
   other settings unchanged. Tell the lead if any settings changed; do not
   silently declare a match. This tool neither navigates menus nor changes settings.
2. Put bots in view. The actual sequence needs a visible bot left of the
   crosshair, then a visible bot to the right after the first alignment.
   The LEFT target must sit outside the measured hero-region exclusion:
   x < 0.27 of frame width (x < 691.2 at 2560, more than about 590 px left
   of centre), or above y = 0.39 of frame height (y < 561.6 at 1440).
   **Prefer the left target above y = 0.39**: a far-left target at ordinary
   height can enter the excluded region while yaw converges. The right target
   stays right of the crosshair as before. Each acquisition needs more than 24 horizontal pixels
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
$compatOut = Join-Path $compatSitting 'run-03'
$compatPlacementOut = Join-Path $compatSitting 'run-03-placement'
$compatStdout = Join-Path $compatSitting 'run-03.stdout.log'
$compatStderr = Join-Path $compatSitting 'run-03.stderr.log'
if ((Test-Path -LiteralPath $compatOut) -or (Test-Path -LiteralPath $compatPlacementOut) -or (Test-Path -LiteralPath $compatStdout) -or (Test-Path -LiteralPath $compatStderr)) {
    throw 'Attempt paths already exist; preserve them and return to the lead'
}
# run-01/run-02 remain intact. This procedure grants no retry.
& $compatUv run --no-project --python $compatPython python docs/evidence/live-loop-compat-20260929-v3/placement_preflight.py --live-screenshot --game-pid $compatGamePid --out $compatPlacementOut
if ($LASTEXITCODE -ne 0) { throw 'Finder placement preflight refused; do not launch' }
# Exact child invocation: python -m agent.loop --compat --live --camera-map alt-247-124 --camera-settings-match alt-247-124 --game-pid CURRENT_PID --max-s 60 --out RUN_03
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
The placement check captures a fresh native screenshot without pad input and
requires the native finder to report an eligible LEFT and RIGHT enemy, range
HUD, and no idle warning. The lead inspects the saved placement.png and
placement.json to confirm the intended Galacta bots, then launches without
repositioning or changing focus. Movement invalidates this preflight; an old
screenshot or offline --frame result cannot satisfy it. One screenshot does
not establish tracker identity or guarantee continued detection; the live
runner still requires fresh guarded observations. The hero exclusion stays
unchanged. See the [v3 LAND receipt](../../../docs/evidence/live-loop-compat-20260929-v3/review-v3-receipt.json)
and [support-only cleanup note](../../../docs/evidence/live-loop-compat-20260929-v3/support-only-cleanup.md).
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
single-axis yaw pulse (up to +/-0.3) has a 50 ms window; pitch uses +/-0.1 for
50 ms or coarse +/-0.2 for 100 ms, followed by neutral observation;
observed response must arrive within 750 ms. Native actuator release timing
remains subject to scheduling/device behavior; a blocked call can delay process
exit, so do not infer completion merely from elapsed wall time.

**Pass:** run-03/result.json reports result="passed", completed_sides=[-1,1],
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

Retain run-03/result.json, native acquisition/pre-pulse/response/convergence/stop
PNGs, stdout/stderr, original OBS video and logger. The PNG labeled before is
retained before a new command-authorizing observation; proof_t in the pulse
trace identifies that newer frame. Report observed response delays as evidence,
not guaranteed latency or pitch degrees. Focal, pitch angular rates, latency
and interpolation remain holes; passing this bounded check does not accept
an ordinary whole-camera controller map.

## First learned-policy sitting (2026-09-30)

**Private closed-loop test after compat run-05, not a demo (James/lead,
2026-09-30).** The lead selected `bc2-bs8-hybrid`: BC2 camera with the old
buttons, whose held-out yaw now beats zero. These commands authorize no sitting
themselves.

The lead launches this only after the quick live-input safety read and James's
sitting grant. Use Spider-Man in the Practice Range near the Galacta bots, with
the crosshair between them and a slight downward look. Keep Steam Input disabled
and the alt controller settings at horizontal 247 / vertical 124. Start OBS
recording before launch; keep that original native video. The runner does not
navigate, choose a hero or start OBS.

Invoke `launch-learned-01.ps1 -Run A` for a maximum of 60 seconds with learned
yaw at `--yaw-scale 1.0`. After inspecting that result and arranging the next sitting,
invoke `launch-learned-01.ps1 -Run B` for another independently launched maximum
of 60 seconds with `--yaw-scale 0.5`. Each can take `-ObsVideo '<native MKV path>'`
to record the operator-supplied video path. Outputs are `learned-01-a/` and
`learned-01-b/`, with separate stdout/stderr; existing attempts are refused.

The bundle defaults to `D:/rivals-policy/bundles/bc2-bs8-hybrid` and can be changed
with `-PolicyBundle`. Real policy/readers/finder warm-up happens before attach,
then the recurrent policy resets. Both compat run-05 and learned runs opt into
one guarded attach opener: LY=0.25 for at most 50 ms, with no camera, trigger or
button, then neutral and a fresh range observation. This cancels the measured
fresh-pad left drift before target acquisition or learned input. It is logged
separately from the compatibility camera-pulse caps; their 2 s / 40-pulse caps
remain unchanged. Inference uses one latest-frame worker;
capture and guarded input remain on the control thread. Native frames at up to
10 Hz, per-tick predictions, raw/scaled yaw, masked actions, sent pad snapshots,
request expiry/release times, inference/queue timing and the stop frame are
retained alongside `result.json`. OBS remains the native session-video owner.

Yaw uses measured signed knots, capped at |rx|=0.45; A/B compares full and half
learned yaw in this private test. Pitch goes through an explicitly **unmeasured**
rate approximation (signed yaw rate times 124/247), capped at |ry|=0.2. Each
axis pulse is at most 1/60 second; action-only leases are at most 100 ms. Every
input request still expires 100 ms after its original policy frame. Ult,
team-up and GOH-targeting remain masked. No calibrated pitch accuracy or
guaranteed camera latency is claimed.

Completion means reaching the configured deadline with a confirmed pad close
and usable recording. Bad play is permitted; it is not a learned-policy success
claim. Any focus/HUD/idle/takeover/IO failure stops and releases input. Stale
decisions are discarded with neutral input and re-observed, never given a wider
freshness window. Preserve all artifacts and return to the lead; do not retry
or navigate automatically. Inspect the actual play and recording before a
second sitting or any policy-quality claim.
