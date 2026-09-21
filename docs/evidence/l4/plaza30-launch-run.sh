#!/bin/zsh
# ONE run: native recording on, then the reach30 command with --run plaza30; waited on; log tail printed
S=${0:A:h}; run=plaza30
exists=$(zsh ~/.claude/skills/windows-pc/pc.sh "Test-Path C:\\rivals-agent\\data\\l1\\$run")
[[ "$exists" == *True* ]] && { echo "REFUSING: $run already exists"; exit 2; }
zsh ~/.claude/skills/windows-pc/desk.sh "Focus 'Marvel Rivals' | Out-Null; Start-Sleep 1; \$ff = (Get-Command ffmpeg).Source; Start-Process -FilePath \$ff -ArgumentList '-hide_banner','-loglevel','warning','-y','-filter_complex','\"ddagrab=output_idx=0:framerate=60\"','-c:v','h264_nvenc','-preset','p4','-cq','19','-t','75','C:\\rivals-agent\\data\\video\\$run.mp4' -WindowStyle Hidden -RedirectStandardError C:\\rivals-agent\\data\\video\\$run.log; Start-Sleep 2; Start-Process -FilePath cmd -ArgumentList '/v:on','/c','echo START %time% > data\\l4\\loop-$run.log & uv run --no-project --with dxcam --with opencv-python --with numpy --with pillow --with vgamepad python -m agent.loop --live --cooldowns normal --run $run --max-s 30 >> data\\l4\\loop-$run.log 2>&1 & echo EXIT !errorlevel! !time! >> data\\l4\\loop-$run.log' -WorkingDirectory C:\\rivals-agent -WindowStyle Hidden; 'started'"
for i in $(seq 1 30); do
  perl -e 'sleep 5'
  r=$(zsh ~/.claude/skills/windows-pc/pc.sh "Select-String -Path C:\\rivals-agent\\data\\l4\\loop-$run.log -Pattern '^EXIT' -Quiet")
  [[ "$r" == *True* ]] && break
done
zsh ~/.claude/skills/windows-pc/pc.sh "Get-Content C:\\rivals-agent\\data\\l4\\loop-$run.log | Select-Object -First 6; '...'; Get-Content C:\\rivals-agent\\data\\l4\\loop-$run.log -Tail 4; 'procs: ' + @(Get-Process python,uv -ErrorAction SilentlyContinue).Count; 'pads: ' + @(Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | Where-Object FriendlyName -like '*Xbox 360*').Count"
