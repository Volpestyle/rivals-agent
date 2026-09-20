# L3 — detector

Owner: `rivals-det` (pane w26:pA). Files: `perception/autolabel.py`, `train.py`,
`eval.py`, `detect.py`, `outline.py`, `setup_pc.ps1`, `docs/evidence/l3/`, `data/`.

Full method, measurements and contact sheets: **`docs/evidence/l3/README.md`**.
This file is status, facts other lanes depend on, and decisions.

## Status

| | |
|---|---|
| Pipeline end to end (autolabel → train → eval → detect) | Runs on Mac MPS |
| `detect.py` returns `agent.state.Detection` | Done |
| `outline.py` classical prototype | Done, measured, **not recommended as-is** |
| PC CUDA environment | Verified: torch 2.11.0+cu128, CUDA True, RTX 4080 SUPER |
| run1 fine-tune (2121 frames, 1632 instances) | Done |
| Weights for the controller lane | `weights/range.pt`, and `C:\rivals-agent\weights\range.pt` |

### Results

| Run | Frames | Instances | mAP50 | mAP50-95 | P | R | Latency @1280x720 (MPS) |
|---|---|---|---|---|---|---|---|
| trial1 | 201 | 128 | 0.082 | 0.029 | 0.176 | 0.170 | median 13.2 ms, p95 15.9, max 18.9 |
| **run1** | **2121** | **1632** | **0.656** | **0.349** | **0.597** | **0.722** | median 21.5 ms, p95 26.3, max 29.9 |

Val: 318 images, 503 instances, one contiguous clip. 15 epochs, yolo11s, `imgsz=1280`,
`batch=4`, MPS, ~5 min/epoch. The 4080 figure is unmeasured — the PC GPU stays with
the game.

**Read mAP50 0.656 carefully — it is not 66% correct.** Val labels are auto-labels from
the same open-vocabulary labeller as train, and that labeller is ~50% precise. The score
says the model faithfully reproduces the labeller, *including its mistakes*. The eval
sheet shows exactly that: it boxes the purple bollard props confidently and never boxes
the player. So the jump from 0.082 to 0.656 is real learning of a consistent signal, but
it is consistency with a biased teacher, not accuracy against truth. **A hand-checked
ground-truth set is required before this number means what it appears to mean**, and
that is the main thing still owed on this lane.

### Loading it

```python
from perception.detect import Detector
det = Detector("weights/range.pt")          # or C:\rivals-agent\weights\range.pt
dets = det(frame_bgr)                        # list[agent.state.Detection]
```

Picks CUDA, then MPS, then CPU; fp16 only on CUDA. Boxes are in the pixels of the frame
passed in. sha256 `77ce87aa418e4eb3c39955d697efc05e632d7bd8df7a1f238e7d60ae402d1c04`,
18.3 MB, identical on both machines.

## Facts other lanes need

- **Targets are tiny.** Median box 21x33 px at 1280x720 (p10 10x19, p90 45x96).
  `imgsz` must stay 1280; at 640 the median bot is ~10 px. Track **mAP50**, not
  mAP50-95 — a few pixels of error is a large IoU error at this size.
- **The label ceiling, not the model, is the problem.** Hand-judged 36 random
  auto-labels: ~50% are scenery (pillars, fire, foliage). No schedule fixes that.
- **The player can be mislabelled as an enemy.** At low confidence the labeller put
  boxes on Spider-Man's own torso and arm. `autolabel.py` now drops anything >60%
  inside the detected hero, but consumers should not assume it can never happen.
- **`detect.py` returns boxes in the pixels of the frame it is given.** Keep capture
  size and `State.frame` equal — rivals-brain is making `State.frame` required and
  runtime perception runs on the same 1280x720 downscale used for training.
- **Enemy health bars are not auto-labellable.** Zero boxes across seven prompt
  variants. Reassigned to L2, anchored to the enemy box.
- **Red is a bad cue for this hero.** Spider-Man's belt is a wide thin bright-red
  bar of near-identical geometry to an enemy nameplate.

## Dead ends — do not re-run these

| Tried | Result | Why it failed |
|---|---|---|
| `healthbar` as an open-vocab class | 0 boxes, 7 prompt variants (`red health bar`, `health bar`, `red bar`, `progress bar`, `red rectangle`, `name tag`, `floating name label`) | YOLO-World does not find thin UI bars. Dropped; reassigned to L2. |
| Prompt tuning for better recall | `broad` set 27 boxes vs `current` 23 over 29 frames; `purple` 3, `combat` 4 | Marginal at best, and scenery prompts (`statue`, `toy figure`) add false positives. Most empty frames are genuinely empty — L1 was traversing. |
| Fixed own-hero rectangle (0.28–0.55 x, 0.35–1.0 y) | Ate real bots | A bot at mid-screen depth stands inside it (Luna Snow in trial1/000095). Replaced by size + containment. |
| `val` = last N frames | 2 instances in val, mAP meaningless | trial1 ends on traversal with no bots. Replaced by densest contiguous block. |
| `val` = window closest to proportional instance share | Picked an *empty* window | 15% of a small instance count is under one instance, so "closest" minimises toward zero. Replaced by maximising. |
| Red-bar cue with loose thresholds (`S>120, V>110`) | Boxed half the architecture | The map's pink masonry is in range. Fixed by measuring the actual nameplate (bright, V~229) vs suit (dark, V~200) vs masonry (unsaturated, S~48). |
| Red-bar cue at all, for Spider-Man | ~19% precision, structurally blind | Only the engaged/damaged bot (Luna Snow) has a red bar; Galacta bots have white nameplates and none. And **Spider-Man's belt is a wide thin bright-red bar** of near-identical geometry. Superseded by the green-outline request. |
| Inferring threshold scale from frame height | Wrong on crops | A 960 px square from a 1440p capture is 960 tall but its markers are 2.0x, not 1.33x. `scale` is now an explicit argument. |

## Tool and environment facts

- **PC torch is CPU-only by default.** PyPI's Windows `torch` wheel has no CUDA;
  a plain `uv run --with ultralytics` silently trains on the i9 (observed:
  `torch 2.14.0+cpu`). Neither `--torch-backend` (uv 0.9.26 rejects it on `run`) nor
  `UV_TORCH_BACKEND=auto` helped. Name the index: `--index https://download.pytorch.org/whl/cu128`.
  With it: torch 2.11.0+cu128, CUDA True. `perception/setup_pc.ps1` does this.
- **Pulling frames**: stage a zip in `$env:TEMP` on the PC and `scp` that one file.
  A `scp` of thousands of names fails — the argument list is too long, and zsh does
  not expand braces inside quotes. 2121 frames = 421 MB = ~25 s.
- **Ultralytics resolves a relative `project=` against its own `runs_dir`**, so weights
  landed in `runs/detect/data/runs/...`. Pass an absolute path.
- **Self-checks live in each script's `__main__`**, not in `tests/`: `uv run pytest`
  ignores the cv2-dependent tests, so a pytest file here would never run. Running any
  of these scripts runs its checks. (Worth the lead's attention: the cv2 tests are
  excluded from the default suite, so L2's `test_hud.py` does not run either.)
- Training on MPS: ~5 min/epoch for 1803 images at `imgsz=1280, batch=4`, and it slows
  markedly if anything else heavy runs on the same machine.

## Decisions

| Decision | By | Why |
|---|---|---|
| `ENEMY` only; no `TARGET`, no `ANCHOR` | Lead | `ANCHOR` comes from geometry. No static dummies exist in run1 — every hostile is a moving bot. |
| `distance`, `tagged` stay `None` | Lead | Detector estimates neither; `None` means "not read". `tagged` becomes an L2 reader above the enemy box. |
| Val is one contiguous, densest clip | L3 | Neighbouring frames are near-duplicates, so a random split leaks and flatters. The plain tail left 2 instances in val and made mAP meaningless. |
| Train on the Mac (MPS, niced) | Lead | PC GPU stays with the game; L4 takes the live game after L1. |
| Health-bar class dropped | Lead | Not detectable; brain does not use it. |

## Open ask for L4

Enable the game's **enemy outline / highlight** and set it to **pure green, #00FF00,
standard hue 120°** (OpenCV hue 60). Fallback order if the palette is fixed: green,
then yellow; **never** cyan, teal or magenta — they collide with the map lighting and
the suit.

Evidence, 107 run1 frames, share of *very vivid* pixels (S>150, V>200) per 5° OpenCV
hue bin:

| OpenCV hue | standard | share | what it is |
|---|---|---|---|
| 30–34 | 60–68° | 1.21% | yellow highlights |
| 35–39 | 70–78° | 0.003% | (quiet) |
| **55–69** | **110–138°** | **0.000%** | **empty — pure green lives here** |
| 75–79 | 150–158° | 1.54% | **the range's green doors** |
| 100–104 | 200–208° | 22.08% | map lighting |
| 105–109 | 210–218° | 11.76% | map lighting |

The green doors are an *emerald* green at standard hue 150–158°, about 30° away from
pure green. They do not rule green out; they rule out that particular green.

## outline.py — measured

Over 2121 run1 frames (every 3rd of 6361), full-frame 1280x720:

| | detections | frames with ≥1 | latency median | p95 |
|---|---|---|---|---|
| player guard off | 766 | 547 | 4.96 ms | 6.48 ms |
| **player guard on** | **612** | **462** | **5.33 ms** | **7.42 ms** |

The guard removes **154 detections, 20.1%** — scaled to the lead's 2317 over the full
run, about **466**. Hand-judged precision on 36 random detections rose from ~19% to
~29%. Player boxes are much reduced but **not eliminated**: a few close-ups of the suit
still produce one. Recall is not quoted yet — it needs hand-checked ground truth, and at
21x33 px distant bots cannot be counted honestly by eye.

### Ranging: use the nameplate, not the box height

The body box height is `BODY_H x bar_width` by construction, so **ranging by box height
is already ranging by nameplate width**, just multiplied by a constant — it is not
pose-dependent and does not get noisier at melee range. The short box the lead saw
(head-to-waist, 0.167 of frame height, frame 000334) is therefore a constant-factor
*bias*, not noise: distances come out systematically wrong by a fixed ratio, not
scattered.

Two ways to settle it, and the first is better:

1. **Range on the bar directly.** It is measured rather than synthesized, and it stays
   visible when the body is occluded or clipped by the frame edge — which is exactly the
   melee case that prompted the question.
2. Raise `BODY_H` to the measured full-silhouette ratio (median 1.62 of bar width, p25
   0.57, p75 2.33) so the box looks right. This adds no information — same number, bigger
   constant — and the wide spread means the box will often overshoot into the ground.

## Native-resolution aim path (lead direction)

The aim path will run on a ~960 px native crop of the 2560x1440 capture, where a bot
is ~42x66 px instead of 21x33; full-frame 720p stays the slow search pass.
`outline.py` takes an explicit `scale` and returns boxes in the pixels of the frame it
was given. **Scale cannot be inferred from a crop** — a 960 px square cut from a 1440p
capture is 960 tall but its nameplates are 2.0x, not 1.33x — so the caller passes
`scale=2.0` and adds the crop origin itself.

Precision/recall/latency for outline alone at both sizes is owed before anything is
retrained on outline boxes. Recall needs hand-checked ground truth, and native frames
make that materially more reliable: at 21x33 px distant bots cannot be counted honestly
by eye, which is the main reason the current recall figure is not quoted.

With that on, `outline.py` becomes colour-keyed segmentation: high precision *and*
high recall, giving the body silhouette directly instead of guessing it from a
nameplate, and good enough to auto-label for YOLO. Without it, the classical route
measures ~19% precision and is structurally blind to the Galacta bots, which carry
white nameplates and no red bar at all.
