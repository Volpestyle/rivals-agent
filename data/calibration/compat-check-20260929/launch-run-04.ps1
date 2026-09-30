$ErrorActionPreference = 'Stop'
Set-Location C:/Users/volpe/repos/rivals-agent
$compatUv = 'C:/Users/volpe/AppData/Local/Programs/Python/Python311/Scripts/uv.exe'
$compatPython = 'C:/Users/volpe/.venvs/rivals-live-cu128/Scripts/python.exe'
& $compatUv run --no-project --python $compatPython python docs/evidence/live-loop-compat-20260929-v2/preflight_hashes.py
if ($LASTEXITCODE -ne 0) { throw 'Hash preflight refused; do not launch' }
& $compatUv run --no-project --python $compatPython python scripts/capture.py preflight
if ($LASTEXITCODE -ne 0) { throw 'Capture preflight refused; do not launch' }
$compatGames = @(Get-Process -Name 'Marvel-Win64-Shipping' -ErrorAction Stop)
if ($compatGames.Count -ne 1) { throw 'Expected exactly one game process; inspect before launch' }
$compatGamePid = [int]$compatGames[0].Id
$compatSitting = 'C:/Users/volpe/repos/rivals-agent/data/calibration/compat-check-20260929'
$compatOut = Join-Path $compatSitting 'run-04'
$compatStdout = Join-Path $compatSitting 'run-04.stdout.log'
$compatStderr = Join-Path $compatSitting 'run-04.stderr.log'
if ((Test-Path -LiteralPath $compatOut) -or (Test-Path -LiteralPath $compatStdout) -or (Test-Path -LiteralPath $compatStderr)) {
    throw 'Attempt paths already exist; preserve them and return to the lead'
}
& $compatUv run --no-project --python $compatPython python docs/evidence/live-loop-compat-20260929-v3/placement_preflight.py --live-screenshot --game-pid $compatGamePid --out (Join-Path $compatSitting 'run-04-placement')
if ($LASTEXITCODE -ne 0) { throw 'Finder placement preflight refused; do not launch' }
$compatArguments = @(
    'run', '--no-project', '--python', $compatPython, 'python', '-m', 'agent.loop',
    '--compat', '--live', '--camera-map', 'alt-247-124',
    '--camera-settings-match', 'alt-247-124', '--game-pid', "$compatGamePid",
    '--max-s', '60', '--out', $compatOut
)
$compatProcess = Start-Process -FilePath $compatUv -ArgumentList $compatArguments -WorkingDirectory 'C:/Users/volpe/repos/rivals-agent' -WindowStyle Hidden -PassThru -RedirectStandardOutput $compatStdout -RedirectStandardError $compatStderr
"compat process=$($compatProcess.Id) game=$compatGamePid output=$compatOut"
