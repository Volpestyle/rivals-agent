#!/bin/zsh
# usage: m2.sh <n>   -- native recording on, then ONE `python -m agent.loop --live --pose-only --run m2-pose-<n>`; waited on; log printed
S=${0:A:h}; n=$1; run=m2-pose-$n
exists=$(zsh ~/.claude/skills/windows-pc/pc.sh "Test-Path C:\\rivals-agent\\data\\l1\\$run")
[[ "$exists" == *True* ]] && { echo "REFUSING: $run already exists (never reuse a name)"; exit 2; }
zsh ~/.claude/skills/windows-pc/desk.sh "New-Item -ItemType Directory -Force C:\\rivals-agent\\data\\video | Out-Null; Focus 'Marvel Rivals' | Out-Null; Start-Sleep 1; \$ff = (Get-Command ffmpeg).Source; Start-Process -FilePath \$ff -ArgumentList '-hide_banner','-loglevel','warning','-y','-filter_complex','\"ddagrab=output_idx=0:framerate=60\"','-c:v','h264_nvenc','-preset','p4','-cq','19','-t','45','C:\\rivals-agent\\data\\video\\$run.mp4' -WindowStyle Hidden -RedirectStandardError C:\\rivals-agent\\data\\video\\$run.log; Start-Sleep 2; Start-Process -FilePath cmd -ArgumentList '/v:on','/c','echo START %time% > data\\l4\\$run.log & uv run --no-project --with dxcam --with opencv-python --with numpy --with pillow --with vgamepad python -m agent.loop --live --pose-only --run $run >> data\\l4\\$run.log 2>&1 & echo EXIT !errorlevel! !time! >> data\\l4\\$run.log' -WorkingDirectory C:\\rivals-agent -WindowStyle Hidden; 'started'"
for i in $(seq 1 20); do
  perl -e 'sleep 4'
  r=$(zsh ~/.claude/skills/windows-pc/pc.sh "Select-String -Path C:\\rivals-agent\\data\\l4\\$run.log -Pattern '^EXIT' -Quiet")
  [[ "$r" == *True* ]] && break
done
zsh ~/.claude/skills/windows-pc/pc.sh "Get-Content C:\\rivals-agent\\data\\l4\\$run.log; 'procs: ' + @(Get-Process python,uv -ErrorAction SilentlyContinue).Count; 'pads: ' + @(Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | Where-Object FriendlyName -like '*Xbox 360*').Count; Get-ChildItem C:\\rivals-agent\\data\\l1\\$run | Select-Object Name,Length | Format-Table -AutoSize"
