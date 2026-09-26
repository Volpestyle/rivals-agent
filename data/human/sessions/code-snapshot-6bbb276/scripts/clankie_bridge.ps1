param(
    [string]$Address = '127.0.0.1',
    [int]$Port = 4330,
    [ValidateSet('off', 'normal')][string]$Cooldowns
)
$ErrorActionPreference = 'Stop'
if (-not $Cooldowns) { throw '-Cooldowns off|normal is required (no default)' }
Set-Location (Split-Path $PSScriptRoot -Parent)
New-Item -ItemType Directory -Force data | Out-Null
$uv = (Get-Command uv -ErrorAction Stop).Source
$token = Join-Path (Get-Location) 'data\clankie-token'
if (-not (Test-Path $token)) {
    & $uv run --no-project python -m agent.server --token-file $token --init-token
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & icacls.exe $token /inheritance:r /grant:r "${env:USERNAME}:(F)" 'SYSTEM:(F)' | Out-Null
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
# One desktop-session server, idle until Clankie starts a bounded sitting.
& $uv run --no-project --with dxcam --with vgamepad --with opencv-python --with pillow python -m agent.server --host $Address --port $Port --token-file $token --cooldowns $Cooldowns *>> data\clankie-bridge.log
exit $LASTEXITCODE
