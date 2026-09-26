# Prepare the PC (supedupsilly, RTX 4080 SUPER) to train and run the L3 detector.
# Run it from this Mac:  zsh ~/.claude/skills/windows-pc/pc.sh -f perception/setup_pc.ps1
# Idempotent: it warms the uv environment and proves CUDA, it trains nothing.
#
# The only real trap here is torch. PyPI's Windows `torch` wheel is CPU-only, so a
# plain `uv run --with ultralytics` silently trains on the i9 at a few percent of
# GPU speed (observed here: torch 2.14.0+cpu, cuda build None). Neither the
# `--torch-backend` flag (uv 0.9.26 rejects it on `run`) nor UV_TORCH_BACKEND=auto
# changed that, so the CUDA wheel index is named outright. Driver 610.60 covers cu128.
# Every command that trains or infers on this PC needs $TORCH_INDEX.

$ErrorActionPreference = "Stop"
$TORCH_INDEX = "https://download.pytorch.org/whl/cu128"

$repo = "C:\rivals-agent"
New-Item -ItemType Directory -Force -Path "$repo\data" | Out-Null

Write-Output "uv:     $(& uv --version)"
Write-Output "driver: $(& nvidia-smi --query-gpu=driver_version,name --format=csv,noheader)"

# Resolve and cache the full training environment once, so the real run starts immediately.
$probe = Join-Path $env:TEMP "l3_probe.py"
@'
import torch, ultralytics
print("torch", torch.__version__, "| cuda build", torch.version.cuda)
print("cuda available:", torch.cuda.is_available(),
      "|", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "NO GPU")
print("ultralytics", ultralytics.__version__)
assert torch.cuda.is_available(), "torch has no CUDA: the run is missing --index for the cu128 wheels"
'@ | Set-Content -LiteralPath $probe -Encoding ASCII

& uv run --no-project --index $TORCH_INDEX --with ultralytics --with "clip @ git+https://github.com/ultralytics/CLIP.git" python $probe
if ($LASTEXITCODE -ne 0) { throw "environment probe failed with exit $LASTEXITCODE" }
Write-Output "setup_pc: ready"
