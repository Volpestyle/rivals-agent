param(
    [Parameter(Mandatory = $true)][string]$Out,
    [string]$BaseBundle = 'D:/rivals-policy/bundles/bc2-mix399-s0',
    [int]$Episodes = 20,
    [double]$EpisodeSeconds = 45,
    [double]$SettleSeconds = 1.5,
    [int]$BcEvery = 0,
    [switch]$NoReset
)
# Lead only, after the quick safety read AND neutral-only takeover verification.
# One BC control then RL, 15 Hz; model/readers/capture persist. Each reset <=30s;
# each episode+settle <=60s under a fresh guarded scope. Human takeover is latched
# across the gaps. Background AWR runs only within this supervised sitting.
$ErrorActionPreference = 'Stop'
Set-Location C:/Users/volpe/repos/rivals-agent
$persistentUv = 'C:/Users/volpe/AppData/Local/Programs/Python/Python311/Scripts/uv.exe'
$persistentPython = 'C:/Users/volpe/.venvs/rivals-live-cu128/Scripts/python.exe'
if (Test-Path -LiteralPath $Out) { throw 'Output exists; preserve it' }
if (-not (Test-Path -LiteralPath (Join-Path $BaseBundle 'bundle.json'))) { throw 'Bundle missing' }
if ($Episodes -lt 1 -or $Episodes -gt 20 -or $EpisodeSeconds -le 0 -or $SettleSeconds -lt 0 -or ($EpisodeSeconds + $SettleSeconds) -gt 60 -or $BcEvery -lt 0) { throw 'Invalid bounded sitting arguments' }
& $persistentUv run --no-project --python $persistentPython python scripts/capture.py preflight --min-fps 60 --attempts 3
if ($LASTEXITCODE -ne 0) { throw 'Capture preflight refused' }
$persistentGames = @(Get-Process -Name 'Marvel-Win64-Shipping' -ErrorAction Stop)
if ($persistentGames.Count -ne 1) { throw 'Expected one game process' }
$persistentArguments = @('run', '--no-project', '--python', $persistentPython, 'python', '-m', 'rl.online.persistent_sitting',
    '--live', '--game-pid', "$($persistentGames[0].Id)", '--camera-settings-match', 'alt-247-124',
    '--base-bundle', ('"' + $BaseBundle + '"'), '--out', ('"' + $Out + '"'),
    '--episodes', "$Episodes", '--episode-s', "$EpisodeSeconds", '--settle-s', "$SettleSeconds", '--bc-every', "$BcEvery")
if ($NoReset) { $persistentArguments += '--no-reset' }
foreach ($persistentSuffix in @('.stdout.log', '.stderr.log')) {
    $persistentLog = $Out + $persistentSuffix
    if (Test-Path -LiteralPath $persistentLog) { throw 'Log path exists; preserve it' }
}
$persistentProcess = Start-Process -FilePath $persistentUv -ArgumentList $persistentArguments -WorkingDirectory 'C:/Users/volpe/repos/rivals-agent' -WindowStyle Hidden -PassThru -RedirectStandardOutput ($Out + '.stdout.log') -RedirectStandardError ($Out + '.stderr.log')
"Persistent sitting process=$($persistentProcess.Id), output=$Out"
