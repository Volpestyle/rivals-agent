# Mac and PC responsibilities

This is the machine contract for this repo. It applies whichever machine hosts
the lead agent. Scope and admission gates in [the plan](plan.md) and
[learning plan](learning-plan.md) still apply.

| Responsibility | Windows PC: `supedupsilly` | Mac: M5 Max, 128 GB |
|---|---|---|
| Game and human demonstrations | Marvel Rivals, OBS, raw keyboard/mouse logger; immutable original recordings | Review finalized copies offline |
| Live agent | Desktop-session capture, perception, local safety checks, control and episode metrics | Offline analysis; optional slow services only after measured latency checks |
| Data preparation | Finalize and verify a named capture, hash original bytes | Verify transferred bytes, review/admit, import and prepare training windows |
| Training and evaluation | Bounded CPU checks; CUDA only with game/recording stopped and GPU available | Default: niced offline jobs, PyTorch MPS for paired execution; historical MLX stays separate |
| Development | Git, native Windows environment, Windows integration checks | Git, native macOS environment, MPS and Unix integration checks |

The RTX 4080 SUPER stays available to the running game. The live agent loop
must not depend on SSH shipping every frame to the Mac and every action back.
Local inference placement still needs measured PC frame-time and action latency.
The Mac's unified memory is useful for preparation and experiments; it is not
a performance guarantee. `nice` changes CPU scheduling, not GPU priority: avoid
overlapping training with another heavy Mac GPU workload.

## Reach either machine

Verified Windows-to-Mac SSH identity: `james`, Darwin arm64, Apple M5 Max,
137438953472 bytes RAM (128 GiB). The PC has Windows OpenSSH and a dedicated
private key; only its public key is installed on the Mac.

| From | Shell route | Skill |
|---|---|---|
| Windows | `ssh mac`, Tailscale `jamess-macbook-pro.tailb90f24.ts.net` / `100.103.220.58` | `mac-remote` |
| Mac | `ssh volpe@supedupsilly`, Tailscale `100.108.214.60` | `windows-pc` |

Windows PowerShell example:

```powershell
& "$HOME/.claude/skills/mac-remote/mac.ps1" 'uname -sm; command -v uv ffmpeg'
& "$HOME/.claude/skills/mac-remote/mac.ps1" -File ./job.zsh -WorkingDirectory /Users/james/dev/rivals-agent
```

Mac Terminal example:

```zsh
zsh ~/.claude/skills/windows-pc/pc.sh 'Get-ComputerInfo | Select-Object CsName,OsName'
```

The wrappers preserve the destination shell's quoting and encoding. Mac `chmod`
and `authorized_keys` setup runs in Mac Terminal. Windows PowerShell setup runs
on Windows. Shell connectivity does not provide a desktop session: load the
live-game skill and obtain the existing desktop-owner handoff before game input.
Host keys remain checked. See each skill for connection diagnosis and long jobs.

## Code and environments

Windows development checkout: `C:\Users\volpe\repos\rivals-agent`. Mac's existing
checkout: `/Users/james/dev/rivals-agent`. Use an isolated worktree when a checkout
belongs to another agent. Record `git rev-parse HEAD` on both sides before comparing
results; use Git to transfer code, without resetting another checkout's work.
The execution branch's isolated Mac worktree is
`/Users/james/dev/rivals-agent-worktrees/human-execution`; use that directory for
the new paired execution pipeline. Its detached commit is updated explicitly
after checking that the worktree is clean.

Each machine creates its own `.venv` from `uv.lock`. Do not copy `.venv`, native
packages, build caches or credentials between operating systems. `uv run --locked
pytest` is the ordinary offline check. Install `execution` only for a job that
needs PyTorch; the historical `policy` group contains Mac-specific MLX.

Before selecting MPS, run this in the intended Mac checkout:

```zsh
uv run --locked --group execution python -c 'import torch; print(torch.__version__); print(torch.backends.mps.is_built(), torch.backends.mps.is_available()); x=torch.arange(4.,device="mps",requires_grad=True); x.square().sum().backward(); torch.mps.synchronize(); print(x.grad.cpu().tolist())'
```

This proves a device operation and gradient, not the complete training pipeline.
Run the relevant synthetic pipeline checks, then an admitted-data experiment with
`--device mps`. Keep CPU as an explicit diagnostic choice; don't silently relabel
a CPU run as MPS. The lock's Windows PyTorch wheel is currently CPU-only: selecting
`--device cuda` alone does not install a CUDA build. A future CUDA environment
needs its own dependency and device verification.

## Record on Windows, import on the Mac

1. Finalize one named OBS session. Keep its original video, `metadata.json`,
   `inputs.jsonl` and `frames.csv` together in the transfer manifest. Verify the
   recorder's completion/loss report. Never consume a growing recording folder.
2. Hash the original video on Windows with `Get-FileHash -Algorithm SHA256`; save
   that source digest before transferring. Hash the accompanying files too and
   retain a transfer receipt. Copy only the explicitly selected, authorized files.
3. Verify the destination hashes with `shasum -a 256`. Keep recorder metadata
   immutable, including its literal Windows `video_path`. An identical video on
   the Mac has a different local path; editing recorder metadata would obscure
   provenance.
4. In the Mac's complete split registry, keep session ID, session group and split.
   Set `video_path` to the local file. For relocation, add the paired fields
   `recorded_video_path` (exact original metadata string) and
   `expected_media_sha256` (lowercase SHA-256 measured on Windows). The importer
   checks source identity and destination bytes before probing media. Follow
   [the importer contract](human-demo-schema.md) for the complete schema.
5. Supply the independently reviewed gameplay/suitability, settings/bindings,
   patch/cooldown regime, device scope, timing anchor and alignment evidence;
   then import on the Mac and retain its registry and imported artifacts for
   that experiment. A valid copy or recorder integrity check is not admission.

Selections exported with LosslessCut remain selections of the same original
session; they do not become independent train and validation examples. Prefer
original media plus reviewed intervals because exported timestamps and keyframe
boundaries can differ. Unknown DPI can remain explicitly unknown when reconstructing
logged native counts; record sensitivity and binding evidence without inventing DPI.

Sealed test access rules remain unchanged on both machines. Registry portability
does not grant permission to inspect test payloads. Existing imported artifacts
pin their local placement: import from immutable source on the destination using
the checked relocation contract; don't hand-edit an artifact to move it.

## Train on the Mac, return results

Follow [execution training](execution-training.md) in a dedicated run directory.
Begin with bounded samples and an explicit device; retain the exact code commit,
lockfile, source-file hashes, review and split registry, training configuration,
checkpoint and metric report. Long jobs need a durable process with a log and
exit status. Report completion from the output artifact, not the launch response.

Copy the checkpoint and report back to a new PC run directory and compare hashes.
The offline evaluator pins its exact validation artifacts and registry; rerun it
in the original experiment environment for a like-for-like report. Portable model
weights do not make a moved experiment's path-sensitive provenance interchangeable.

The current learned execution model predicts native keyboard/mouse controls
offline. Its checkpoint is not a gamepad controller and has no approved live input
adapter. Returning weights to Windows does not authorize deployment. The existing
virtual-pad harness and any future learned controller must pass the plan's input,
range-only, recovery, latency and evaluation gates before a gameplay claim.

## Verified on 2026-09-22 UTC

- Windows-to-Mac key authentication and Mac-to-Windows key authentication both
  returned the intended user. The `mac-remote` helper was independently checked
  on the real Mac for Unicode, shell quoting, working-directory quoting, ordinary
  failure and early failure during a large script. Its source lives in
  `Volpestyle/skills`, `platform/mac-remote`; all three Windows agent skill roots
  point to that source.
- In the isolated Mac worktree at `db6492a`, locked PyTorch 2.14.0 reported MPS
  built and available. A real MPS gradient returned `[0, 2, 4, 6]`. All seven
  execution tests passed on Mac. A separate two-epoch **MPS** fit used the tests'
  generated-video fixture, eight train and eight validation windows, small
  encoder, hidden size 8 and 16-pixel images. MPS checkpoint reload reproduced
  validation metrics exactly. No human recording was used.
- That synthetic checkpoint and its two reports were copied back to Windows;
  SHA-256 matched on both machines. Checkpoint digest:
  `fec9d61b5eb146c9b3033b6b89ad7cd5d65e8abc3612877309873e52ac94c741`.
  The returned MPS-trained checkpoint also loaded successfully on Windows CPU
  through the actual `load_checkpoint` API with its native action specification.
  Mac artifacts: `data/machine-verification/mps-20260922/`. Windows copies:
  `data/machine-verification/mps-20260922-return/`. These local, gitignored
  synthetic artifacts measure software behavior, not imitation quality.
- Independent relocation review exercised a literal Windows recorder path on
  the real Mac using disposable synthetic files: metadata stayed unchanged,
  frame references used the local Mac path, changed bytes were rejected and a
  sealed session was refused before source access. No real dataset was admitted.
- The Windows offline suite with the execution group passed **547 tests**, with
  12 opt-in/dependency/data skips. The relocation delta has independent read-only
  acceptance; this accepts software behavior, not a human training corpus.
