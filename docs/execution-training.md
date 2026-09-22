# Offline human execution baseline

`policy.execution` fits a PyTorch temporal keyboard/mouse policy from explicitly
imported OBS sessions and their original video. It does not send input, load the
historical MLX policies, translate mouse counts into stick axes, or access sealed
test payloads. A successful fit establishes software plumbing, not Spider-Man
competence. Independent admission review remains required before using real data.

## Inputs and commands

First follow [the importer contract](human-demo-schema.md): finalize a session,
review its gameplay and imitation suitability, record bindings/settings (including
DPI when known and sensitivity), patch/cooldown regime, single-device scope, independent PTS
anchor and explicit capture-latency assumption/bound. Import each named recording
using one shared session-group split registry. Only accepted segments are sampled.
Keep original media in the registered paths. This consumer accepts the imported
`rivals-human-demo-v1` artifacts, not exported sample JSONL or old pad recordings.

Install the `execution` dependency group (PyTorch and torchvision), plus ffmpeg
and ffprobe on PATH. The module imports PyTorch lazily; `--help` works without it.
Use CPU explicitly for a first smoke run. The PC GPU belongs to the running game;
use MPS on the Mac or CUDA only when the PC is available for training.
See [machine responsibilities](machines.md) for checked Windows-to-Mac recording
relocation, native environments and the artifact return path.

```powershell
uv run --group execution python -m policy.execution fit --train data/human/imported/train-a.json --val data/human/imported/val-b.json --splits data/human/session-splits.json --checkpoint data/human/run-01.pt --report data/human/run-01.json --encoder small --device cpu --epochs 2 --max-samples-per-session 100
uv run --group execution python -m policy.execution evaluate --val data/human/imported/val-b.json --splits data/human/session-splits.json --checkpoint data/human/run-01.pt --report data/human/run-01-repeat.json --device cpu
```

Create output directories first and use new output filenames; existing checkpoints
and reports are never overwritten. `--train` and `--val` each accept multiple named
artifacts. The small encoder starts from random weights and is intended for smoke
checks. For a frozen pretrained visual baseline, use `--encoder resnet18
--download-weights --image-size 224`, or `--encoder resnet18 --weights
path/to/resnet18-state-dict.pt --image-size 224`. Downloading is explicit. Local
weights must be a torchvision ResNet18 state dictionary with its classification
head; checkpoint reload needs no original weights file and downloads nothing.

Default windows use 500 ms history, frames every 100 ms, ten future 20 ms action
bins and 100 ms sample stride. Change `--history-ms`, `--frame-step-ms`, `--bin-ms`,
`--bins` and `--stride-ms` deliberately. `--max-samples-per-session` takes the first
eligible windows of each session (default 1,000); this is a bounded development
sample, not a representative whole-recording evaluation. Raise it for a planned
experiment and retain the recorded setting. Evaluation reuses the saved windows
and limits and accepts exactly the same validation artifacts and registry.

## Model and action contract

The encoder receives only causal `Sample.observation()` RGB history. A GRU encodes
the sequence; the prediction head also receives causal anchor-time held controls
and their known bits. It produces an entire future action chunk. Labels come only
from `Sample.future`. There are no implicit skill/intent/outcome labels. Raw past
input events remain available in observations but this baseline uses their held
state summary; it does not separately encode past mouse velocity or key timing.

Keyboard output identity is `key:<scan>:<E0/E1 flags>`. The importer retains native
device HANDLE, VK, scan and flags, but handles are session-local and intentionally
do not become model action identities. This normalization requires the reviewed
single-keyboard/single-mouse admission contract. Bindings/layout and all settings
must match across sessions. Training-only VK aliases map focus uncertainty onto
the physical controls, including sided modifiers. Zero scan codes are rejected.
An unseen validation scan code is reported as unsupported and never expands the
training vocabulary. The five mouse buttons use their native button numbers.

Each control predicts end-of-bin **held**, **press exists**, and **release exists**.
A tap ending released therefore retains both edges. Repeated make/break messages
without a state transition do not become edges. For one press and one release,
the known starting hold determines their order. Exact sub-bin timing is not
predicted. More than one real press or release per control/bin cannot be encoded:
both edge losses are masked and the report counts those unsupported bins. Raw
ordered events remain in the importer artifact. Predictions can be mutually
inconsistent; this baseline is a forecasting model with no executable replay or
constraint decoder.

Snapshot-unknown physical keys never become released labels. Unknown starting
state masks edge supervision for that entire bin, even if it later resolves.
End-held supervision uses its own known mask. Unknown physical identity does not
mask otherwise known mouse buttons. Focus/pause boundaries are rejected. Absolute
mouse motion masks dx/dy; relative dx/dy and both wheel axes retain native signed
counts per bin. Wheels are regression targets, not silently discarded events.

Binary channels use masked BCE and continuous channels use masked Smooth L1 after
training-only mean/scale normalization. The local two-convolution encoder learns
jointly with the GRU. ResNet18 is frozen, including BatchNorm, with fixed ImageNet
normalization. Frames are stretched to the configured square size; tiny targets
and HUD text can be lost. No visual adequacy or gameplay transfer is established.

## Splits, provenance and metrics

The importer revalidates the shared registry, media checksums, reviewed intervals
and exact decoded-frame timing. Duplicate sessions, media reused across groups,
session-group split leakage and mixed patch/cooldown contexts are refused. The
consumer additionally requires identical settings and bindings. There is no
mixed-context mode and no unseal/test option. Sealed artifact refusal occurs at
the header, before body parsing or media decoding.

Vocabulary, control priors, mouse normalization and all optimizer updates use
train sessions only. No validation-dependent early stopping or threshold tuning
is implemented: the threshold is fixed at 0.5. Reports contain each control's
training support and validation known/positive support, accuracy, precision,
recall and F1 for held/press/release separately. Undefined metrics are null.
Unseen controls include the number of validation chunks in which they occur.
Dx, dy and both wheel axes have separate count-unit MAE/RMSE and known support.
Overlapping chunks count repeated targets; sample count is not independent trials.

Compare all three reported predictors: the model, anchor-held persistence with
no new edges and zero mouse/wheel counts, and a train-only per-horizon control
prior plus train mean motion. Persistence held support excludes anchor-unknown
controls; compare those support counts before comparing scores. These baselines
do not establish gameplay quality, and inactive-control accuracy can be high.

Checkpoints record the action domain/spec and VK aliases, architecture/window/run
settings, all training statistics, weights, registry/artifact/media/settings
fingerprints, per-session alignment reviews, source hash and PyTorch version.
`load_checkpoint(..., domain="gamepad")` rejects compatibility before loading.
Model weights load with `weights_only=True`; source changes or dependency upgrades
can still affect numerical reproducibility and should receive new verification.

Decoding batches selected presentation ordinals in one ffmpeg process per video;
it never starts a process per frame or uses approximate seeking. A temporary
filter script avoids Windows command-line length limits, and exact raw byte counts
are checked before pairing frames with indices. Selected uint8 frames reside in
RAM; `--max-frames` defaults to 20,000 (about 0.55 GB at 96 square, 3 GB at 224,
plus overhead). It still decodes the whole video and repeats the visual encoder
each epoch. This is a usable bounded baseline, not a scalable feature cache.

## Verification and current limits

```powershell
uv run --group execution pytest tests/test_execution.py -q
```

The default stdlib-only suite skips this file when PyTorch is absent. Synthetic
tests exercise tap/repeat/multi-edge labels, physical identity across changed
device handles, focus and absolute-motion masks, zero masked gradients, causal
future rewrite, unseen held-session labels, exact checkpoint prediction reload,
loss reduction on a tiny CPU fixture, exact nonconsecutive ffmpeg frame ordinals,
and real generated-video import through fit/evaluate with split/sealing/settings
rejections. These tests download nothing and never open the demonstration corpus.
Independent read-only review accepted the implementation's admission and training
boundaries, including train-only fitting, causal inputs, support metrics and masks.
Real recording admission still needs its own reviewed evidence.

On 2026-09-21, the seven tests passed in 7.05 seconds with the locked Windows
CPU environment (PyTorch 2.14.0+cpu, torchvision 0.29.0+cpu). The two-epoch
generated-video fit's training loss changed from 0.780476 to 0.776323 over eight
training windows. Reloaded module-CLI evaluation reproduced all eight validation
window metrics exactly. These are small software checks; neither the generated
solid-color frames nor these loss values measure imitation of a human player.

No real human training run or gameplay success is claimed. Uncalibrated OBS capture
delay remains an explicit assumption even when software alignment passes. Technical
execution needs reviewed examples, rare-control support, diverse held sessions,
native-frame adequacy and eventually separately authorized live-domain validation.
