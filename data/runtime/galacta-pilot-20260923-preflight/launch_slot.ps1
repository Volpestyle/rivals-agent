# One scheduled galacta-pilot-20260923 allocation, once. Adapted from the slot-3/slot-4 launchers of galacta-pilot-20260922.
# Runs as a C:\desk job (desktop session: Focus/Screenshot come from C:\desk\lib.ps1). -CheckOnly runs every pre-launch
# check, consumes nothing, sends nothing, and needs no desktop session.
#   . C:\desk\lib.ps1; & <this file> -Index 1 -GamePid <pid>
#   & <this file> -Index 1 -GamePid 0 -CheckOnly [-Preflight <dry-run dir>] [-LiveTree <dry-run clone>]
param([Parameter(Mandatory)][ValidateRange(1, 20)][int]$Index, [Parameter(Mandatory)][int]$GamePid, [switch]$CheckOnly,
      [string]$Preflight = 'C:\Users\volpe\repos\rivals-agent\data\runtime\galacta-pilot-20260923-preflight',
      [string]$LiveTree = 'C:\Users\volpe\repos\rivals-agent-live')
$ErrorActionPreference = 'Stop'
$repo = 'C:\Users\volpe\repos\rivals-agent'
$here = Join-Path $repo 'data\runtime\galacta-pilot-20260923-preflight'   # scripts and candidate.json
$pre = $Preflight                                                           # freeze, binding and slot outputs
$liveTree = $LiveTree
if (-not $CheckOnly -and ($pre -ne $here -or $liveTree -ne 'C:\Users\volpe\repos\rivals-agent-live')) { throw 'A launch uses the real preflight directory and live tree' }
$uv = 'C:\Users\volpe\AppData\Local\Programs\Python\Python311\Scripts\uv.exe'
$uvEnv = 'run --offline --no-project --python 3.11 --with dxcam --with vgamepad --with opencv-python-headless --with pillow --with torch==2.14.0'
$checks = [ordered]@{}

$candidate = Get-Content -LiteralPath (Join-Path $here 'candidate.json') -Raw | ConvertFrom-Json
$schedulePath = Join-Path $repo $candidate.schedule.path
$slot = (Get-Content -LiteralPath $schedulePath -Raw | ConvertFrom-Json).trials | Where-Object { $_.schedule_index -eq $Index }
$role = $slot.policy_role; $name = $slot.planned_run_name
$slotDir = Join-Path $pre ('slots\{0:D2}-{1}' -f $Index, $role)
$runDir = Join-Path $repo "data\l1\$name"

# Order and once-only: every earlier slot is consumed (run or refused), this one is not.
foreach ($i in @(1..$Index | Where-Object { $_ -lt $Index })) {          # 1..0 counts down in PowerShell
  if (-not (Get-ChildItem -Path (Join-Path $pre ('slots\{0:D2}-*\allocation-consumed.json' -f $i)) -ErrorAction SilentlyContinue)) { throw "Slot $i is not consumed: the schedule runs in order" }
}
if ((Test-Path -LiteralPath $runDir) -or (Test-Path -LiteralPath (Join-Path $slotDir 'allocation-consumed.json'))) { throw "Slot $Index already has artifacts: no replacement retry" }
$checks.order = "$($Index - 1) earlier slot(s) consumed; slot $Index unconsumed"

# The schedule, deployed bytes and live tree are the frozen ones.
$scope = Get-Content -LiteralPath (Join-Path $pre 'runtime-semantic-review.json') -Raw | ConvertFrom-Json
if ((Get-FileHash -LiteralPath $schedulePath).Hash.ToLower() -ne $scope.scope.schedule.sha256) { throw 'Schedule changed since the binding' }
$frozen = (Get-Content -LiteralPath (Join-Path $pre 'deployment-check.json') -Raw | ConvertFrom-Json).commit
if ((cmd /c "git -C $liveTree rev-parse HEAD 2>NUL") -ne $frozen -or (cmd /c "git -C $liveTree status --porcelain 2>NUL")) { throw 'Live tree moved or is dirty since the freeze' }
foreach ($m in @('controller-deployed.json', 'perception-deployed.json')) {
  $manifest = Get-Content -LiteralPath (Join-Path $pre $m) -Raw | ConvertFrom-Json
  foreach ($p in $manifest.files.PSObject.Properties) {
    if ((Get-FileHash -LiteralPath (Join-Path $liveTree $p.Name)).Hash.ToLower() -ne $p.Value.sha256) { throw ('Deployed bytes changed: ' + $p.Name) }
  }
}
$checks.deployed = "live $frozen, manifests match"
if ($role -eq 'learned') {
  $model = Join-Path $repo $candidate.checkpoint.path
  if ((Get-FileHash -LiteralPath $model).Hash.ToLower() -ne $candidate.checkpoint.sha256) { throw 'Checkpoint changed' }
  $loader = Get-Content -LiteralPath (Join-Path $pre 'loader-preflight.json') -Raw | ConvertFrom-Json
  $binding = (Get-FileHash -LiteralPath (Join-Path $pre 'deployment-binding.json')).Hash.ToLower()
  if (-not $loader.loaded -or $loader.controls_passed_wrongly.Count -or $loader.binding_sha256 -ne $binding) { throw 'Loader preflight missing or not for this binding' }
  if ($scope.scope.game_pid -ne $GamePid) { throw "Binding is for game PID $($scope.scope.game_pid), not ${GamePid}: re-issue (README, Re-issue)" }
  $checks.binding = "binding $binding, loader preflight passed"
}

# Machine state: game PID, CPU, no sibling decode, a monitor sink.
if ($GamePid -ne 0) {
  $game = Get-Process -Id $GamePid -ErrorAction Stop
  if ($game.ProcessName -ne 'Marvel-Win64-Shipping') { throw 'Game PID changed' }
  $checks.game = "PID $GamePid started $($game.StartTime.ToString('o'))"
}
$cpu = [math]::Round(((Get-Counter '\Processor(_Total)\% Processor Time' -SampleInterval 1 -MaxSamples 3).CounterSamples | Measure-Object CookedValue -Average).Average, 1)
$decoders = @(Get-Process -Name ffmpeg, ffprobe -ErrorAction SilentlyContinue)
if ($cpu -ge 60 -or $decoders.Count) { throw "CPU $cpu% or $($decoders.Count) ffmpeg/ffprobe running: wait for the lead's go" }
$monitors = @(Get-PnpDevice -Class Monitor -ErrorAction SilentlyContinue | Where-Object Present)
if (-not $monitors.Count) { throw 'No monitor Present: dxcam will deliver nothing (README checklist 1)' }
$checks.machine = "CPU $cpu%, no ffmpeg/ffprobe, $($monitors.Count) monitor(s) present"
if ($CheckOnly) { [pscustomobject]@{slot = $Index; role = $role; run = $name; checks = $checks; launched = $false} | ConvertTo-Json -Depth 4; return }

# Native stderr (uv's "Installed N packages") redirected in PowerShell 5.1 under ErrorAction Stop throws: merge it in cmd.
$pre_capture = cmd /c "$uv $uvEnv python $liveTree\scripts\capture.py preflight 2>&1" | Out-String
if ($LASTEXITCODE) { throw "capture preflight failed: $pre_capture" }
New-Item -ItemType Directory -Force $slotDir | Out-Null
Focus 'Marvel Rivals'
Screenshot (Join-Path $slotDir 'before.png')
@{slot = $Index; run = $name; policy = $role; consumed_utc = [DateTime]::UtcNow.ToString('o'); game_pid = $GamePid; checks = $checks
  binding_sha256 = $(if ($role -eq 'learned') { $binding } else { $null }); capture_preflight = $pre_capture.Trim()
  reason = 'predeclared galacta-pilot-20260923 allocation, once; preserve failure, no replacement'} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $slotDir 'allocation-consumed.json')
$video = Join-Path $slotDir "$role-native.mp4"
$clockBefore = [Diagnostics.Stopwatch]::GetTimestamp(); $wallBefore = [DateTime]::UtcNow.ToString('o')
$record = Start-Process -FilePath (Get-Command ffmpeg.exe).Source -WindowStyle Hidden -ArgumentList "-hide_banner -nostdin -f lavfi -i ddagrab=framerate=60 -c:v h264_nvenc -cq 20 -t 60 $video" -RedirectStandardError (Join-Path $slotDir "$role-record.log") -PassThru
@{video = $video; record_pid = $record.Id; launch_utc_before = $wallBefore; launch_utc_after = [DateTime]::UtcNow.ToString('o'); stopwatch_before = $clockBefore; stopwatch_after = [Diagnostics.Stopwatch]::GetTimestamp(); stopwatch_frequency = [Diagnostics.Stopwatch]::Frequency; video_loop_mapping_known = $false; command = 'ddagrab=framerate=60 -> h264_nvenc -cq20 -t60'} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $slotDir "$role-recorder.json")
$common = "--live --game-pid $GamePid --max-s 20 --reflex-hz 60 --decision-hz 10 --save-fps 10 --cooldowns normal --collect-episode --stop-on-feed --run $name"
if ($role -eq 'learned') {
  $loopArgs = "$uvEnv python $here\run_instrumented.py --thread-record $slotDir\actual-thread-settings.json --brain range-skill $common --range-checkpoint $model --range-sha256 $($candidate.checkpoint.sha256) --range-identity $pre\source-identity.json --range-runtime $pre\runtime-identity.json --range-deployment $pre\deployment-binding.json"
} else {
  $loopArgs = "$uvEnv python -m agent.loop --brain scripted $common"
}
$run = Start-Process -FilePath $uv -WorkingDirectory $liveTree -WindowStyle Hidden -ArgumentList $loopArgs -RedirectStandardOutput (Join-Path $slotDir "$role.log") -RedirectStandardError (Join-Path $slotDir "$role.err") -Wait -PassThru
@{exit_code = $run.ExitCode; ended_utc = [DateTime]::UtcNow.ToString('o'); original_record_pid = $record.Id; run = $runDir} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $slotDir 'launch-result.json')
Screenshot (Join-Path $slotDir 'after.png')
"slot $Index $role exit=$($run.ExitCode)"
if ($role -eq 'learned' -and (Test-Path -LiteralPath $runDir)) {
  cmd /c "$uv run --offline --no-project python -B $repo\data\benchmarks\galacta-pilot-20260923\fragment_accounting.py $runDir --out $slotDir\fragment-accounting.json >NUL 2>&1"
  if ($LASTEXITCODE -eq 3) { 'STOP: boundary anomaly, see fragment-accounting.json; hand back to the lead' } elseif ($LASTEXITCODE) { 'STOP: fragment accounting could not read the run' }
}
