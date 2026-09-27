#!/bin/zsh
# Send a pad token sequence to the live game, then pull a screenshot to this Mac.
#   scripts/padrun.sh "<tokens>" <shot.png> [--dangerous]     tokens: see scripts/pad.py
# X, START, BACK and the d-pad are refused without --dangerous: pass it only after reading a screenshot.
# Runs pad.py inside the PC's desktop session (a C:\desk job), focusing the game first:
# the game ignores the pad while another window has focus.
set -e
tokens=$1; shot=${2:?usage: padrun.sh "<tokens>" <shot.png> [--dangerous]}; flag=${3:-}
skill=~/.claude/skills/windows-pc
job="Focus \"Marvel Rivals\"; Start-Sleep -Milliseconds 400; Set-Location 'C:\\rivals-agent'; & 'C:\\Users\\volpe\\AppData\\Local\\Programs\\Python\\Python311\\Scripts\\uv.exe' run --no-project --python 3.11 --with vgamepad python pad.py '$tokens' $flag 2>&1 | Select-Object -Last 2"
zsh $skill/desk.sh "$job" | tail -1
zsh $skill/desk.sh shot "$shot" | tail -1
