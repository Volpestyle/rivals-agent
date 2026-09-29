# Authorized game-absent gate check. No focus, capture or input commands here.
$ErrorActionPreference = 'Stop'
Set-Location C:/Users/volpe/repos/rivals-agent
if (@(Get-Process Marvel* -ErrorAction SilentlyContinue).Count -ne 0) { throw 'Game present; do not run absent-game preflight' }
if (Get-Process -Id 2147483647 -ErrorAction SilentlyContinue) { throw 'Dry PID unexpectedly exists' }
$root = 'C:/Users/volpe/repos/rivals-agent/docs/evidence/live-loop-sitting-prep-20260928c'
$env:CUDA_VISIBLE_DEVICES = ''
$env:OMP_NUM_THREADS = '2'
$env:OPENBLAS_NUM_THREADS = '2'
$uv = 'C:/Users/volpe/AppData/Local/Programs/Python/Python311/Scripts/uv.exe'
$py = 'C:/Users/volpe/.venvs/rivals-live-cu128/Scripts/python.exe'
$argsDry = @('run','--no-project','--python',$py,'python','scripts/measure_camera_turns.py',
    '--live','--review-receipt','docs/evidence/camera-ready-revision-20260928/review-v2.json',
    '--game-pid','2147483647','--sitting','alt-cam-20260928c-dry-preflight',
    '--recording-ref','DRY_PREFLIGHT_NO_RECORDING','--scope-seconds','180',
    '--deflections','.45','-.45','.1','-.1','--seconds','20','--output',"$root/dry-preflight")
if (Test-Path -LiteralPath "$root/dry-preflight") { throw 'Dry output exists' }
$job = Start-Process -FilePath $uv -ArgumentList $argsDry -WorkingDirectory C:/Users/volpe/repos/rivals-agent -WindowStyle Hidden -PassThru -RedirectStandardOutput "$root/dry.stdout.log" -RedirectStandardError "$root/dry.stderr.log"
if (-not $job.WaitForExit(15000)) { throw "Dry preflight still running, owned PID $($job.Id); inspect before proceeding" }
$job.Refresh()
$exitCode = $job.ExitCode
$failure = Get-Content -LiteralPath "$root/dry-preflight/failure.json" -Raw | ConvertFrom-Json
if ($failure.error -ne "ValueError('game must already be focused')") { throw "Unexpected refusal: $($failure.error)" }
if ($null -ne $failure.report_timing) { throw 'Unexpected pad report timing object' }
if (Test-Path -LiteralPath "$root/dry-preflight/ready-attach.json") { throw 'Unexpected attach gate reached' }
$result = @{session_id=(Get-Process -Id $PID).SessionId; child_pid=$job.Id; child_exited=$job.HasExited; exit_code=$exitCode; expected_refusal=$failure.error; game_absent=$true; capture_opened=$false; pad_opened=$false; qualification='focus gate only; no range/HUD/capture qualification'; uv_arguments=$argsDry}
[IO.File]::WriteAllText("$root/dry-result.json", ($result | ConvertTo-Json -Depth 6), [Text.UTF8Encoding]::new($false))
$result | ConvertTo-Json -Depth 6
