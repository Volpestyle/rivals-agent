#!/bin/zsh
n=$1
zsh ~/.claude/skills/windows-pc/desk.sh "Focus 'Marvel Rivals' | Out-Null; Start-Sleep 1; Start-Process -FilePath cmd -ArgumentList '/v:on','/c','echo START %time% > data\\l4\\reenter-$n.log & uv run --no-project --with dxcam --with opencv-python --with numpy --with pillow --with vgamepad python scripts\\reenter.py >> data\\l4\\reenter-$n.log 2>&1 & echo EXIT !errorlevel! !time! >> data\\l4\\reenter-$n.log' -WorkingDirectory C:\\rivals-agent -WindowStyle Hidden; 'started'"
for i in $(seq 1 30); do
  perl -e 'sleep 6'
  r=$(zsh ~/.claude/skills/windows-pc/pc.sh "Select-String -Path C:\\rivals-agent\\data\\l4\\reenter-$n.log -Pattern '^EXIT' -Quiet")
  [[ "$r" == *True* ]] && break
done
zsh ~/.claude/skills/windows-pc/pc.sh "Get-Content C:\\rivals-agent\\data\\l4\\reenter-$n.log; 'procs: ' + @(Get-Process python,uv -ErrorAction SilentlyContinue).Count; 'pads: ' + @(Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | Where-Object FriendlyName -like '*Xbox 360*').Count; Get-ChildItem C:\\rivals-agent\\data\\reenter -Directory -Filter 'arrive-*' | Select-Object -Last 1 -ExpandProperty Name"
