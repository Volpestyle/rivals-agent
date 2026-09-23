$ErrorActionPreference = 'Stop'
$runtime = 'C:\Users\volpe\repos\rivals-agent\data\runtime\range-request-20s-preflight-20260922'
$liveTree = 'C:\Users\volpe\repos\rivals-agent-live'
$runDir = 'C:\Users\volpe\repos\rivals-agent\data\l1\range-request-20s-20260922-1'
$model = 'C:\Users\volpe\repos\rivals-agent\data\diagnostics\range-request-human-fit-20260922\run-1\model.pt'
$video = Join-Path $runtime 'learned-native.mp4'
if ((Test-Path -LiteralPath $runDir) -or (Test-Path -LiteralPath $video) -or (Test-Path -LiteralPath (Join-Path $runtime 'binding-consumed.json'))) { throw 'The one authorized diagnostic already has artifacts' }
if ((Get-FileHash -LiteralPath $model).Hash.ToLower() -ne '6ee388070599e3df042ea73876e391340bf228a9e626cc212c60875d8191aeef') { throw 'Checkpoint changed' }
foreach ($name in @('controller-deployed.json','perception-deployed.json')) {
  $manifest = Get-Content -LiteralPath (Join-Path $runtime $name) -Raw | ConvertFrom-Json
  foreach ($p in $manifest.files.PSObject.Properties) {
    if ((Get-FileHash -LiteralPath (Join-Path $liveTree $p.Name)).Hash.ToLower() -ne $p.Value.sha256) { throw ('Deployed bytes changed: '+$p.Name) }
  }
}
$game = Get-Process -Id 48460 -ErrorAction Stop
if ($game.ProcessName -ne 'Marvel-Win64-Shipping') { throw 'Game PID changed' }
Focus 'Marvel Rivals'
Screenshot 'C:\desk\out\range-request-20s-before.png'
@{run='range-request-20s-20260922-1'; consumed_utc=[DateTime]::UtcNow.ToString('o'); checkpoint_sha256='6ee388070599e3df042ea73876e391340bf228a9e626cc212c60875d8191aeef'; binding_sha256=(Get-FileHash (Join-Path $runtime 'deployment-binding.json')).Hash.ToLower(); reason='one authorized exploratory launch; preserve failure; do not rerun this binding'} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtime 'binding-consumed.json')
$clockBefore = [Diagnostics.Stopwatch]::GetTimestamp()
$wallBefore = [DateTime]::UtcNow.ToString('o')
$record = Start-Process -FilePath (Get-Command ffmpeg.exe).Source -WindowStyle Hidden -ArgumentList '-hide_banner -nostdin -f lavfi -i ddagrab=framerate=60 -c:v h264_nvenc -cq 20 -t 60 C:\Users\volpe\repos\rivals-agent\data\runtime\range-request-20s-preflight-20260922\learned-native.mp4' -RedirectStandardError (Join-Path $runtime 'learned-record.log') -PassThru
@{video=$video; record_pid=$record.Id; launch_utc_before=$wallBefore; launch_utc_after=[DateTime]::UtcNow.ToString('o'); stopwatch_before=$clockBefore; stopwatch_after=[Diagnostics.Stopwatch]::GetTimestamp(); stopwatch_frequency=[Diagnostics.Stopwatch]::Frequency; video_loop_mapping_known=$false; command='ddagrab=framerate=60 -> h264_nvenc -cq20 -t60'} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtime 'learned-recorder.json')
'record_pid=' + $record.Id
$run = Start-Process -FilePath 'C:\Users\volpe\AppData\Local\Programs\Python\Python311\Scripts\uv.exe' -WorkingDirectory $liveTree -WindowStyle Hidden -ArgumentList 'run --offline --no-project --python 3.11 --with dxcam --with vgamepad --with opencv-python-headless --with pillow --with torch python C:\Users\volpe\repos\rivals-agent\data\runtime\range-request-20s-preflight-20260922\run_instrumented.py --live --brain range-skill --game-pid 48460 --max-s 20 --cooldowns normal --no-scoreboard --run range-request-20s-20260922-1 --range-checkpoint C:\Users\volpe\repos\rivals-agent\data\diagnostics\range-request-human-fit-20260922\run-1\model.pt --range-sha256 6ee388070599e3df042ea73876e391340bf228a9e626cc212c60875d8191aeef --range-identity C:\Users\volpe\repos\rivals-agent\data\runtime\range-request-20s-preflight-20260922\source-identity.json --range-runtime C:\Users\volpe\repos\rivals-agent\data\runtime\range-request-20s-preflight-20260922\runtime-identity.json --range-deployment C:\Users\volpe\repos\rivals-agent\data\runtime\range-request-20s-preflight-20260922\deployment-binding.json' -RedirectStandardOutput (Join-Path $runtime 'learned.log') -RedirectStandardError (Join-Path $runtime 'learned.err') -Wait -PassThru
@{exit_code=$run.ExitCode; ended_utc=[DateTime]::UtcNow.ToString('o'); original_record_pid=$record.Id; run=$runDir} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtime 'launch-result.json')
'learned_exit=' + $run.ExitCode
Screenshot 'C:\desk\out\range-request-20s-after.png'