param(
    [Parameter(Mandatory = $true)][string]$Out,
    [string]$BaseBundle = 'D:/rivals-policy/bundles/bc2-mix399-s0',
    [int]$Episodes = 20,
    [double]$EpisodeSeconds = 20,
    [double]$ExploreTemp = 1.0,
    [double]$OptionRate = 0.5,
    [double]$CamTemp = 1.0,
    [double]$TurnRate = 0.5,
    [double]$SettleSeconds = 1.5,
    [switch]$NoReset,
    [double]$YawScale = 1.0,
    [double]$DecisionHz = 15
)
# Online-RL sitting in the Practice Range (VUH-1321): frozen-BC and RL episodes alternate, 20 s each, with an AWR
# update after every RL episode (rl/online/sitting.py). Each episode is agent.learned_runner, unchanged, with sampled
# action gates (rl/online/explore.py). Stops at the first episode that ends for anything but its deadline; no retry.
# Lead launches only after the quick safety read and the sitting grant.
# Setup as for learned-01: Spider-Man in the Practice Range near the Galacta bots, crosshair between them, slight
# downward look; Steam Input disabled; alt controller sensitivities 247 horizontal / 124 vertical; OBS recording on.
$ErrorActionPreference = 'Stop'
Set-Location C:/Users/volpe/repos/rivals-agent
$rlUv = 'C:/Users/volpe/AppData/Local/Programs/Python/Python311/Scripts/uv.exe'
$rlPython = 'C:/Users/volpe/.venvs/rivals-live-cu128/Scripts/python.exe'
if (-not (Test-Path -LiteralPath (Join-Path $BaseBundle 'bundle.json'))) { throw 'Base bundle is missing; do not launch' }
if (Test-Path -LiteralPath $Out) { throw 'Sitting output exists; preserve it and return to the lead' }
# Bounded capture-rate check (scripts/capture.py, live-loop dee8c23): at least 60 fps within 3 attempts, else refuse.
& $rlUv run --no-project --python $rlPython python scripts/capture.py preflight --min-fps 60 --attempts 3
if ($LASTEXITCODE -ne 0) { throw 'Capture preflight refused (need 60 fps within 3 attempts); do not launch' }
$rlGames = @(Get-Process -Name 'Marvel-Win64-Shipping' -ErrorAction Stop)
if ($rlGames.Count -ne 1) { throw 'Expected exactly one game process; inspect before launch' }
$rlGamePid = [int]$rlGames[0].Id
$rlOthers = @(& nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader | Where-Object { $_ -match '(?i)python' })
foreach ($rlOther in $rlOthers) { Write-Warning "Other GPU client: $rlOther (policy latency and the between-episode update share the GPU)" }
$rlStdout = $Out + '.stdout.log'
$rlStderr = $Out + '.stderr.log'
foreach ($rlPath in @($rlStdout, $rlStderr)) { if (Test-Path -LiteralPath $rlPath) { throw 'Log path exists; preserve it' } }
$rlArguments = @(
    'run', '--no-project', '--python', $rlPython, 'python', '-m', 'rl.online.sitting',
    '--live', '--game-pid', "$rlGamePid", '--camera-settings-match', 'alt-247-124',
    '--base-bundle', ('"' + $BaseBundle + '"'), '--out', ('"' + $Out + '"'),
    '--episodes', "$Episodes", '--episode-s', "$EpisodeSeconds", '--explore-temp', "$ExploreTemp", '--option-rate', "$OptionRate", '--cam-temp', "$CamTemp", '--turn-rate', "$TurnRate",
    '--yaw-scale', "$YawScale", '--decision-hz', "$DecisionHz", '--device', 'cuda', '--settle-s', "$SettleSeconds"
)
if (-not $NoReset) { $rlArguments += '--reset' }   # the runner's integrated guarded reset before each episode
$rlProcess = Start-Process -FilePath $rlUv -ArgumentList $rlArguments -WorkingDirectory 'C:/Users/volpe/repos/rivals-agent' -WindowStyle Hidden -PassThru -RedirectStandardOutput $rlStdout -RedirectStandardError $rlStderr
"rl sitting process=$($rlProcess.Id) game=$rlGamePid output=$Out"
