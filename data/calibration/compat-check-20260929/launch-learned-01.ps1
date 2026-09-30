param(
    [ValidateSet('A', 'B')][string]$Run = 'A',
    [string]$PolicyBundle = 'D:/rivals-policy/bundles/bc2-mix-s1',
    [string]$ObsVideo = ''
)
# Private closed-loop test after compat run-05, not a demo (James/lead, 2026-09-30).
# Pure BC2 expert-mix policy; run A uses full yaw, run B uses half yaw.
# Lead launches only after the quick safety read and sitting grant.
# Spider-Man in Practice Range near Galacta bots; crosshair between bots, slight downward look.
# Steam Input disabled, alt controller sensitivities 247 horizontal / 124 vertical.
# Start OBS session recording first; optionally supply -ObsVideo with its native MKV path.
# Native frames and prediction/pad/timing rows are also recorded in learned-01/.
$ErrorActionPreference = 'Stop'
Set-Location C:/Users/volpe/repos/rivals-agent
$learnedUv = 'C:/Users/volpe/AppData/Local/Programs/Python/Python311/Scripts/uv.exe'
$learnedPython = 'C:/Users/volpe/.venvs/rivals-live-cu128/Scripts/python.exe'
if (-not (Test-Path -LiteralPath (Join-Path $PolicyBundle 'bundle.json'))) {
    throw 'Policy bundle is missing; do not launch'
}
& $learnedUv run --no-project --python $learnedPython python scripts/capture.py preflight
if ($LASTEXITCODE -ne 0) { throw 'Capture preflight refused; do not launch' }
$learnedGames = @(Get-Process -Name 'Marvel-Win64-Shipping' -ErrorAction Stop)
if ($learnedGames.Count -ne 1) { throw 'Expected exactly one game process; inspect before launch' }
$learnedGamePid = [int]$learnedGames[0].Id
$learnedSitting = 'C:/Users/volpe/repos/rivals-agent/data/calibration/compat-check-20260929'
$learnedName = 'learned-01-' + $Run.ToLowerInvariant()
$learnedYawScale = if ($Run -eq 'A') { '1.0' } else { '0.5' }
$learnedOut = Join-Path $learnedSitting $learnedName
$learnedStdout = Join-Path $learnedSitting ($learnedName + '.stdout.log')
$learnedStderr = Join-Path $learnedSitting ($learnedName + '.stderr.log')
foreach ($learnedPath in @($learnedOut, $learnedStdout, $learnedStderr)) {
    if (Test-Path -LiteralPath $learnedPath) { throw 'Attempt path exists; preserve it and return to the lead' }
}
$learnedArguments = @(
    'run', '--no-project', '--python', $learnedPython, 'python', '-m', 'agent.learned_runner',
    '--live', '--policy-bundle', ('"' + $PolicyBundle + '"'), '--device', 'cuda',
    '--camera-settings-match', 'alt-247-124', '--game-pid', "$learnedGamePid",
    '--max-s', '60', '--decision-hz', '15', '--yaw-scale', $learnedYawScale, '--save-fps', '10', '--out', $learnedOut
)
if ($ObsVideo) { $learnedArguments += @('--obs-video', ('"' + $ObsVideo + '"')) }
$learnedProcess = Start-Process -FilePath $learnedUv -ArgumentList $learnedArguments -WorkingDirectory 'C:/Users/volpe/repos/rivals-agent' -WindowStyle Hidden -PassThru -RedirectStandardOutput $learnedStdout -RedirectStandardError $learnedStderr
"learned process=$($learnedProcess.Id) game=$learnedGamePid output=$learnedOut"
