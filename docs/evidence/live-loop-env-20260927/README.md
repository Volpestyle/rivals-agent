# Durable live environment repair — 2026-09-27

Usable interpreter: `C:/Users/volpe/.venvs/rivals-live-cu128/Scripts/python.exe`.
Its existing CPython 3.11.9 base is
`C:/Users/volpe/AppData/Local/Programs/Python/Python311/python.exe`.
Neither location depends on Temp. The shared repository `.venv` was not changed.

Installed 36 exact distributions and completed `uv pip check` successfully.
The probe imported torch, torchvision, av, numpy, cv2 and pytest in that order.
DXCAM 0.3.0 then failed during its import-time display enumeration with COM
error -2005270494 (`DXGI_ERROR_NOT_CURRENTLY_AVAILABLE`). No camera was
constructed, no capture was requested, and no input was sent. Vgamepad import,
which followed DXCAM in the command, was not reached. Desktop readiness is
therefore unverified. This failure does not establish a missing Python package.

James resumed play/recording during this repair. The lead canceled GPU smoke
authorization and stopped further installs, tests and probes. No CUDA device
count query, allocation or forward was run. CPU FPS preparation and the
inference/FPS tests were not run in this rebuilt environment. Earlier test
results do not qualify the new environment. No automatic retry is scheduled;
future checks require a fresh owner instruction. All repair processes exited.

## Pins and provenance

The prior fallback/replay packets identify CPython 3.11.9, torch 2.11.0+cu128
and PyAV 18.1.0. The surviving Temp environment's distribution metadata supplied
the exact complete 33-package core freeze in `recovered-freeze.txt`; the recovery
receipt is `recovered-metadata.json`. No latest-version selection was used.
The additional desktop versions came from the existing local live uv environment
at `C:/Users/volpe/AppData/Local/uv/cache/archive-v0/ddbgu37yFuZmn58SWE7PY/Lib/site-packages`:
DXCAM 0.3.0, comtypes 1.4.17 and vgamepad 0.1.0. `installed-freeze.txt` records
all 36 installed distribution versions read back from their metadata directories.

The existing cached vgamepad wheel is retained here to avoid a source build:
its setup script may launch a driver installer. Wheel SHA256:
`c96f55a52b2755caf5b5845f5e1528c24ce844a4c44f7d135c78da3d1bbfd4b1`.
Installing the wheel did not run its source setup script. Inspecting vgamepad's
source showed import initializes a ViGEm bus client, while virtual target
construction happens later in the pad class constructor. This repair did not
import it or construct a pad. DXCAM import itself enumerates display devices;
it is not a side-effect-free import, even without calling `create()`.

## Reproduction when separately authorized and game/OBS are stopped

Use uv 0.9.26 and the existing durable 64-bit CPython 3.11.9 base. The base
executable SHA256 is recorded in `verification.json`; this is an executable
identity check, not an installer archive checksum. This packet does not install
or replace the base Python. Never remove or recreate an occupied environment.
From this repository in PowerShell, for a fresh destination:

```powershell
$basePython = 'C:/Users/volpe/AppData/Local/Programs/Python/Python311/python.exe'
$liveEnv = 'C:/Users/volpe/.venvs/rivals-live-cu128'
$livePython = "$liveEnv/Scripts/python.exe"
$packet = 'docs/evidence/live-loop-env-20260927'
if (Get-Process Marvel*,obs64 -ErrorAction SilentlyContinue) { throw 'Game/OBS present' }
if (Test-Path -LiteralPath $liveEnv) { throw 'Destination already exists; preserve it' }
uv venv --python $basePython $liveEnv
if ($LASTEXITCODE) { throw 'venv creation failed' }
uv pip install --python $livePython --no-deps --extra-index-url https://download.pytorch.org/whl/cu128 --index-strategy unsafe-best-match -r "$packet/recovered-freeze.txt"
if ($LASTEXITCODE) { throw 'Core installation failed' }
uv pip install --python $livePython --no-deps -r "$packet/desktop-pins.txt" "$packet/wheels/vgamepad-0.1.0-py3-none-any.whl"
if ($LASTEXITCODE) { throw 'Desktop dependency installation failed' }
uv pip check --python $livePython
```

Maintain the no-game/OBS condition throughout any future install or test job;
the initial process check is not a continuing guard. These are reproduction
instructions, not a running job. Exact version pins freeze package selection;
only the retained vgamepad wheel is artifact-hash pinned in this packet.

The attempted cache-only core install could not find typing_extensions 4.16.0;
the exact-pinned online retry installed all 33 core distributions. Its raw
PowerShell `Tee-Object` log is retained as `install-core.log`. PowerShell rendered
uv's stderr progress as NativeCommandError text, and the wrapper exited 1;
the subsequent successful package compatibility check and metadata readback
establish the actual install result. The three desktop packages installed
successfully afterward.

## Missing Temp launcher investigation

Both `Scripts/python.exe` and `Scripts/pythonw.exe` were missing, while
`pyvenv.cfg`, package metadata and other launchers remained. The old base Python
still exists outside Temp. A read-only search of recent Defender detection/action
events returned no matching old-environment path. The deletion cause is unknown;
the available evidence does not justify attributing it to Temp cleanup,
quarantine or a particular process. The old environment was preserved intact.

`verification.json` records the bounded result and explicit omissions. No
dataset, decoding, training, desktop capture, controller input or GPU inference
was used for this repair.
