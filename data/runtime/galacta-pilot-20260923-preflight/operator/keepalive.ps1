# Keep the range session alive while slots are paused: every 8 min one walk-only nudge (0.15 s forward, 0.15 s back),
# then a screenshot scouted for the range HUD and the designated bot nearby. Stops (exit 3) on any failed check,
# and exits 0 when C:\desk\pilot0923\keepalive.stop exists. Logs to C:\desk\pilot0923\keepalive.log.
param([int]$Max = 18, [int]$PeriodS = 480)
$SP = 'C:\Users\volpe\AppData\Local\Temp\claude\C--Users-volpe-repos-rivals-agent\c01c3aba-4574-44d6-88e0-ce6cc77df198\scratchpad'
$pre = 'C:\Users\volpe\repos\rivals-agent\data\runtime\galacta-pilot-20260923-preflight'
$log = 'C:\desk\pilot0923\keepalive.log'; $stop = 'C:\desk\pilot0923\keepalive.stop'
function Log($m) { $l = "$(Get-Date -Format 'HH:mm:ss') $m"; Add-Content -LiteralPath $log -Value $l; $l }
for ($i = 1; $i -le $Max; $i++) {
  $until = (Get-Date).AddSeconds($PeriodS)
  while ((Get-Date) -lt $until) { if (Test-Path $stop) { Log 'stop file: keep-alive ended'; exit 0 }; Start-Sleep -Seconds 5 }
  if (Test-Path $stop) { Log 'stop file: keep-alive ended'; exit 0 }
  $name = 'p0923-ka-' + (Get-Date -Format 'HHmmss')
  $out = & "$SP\nav-run.ps1" -Name $name -Tokens 'ls:0,1,0.15 ls:0,-1,0.15 w:0.6 shot:a' | Out-String
  if ($out -notmatch 'exit=0') { Log "nudge $i FAILED: $($out -replace '\s+',' ')"; exit 3 }
  $j = cmd /c "uv run --offline --no-project --python 3.11 --with opencv-python-headless --with numpy python -B $pre\scout.py C:\desk\out\$name-a.jpg 2>NUL" | ConvertFrom-Json
  $near = @($j.boxes | Where-Object { $_.finder -eq 'aim' -and $_.h -ge 0.2 })
  $msg = "nudge $i $name in_range=$($j.in_range) hp=$($j.hp) webs=$($j.webs) aim=" + (($j.boxes | Where-Object finder -eq 'aim' | ForEach-Object { "$($_.bbox -join ',') h=$($_.h)" }) -join ' | ')
  Log $msg
  if (-not $j.in_range -or -not $near.Count) { Log "scene check FAILED after nudge $i"; exit 3 }
}
Log 'max iterations reached'
exit 0
