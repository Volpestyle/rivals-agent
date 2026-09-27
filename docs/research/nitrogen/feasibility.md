# NitroGen as a starting point for the range policy: feasibility memo (2026-09-26)

Read-only research memo for the research lead. No weights were downloaded and nothing was trained or run. Sources were
read on 2026-09-26: the paper, the official code at commit `32608444` (2026-01-25), the Hugging Face model and dataset
cards, and the license files. **[V]** marks a fact checked in a primary source; **[I]** marks my inference or estimate;
**[U]** marks a question I could not confirm.

## TL;DR: conditional go, for one bounded offline experiment only

- **The official play harness is a hard no-go.** `nitrogen/game_env.py` pauses the game every step by injecting the
  `xspeedhack` DLL into the game process, and that is scope item 1 in `docs/plan.md`. The model can still be used on
  its own through our own pad executor.
- **The license fits a personal, non-commercial research project.** Weights and code are under the NVIDIA
  non-commercial research license, and the action dataset is CC BY-NC 4.0.
- **The published evidence for our case is weak.** The "52 %" is a best case: combat tasks, one held-out 3D action-RPG,
  about 30 h of target data, scored by human judges. Game-specific tasks gained only 5 %. We have 1.3-3 h. No shooter or
  Marvel title is named anywhere.
- **The architecture could still help with our specific failure.** NitroGen sees one frame, never reads its own past
  actions, and emits 16-step flow-matching chunks, so the copycat/idle pathway cannot form. The flip side is that it
  cannot remember anything, and our HUD is illegible at 256x256.
- **Worth one pre-registered offline fine-tune on the frozen interim cohort and dev split.** Its arms are: NitroGen
  init; the same architecture with stock SigLIP init; and the incumbent `model_nohud`. Estimated cost is about 10 L40S
  GPU-hours, roughly $20-25 on Modal **[I]**. Stop if the NitroGen init does not beat the stock-SigLIP control.

## 1. Facts

| # | Fact | Status | Source |
|---|---|---|---|
| F1 | Weights license: "NVIDIA License". Use is limited to "non-commercially", meaning "for non-commercial research purposes only", and excludes military, surveillance, nuclear and biometric purposes. Derivative works (a fine-tuned checkpoint counts) carry the same limitation (§3.2, §3.3). Breaking a term ends the license (§3.6) | V | [HF LICENSE](https://huggingface.co/nvidia/NitroGen/blob/main/LICENSE); the model card links [NVIDIA-OneWay-Noncommercial-License-22Mar2022.pdf](https://developer.download.nvidia.com/licenses/NVIDIA-OneWay-Noncommercial-License-22Mar2022.pdf) |
| F2 | Code license: the same NVIDIA License text (the GitHub `LICENSE` is byte-identical to the HF one apart from CRLF) | V | [GitHub LICENSE](https://github.com/MineDojo/NitroGen/blob/main/LICENSE) |
| F3 | Dataset license: CC BY-NC 4.0, "for research and development only". It holds **action labels only**, with no videos: per-frame gamepad state for about 30k YouTube-style videos and about 15B frames, split into 20 s chunks | V | [HF dataset card](https://huggingface.co/datasets/nvidia/NitroGen) |
| F4 | The vision backbone is SigLIP 2 under Apache 2.0, per the model card | V | [HF model card](https://huggingface.co/nvidia/NitroGen) |
| F5 | Architecture: a SigLIP vision transformer (256 tokens per frame), a self-attention "VL mixing" transformer, and a DiT with alternating self- and cross-attention that denoises an action chunk by flow matching. Per-embodiment linear action encoder and decoder. An optional game-ID token | V | paper [arXiv 2601.02427](https://arxiv.org/abs/2601.02427); `nitrogen/flow_matching_transformer/nitrogen.py` |
| F6 | Parameters: 4.93e8. `ng.pt` is 1,974,723,762 bytes, consistent with fp32 | V | model card; [HF file tree](https://huggingface.co/api/models/nvidia/NitroGen/tree/main) |
| F7 | Vision tower variant. The card says SigLIP 2 and links `siglip2-base-patch16-224`; the code's default is `google/siglip-large-patch16-256` with a hidden size of 768. The real value sits in the checkpoint's `ckpt_config` | **U** | card; `nitrogen.py` L54-55 |
| F8 | Input: one 256x256 RGB frame. `play.py` resizes the whole game window to 256x256 with `INTER_AREA`, so 16:9 is squashed. The paper says it finds "no benefit from using more than one past frame". Context length is 1 frame (`frame_per_sample=1`, `serve.py --ctx 1`), and there is no action-history input (`action_interleaving=False`) | V | paper; `nitrogen/cfg.py`; `scripts/play.py` L57; `scripts/serve.py` |
| F9 | Output: a 16-step action chunk, 21 dimensions per step: 17 binary buttons and two continuous 2-D sticks in [-1, 1], with triggers treated as buttons. Buttons threshold at 0.5. Inference runs 16 Euler flow steps (`k=16`) and optionally CFG | V | model card ("21x16"); `mm_tokenizers.py` (`action_horizon=16`, `unpack_actions`); paper |
| F10 | Action rate: `play.py` runs `env_fps=60` with `action_downsample_ratio=1`, so a chunk covers 16/60 = 0.27 s at inference. The dataset labels one row per source-video frame, and the paper does not state the video fps | V (code) / **U** (training rate) | `scripts/play.py` L96; `inference_session.py` L68 |
| F11 | Inference latency and hardware: not reported. The official evaluation is synchronous: the game "freezes ... while the model predicts", and Appendix B argues that pausing does not change the physics | V (not reported) | paper §eval, App. B |
| F12 | **How the pause is done:** `GamepadEnv` creates `xsh.Client(process_id=game_pid)` and calls `set_speed(0.0/1.0)` around every step. That is a DLL speed hack injected into the game process. `xspeedhack` is a default dependency in `pyproject.toml` | V | `nitrogen/game_env.py` L7, L473-507; `pyproject.toml` |
| F13 | The pad in the official harness is `vgamepad.VX360Gamepad`, the same ViGEm path our L0 gate accepted | V | `game_env.py` L178; `docs/plan.md` L150 |
| F14 | Released code: inference only (`serve.py`, `play.py`, `InferenceSession`). **There is no trainer, data loader or fine-tuning script.** The model's `forward()` does compute the flow-matching training loss, and the tokenizer has a training-mode `encode` that packs actions, so a fine-tune loop is a small amount of new code. Published hyperparameters: AdamW, weight decay 0.001, constant LR 1e-4 | V | `nitrogen.py` L509-577; `mm_tokenizers.py`; paper |
| F15 | Fine-tuning results. Pretrain with one game held out, then fine-tune on that game. Two games: "an isometric roguelike and a 3D action-RPG". The average relative gain is 10 % (roguelike) and 25 % (action-RPG). "Up to 52 %" is the combat tasks in the low-data (30 h) regime, and game-specific tasks gained 5 %. The metric is human-judged task-completion rate. Fine-tune compute is not disclosed | V | paper §post-training, Fig. 7; [project page](https://nitrogen.minedojo.org/) |
| F16 | Zero-shot evaluation: 10 games (5 2D, 5 3D), 30 tasks (11 combat, 10 navigation, 9 game-specific), human-judged, with "non-trivial success rates". The README says it cannot "play completely unseen game" end to end | V | paper; [GitHub README](https://github.com/MineDojo/NitroGen) |
| F17 | Dataset: 40k h across more than 1,000 games. Action-RPG is 34.9 %, platformer 18.4 %, action-adventure 9.2 %. 846 games have ≥ 1 h and 91 have ≥ 100 h. Labels were extracted from on-screen controller overlays (joystick R² 0.84, button accuracy 0.96). The data is biased to gamepad games; the card says the model is "less effective on games that rely heavily on mouse and keyboard" | V | paper; project page; model card |
| F18 | **No game list is published.** Neither the paper, the cards nor the site names Marvel Rivals, Spider-Man, Overwatch or any shooter. Each chunk's `metadata.json` has a `game` field, but it sits inside 1.4-1.7 GB tar shards. `InferenceSession.from_ckpt` prints the checkpoint's game mapping if one is embedded | **U** | dataset card and tree; `inference_session.py` L127-131 |
| F19 | `ng.pt` loads with `torch.load(..., weights_only=False)`, a full pickle. Loading it can execute code | V | `inference_session.py` `load_model` |
| F20 | The inference code hard-codes CUDA and bf16 autocast (`device="cuda"`), so the Mac/MPS path needs a small patch | V | `inference_session.py` L231-264 |

## 2. Can it run where we need it?

- **VRAM.** bf16 weights are about 1 GB, so inference should need about 2-3 GB with activations for 1x256 tokens
  **[I]**. That fits the 4080 SUPER's 16 GB next to the game on memory alone.
- **Latency is unmeasured, and the authors never ran it in real time (F11).** Per chunk it runs one vision pass plus
  16 × (VL mixing + DiT). `get_action` recomputes the VL mixing inside the loop even though its input does not depend
  on the actions, so hoisting it is a free refactor.
  - My order-of-magnitude estimate for a 4080-class GPU in eager PyTorch is 20-80 ms per chunk, before any contention
    with the game **[I]**.
  - One chunk spans 16 steps (0.53 s at our 30 Hz), so even 100 ms per chunk supports real time if chunks are
    executed asynchronously. Between chunks the policy then runs open loop for 4-16 steps.
  - Fewer flow steps (4-8) are a standard latency lever **[I]**.
- **The real live question is the game's frame-time cost while it shares the GPU.** The learning plan already requires
  this to be measured (capture-to-action latency, game fps). The Mac is a possible inference host, but frame transport
  to it is unmeasured and the plan already notes a 63-90 ms network floor.
- **Conclusion:** plausible at 10-30 Hz decisions using chunked execution, not proven. None of this matters until the
  offline experiment shows benefit.

## 3. Mapping our data to NitroGen's action space

Our labels are semantic actions (hold, press and release for 15 actions) plus camera in degrees per 30 Hz step
(`policy/range_bc/vocab.py`). The live executor already turns them into pad states: `executor.pad_state` maps moves to
the left stick (a unit vector), actions to buttons and triggers through `agent.pad_bindings` (James's alt profile), and
degrees per step to right-stick deflection through the measured `Cal` maps (`stick_for`). So a pad-space label
**derived through our semantic/degree layer** already exists, and it is exactly what the pad would have been sent. That
satisfies `docs/learning-plan.md` L93: no mouse counts touch a stick axis.

Ranked options:

1. **A, native pad-space relabel (recommended first).** Train NitroGen's own 21-dim chunk head on
   `pad_state(held, press, yaw, pitch)` per step.
   - Buttons: LB = jump, RT = spider_power, LT = web_cluster, RB = get_over_here, A = web_swing, B = amazing_combo. The
     masked actions stay 0. Left stick = move vector. Right stick = `stick_for` deflection.
   - Decode back for our metrics: buttons → held; a rise → press (the same hold model as `decode_step`); stick → deg/s
     through the forward `Cal` map, then degrees per step.
   - Pros:
     - It keeps every pretrained weight, including the action encoder/decoder and the "right stick = camera rate"
       prior.
     - The training target equals the executed command, so there is no train/live head mismatch.
   - Cons:
     - It is lossy. Taps shorter than a step become one-step holds, which is already the live contract. Camera
       requests beyond the pad cap (13.8° yaw, 3.3° pitch per step) are clipped. The `Cal` maps are stale for the
       247/124 alt profile (the executor docstring), and the caveat on the degree gain applies.
     - Game-specific button semantics are not transferable anyway. RT does not mean "Spider-Power" in the pretraining
       games.
2. **C, NitroGen trunk with our heads inside the chunk.** Replace the per-embodiment action encoder and decoder with a
   fresh one over 15 hold bits plus 2 continuous degree dimensions (for example, signed-log degrees). The vision, VL
   mixing and DiT stay pretrained. This keeps the degree target unclipped, but it gives up the action-head prior. Use it
   if A's clipping or the stale `Cal` dominate the camera error.
3. **B, frozen NitroGen vision/VL features into our recurrent heads.** This is the cheapest integration, but it brings
   back the history input that produced the copycat collapse (the history-only twin has the lowest dev loss, per
   `docs/lanes/end-to-end-fit.md`, "What the plumbing reports showed"). It also has to beat stock SigLIP features to
   justify NitroGen at all. Keep it only as a diagnostic arm.

Structural caveats for every option:
- **Resolution.**
  - A 256x256 squash of 2560x1440 is a 10x/5.6x downscale. The range-BC design chose a 128x128 crop from the native
    256x256 crosshair region because "a far Galacta is a few pixels at 256x144", and it notes that HUD cooldown digits
    are illegible at 1/10.
  - NitroGen's tokenizer accepts several images per sample, so a crosshair crop and a HUD crop could be passed as
    extra images. That departs from pretraining, where only one frame was used.
- **Memory.** It has no memory beyond the frame. Tracer state, recent pulls and so on cannot be learned, the same
  limit our model has past about 3 s but worse.
- **HUD layout.** Training frames show the M&K HUD, and live pad play shows the pad HUD. This is not specific to
  NitroGen.

## 4. Zero-shot

- **Plausible as a cheap offline sanity check, not as a candidate.** Zero-shot NitroGen has never seen James's bindings
  or this game (F18 is unverified).
- A guarded offline check:
  - Run NitroGen on recorded dev frames (never live) with the game-ID token unconditional.
  - Score the predicted left stick against James's move labels, mapped through option A, for direction agreement.
  - Score the right stick for camera sign and onset agreement, and camera MAE against persistence (0.418°), AR(2)
    (0.376°) and zero motion.
  - Ignore button identity. Report only "any button active" against "any combat action active".
- **Expected result:** near chance on buttons, maybe above chance on the camera sign **[I]**. It needs the 2 GB
  download, a sandboxed pickle load (F19), and a CUDA box with the game stopped or a patched MPS path. It only tells us
  whether the prior "sees" this game. Fold it into the experiment below as arm Z rather than running it separately.

## 5. Proposed first experiment (offline; pre-register before any result)

**Question.** Does game-action pretraining help on our data, beyond what a generic pretrained image encoder and the
architecture (single frame, chunked flow-matching) give?

**Data.** Exactly the countermeasure rounds' inputs:
- train: the five interim sessions (80.53 counted min);
- dev: 171533 + 205528;
- regime `normal`, lag 0, the `vocab` live mask;
- `docs/evidence/range-bc-countermeasures-2-20260926/fit-countermeasures-2-prereg.md`.

Labels come through option A, built from the existing step tables with `executor.pad_state`. No validation or sealed
data.

**Arms (seed 0 first, then 0-2 only if seed 0 clears the kill criteria):**

| Arm | Init | Trained |
|---|---|---|
| N | NitroGen `ng.pt`, full fine-tune (vision layer 11 and head frozen, as in the code) | yes |
| S | Same architecture; vision from stock SigLIP 2 of the same size as F7; VL mixing, DiT and action layers random | yes, identical recipe |
| Z | NitroGen, zero-shot | no |
| A | Incumbent `interim94-s012` `model_nohud`, re-read (`A-reread.json`) | no |

- **S is the matched from-scratch control.** A fully random 493M model on 80 minutes would only measure overfitting.
  N − S isolates the game-action pretraining.
- **Recipe [I]:**
  - AdamW, LR 1e-4 constant with a short warm-up, weight decay 0.001 (the paper's values).
  - bf16, one 256x256 frame per 30 Hz step, a 16-step chunk target (0.53 s).
  - A fixed epoch count pre-registered from N's dev loss on a separate short plumbing run, the same F7 rule as before.
  - Final checkpoint only.

**Evaluation.** Recorded frames, so no live input.
- NitroGen reads no action history, so self-fed and teacher-forced inputs are identical offline. The honest analogue of
  "self-fed" is receding-horizon execution:
  - predict a chunk every *n* steps, *n* ∈ {1, 4, 8} pre-registered;
  - execute its first *n* steps;
  - decode those executed steps with the `decode_step` hold model.
- Reuse the round-2 judge's checks unchanged:
  - S1 hold-onset recall ≥ 0.05;
  - S2 press ratio in [0.5, 2.0] pooled, and ≥ 6 of 10 live actions in band;
  - S3 camera MAE ≤ 0.95 × zero-motion (≤ 1.163° on this dev);
  - S4 any-hold share in [0.35, 0.91];
  - the self-fed macro press-F1 (±1 step).
- Also report:
  - camera MAE against persistence 0.418° and AR(2) 0.376°, per axis, against both raw and pad-clipped targets;
  - decoded presses per action against human;
  - the idle-run length distribution.
- **Caveat:** offline evaluation cannot show closed-loop covariate shift. Passing S here is necessary, not sufficient.

**Decision rules (fix before running):**
- Go to seeds 1-2 only if N passes S1-S4 on seed 0 **and** beats S on self-fed press-F1 by ≥ 0.02 **and** beats S on
  camera MAE.
- **Kill** if N does not beat S. The pretraining is then not the lever, and the single-frame chunked architecture can
  be tested from S cheaply without NVIDIA's license.

**Compute and placement [I].**
- Per sample, 6 × 4.93e8 × about 256 tokens ≈ 0.76 TFLOP is an upper bound. At about 145k samples per epoch that is
  about 1.1e17 FLOP per epoch.
- L40S (the round-3 Modal/AWS benchmark hardware) at about 60 TFLOP/s effective: about 30 min per epoch. N and S at
  about 5 epochs plus dev evaluation is about 6-10 GPU-hours, roughly $20-25 on Modal at current L40S rates. The price is
  unverified; check before launch.
- The Mac (MPS, 128 GB) can hold a full AdamW fine-tune (about 8 GB of state), but its effective bf16 throughput is
  unmeasured. Hours per epoch is plausible, so the Mac is fine for Z and for decoding, and cloud is better for N and S.
- The PC's GPU only while the game and recording are stopped (AGENTS.md).
- Frames leaving our machines for Modal is a lead/James data decision (open question 3).

**New code (small, in a new lane path, reviewed like any fit code).**
- A NitroGen adapter module: option-A labels, a chunk dataset over the existing frame caches resized to 256x256, and a
  training loop around `NitroGen.forward`.
- An MPS patch for inference.
- The option-A decoder.
- **Vendor only** `nitrogen/flow_matching_transformer/*` and `mm_tokenizers.py`, pinned to commit `32608444`. Never
  install the package with its default dependencies, which pull `xspeedhack`, and never import `game_env.py` or
  `play.py`.

## 6. Risks and no-go triggers

- **Scope (hard).** The official harness injects a DLL (F12). We use only the model. The live path stays `agent.controller.Live` with no pause, so the policy
  must work in real time, which the authors never demonstrated.
- **Weak transfer evidence.**
  - The target data is 10-20x smaller than the paper's low-data point.
  - The gains are largest on generic combat and near zero on game-specific skills. Web swing, Get Over Here! chains
    and combos are game-specific.
  - The dataset is biased to gamepad action-RPGs, and shooter coverage is unknown.
- **The observation is too coarse.** At 256x256 with no memory, cooldowns, ammo and far bots are likely invisible. That
  could cap skill below the incumbent even if idle collapse disappears.
- **Camera.** A continuous stick output is a good fit in principle. But our camera targets are mostly above the
  calibrated band, 92 % of yaw motion (`d1201f2`), and the `Cal` maps are stale for the current alt profile. The camera
  comparison may be dominated by calibration, not by the model.
- **The license binds derivatives.** Any fine-tuned checkpoint is non-commercial research only (§3.3). If this ever
  touches monetized content, sponsored use, or RCSStudio/PMC/Vibes work, it is a no-go.
- **Security.** Pickle load (F19). Load once in a sandbox, re-save as `safetensors` plus a JSON config, and hash-pin it.
- **Latency and GPU contention.** If a chunk plus capture cannot hold ≥ 10 Hz next to the game without an fps drop,
  that is a live no-go even after an offline win.

**No-go if any of these hold:**
1. N ≤ S offline.
2. N fails S1-S4 in the same way A does.
3. The measured live latency or fps cost is unacceptable.
4. The use would become commercial.

## 7. Open questions

1. **What is the vision tower and the game list?** Both are in the checkpoint's `ckpt_config` (F7, F18). One sandboxed
   load answers them, and it needs approval for the 2 GB download.
2. **At what rate were the training actions labelled (30 or 60 fps)?** This decides whether our 30 Hz chunks should be
   upsampled.
3. **May the interim frames go to Modal**, or must N and S train on the Mac? This is a data-custody decision for the
   lead and James.
4. Should crosshair and HUD crops be added as extra image tokens in a second round, if N beats S but fails on
   aim/cooldown-dependent actions?
5. Is option A's clipping or the stale `Cal` responsible for camera error? Run the camera metric on both raw and
   clipped targets to find out.

## Sources

- Paper: <https://arxiv.org/abs/2601.02427> (HTML <https://arxiv.org/html/2601.02427>); PDF
  <https://nitrogen.minedojo.org/assets/documents/nitrogen.pdf>
- Project page: <https://nitrogen.minedojo.org/>
- Code: <https://github.com/MineDojo/NitroGen> at `32608444660950ffda95e1e57c79632ad65bea10`. Read: `LICENSE`,
  `README.md`, `pyproject.toml`, `nitrogen/{cfg,shared,mm_tokenizers,inference_session,game_env}.py`,
  `nitrogen/flow_matching_transformer/{nitrogen,modules}.py`, `scripts/{play,serve}.py`
- Model card and files: <https://huggingface.co/nvidia/NitroGen> (`README.md`, `LICENSE`, `EXPLAINABILITY.md`,
  `SAFETY.md`, `BIAS.md`)
- Dataset card: <https://huggingface.co/datasets/nvidia/NitroGen>
- License PDF: <https://developer.download.nvidia.com/licenses/NVIDIA-OneWay-Noncommercial-License-22Mar2022.pdf>
- In repo:
  - `docs/plan.md` (scope boundary);
  - `docs/learning-plan.md` (L60-L117 contract, L555 compute);
  - `docs/lanes/end-to-end-fit.md` (§1, §2, plumbing results);
  - `policy/range_bc/{executor,vocab,model}.py`, `agent/pad_bindings.py`;
  - `docs/evidence/range-bc-countermeasures-2-20260926/`;
  - `docs/machines.md` (cloud accounts).
