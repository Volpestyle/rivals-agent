# Proposal: a latent world model (world model v4), local-first

**Status (2026-09-30): DRAFT for the lead, not approved, nothing launched.** Author: rl lane (VUH-1321).

## Why: what the pixel-space runs showed

All numbers are on James's held-out footage (025230 and 205528), with 768 windows and 1 seed. The evals live in
`rl/world_model/out/*/eval.json`.

| Run | Model | PSNR mean-prediction +1 / +2 / +3 s | Sampled +0.1 / +3 s | Imagined-frame AUC hit / KO (real) | Modal $ |
|---|---|---|---|---|---|
| copy-last | – | 12.7 / 12.4 / 12.3 | – | – | – |
| full-01 | 30M, 72x128, 4-frame context, 93 min | 15.6 / 15.0 / 14.9 (half res) | 17.1 / 14.5 (half) | – | 5.00 |
| v2-noroll | 58M, 144x256, 12-frame context, 170 min | 15.2 / 14.8 / 14.6 | 14.1 / 14.0 | 0.67 / 0.71 (0.97 / 0.997) | 13.42 |
| v2-main | as v2-noroll, plus own-rollout training | 15.3 / 14.8 / 14.6 | 14.2 / 14.0 | 0.63 / 0.69 (0.97 / 0.997) | 14.93 |
| v3-expert | v2-main plus 190 min of expert footage (idm v2-a) | 15.3 / 15.0 / 14.8 | 13.9 / 14.0 | 0.56 / 0.65 (0.97 / 0.997) | 17.52 |

What these runs taught us:

1. **Scale in pixel space bought nothing past 1 s.** Doubling the resolution and the parameters, and adding 1.8x the
   data, left the +2-3 s error where full-01 had it. At half resolution, full-01 still matches v2 or edges it.
2. **The 2-3 s error is content, not the camera.** Per-window PSNR at +2..3 s is almost flat across quartiles of
   logged yaw (15.1 / 14.6 / 14.6 / 14.7 dB; Spearman 0.13). The scene dissolves whether James turns or not. The
   model can't keep a scene it last saw more than 1.2 s ago, and its pixels go to high-frequency detail.
3. **The samples collapse contrast from the first imagined frame.** They have 43-67% of the real pixel std and are
   brighter by 0.06 of the range. More Euler steps make it slightly worse (14.2 / 13.8 / 13.5 dB at 5 / 10 / 20 steps),
   so this comes from the model, not the sampler.
4. **Own-rollout training (scheduled imagined context) was a null result**, within noise at 1 seed.
   **Expert footage helped a little at long horizons and hurt at short ones:** +0.2 dB at 2-3 s, -0.35 dB at +0.1 s.
   It is the only run that edges full-01 at 2-3 s (+0.15 dB at half resolution), but its imagined-frame AUCs are
   the worst. Expert frames earn a place in the tokenizer (no labels needed), not yet in the dynamics.
5. **The reward signal doesn't survive imagination.** On real frames the head is excellent (KO AUC 0.996-0.999, hit
   0.97-0.98). On imagined frames it falls to 0.63-0.71, so imagination RL would optimise noise.

## What: tokenizer plus latent dynamics with a long context

- **Tokenizer (new).** A convolutional autoencoder maps 144x256 frames to an 18x32x16 latent (8x downsampling),
  either continuous (small-KL VAE) or FSQ-quantised.
  - Loss: L1, plus LPIPS-style perceptual loss, plus a light patch-GAN after warm-up, which buys sharpness by
    construction.
  - It needs no action labels, so it trains on every frame we may use: own 170 min, plus all the expert footage
    the idm lane has packed (third-party frames stay private and are deleted afterwards). The dynamics trains on
    own footage first; expert windows come in only if an ablation at the +2 s keep line shows they help.
  - Gate before any dynamics work: reconstruction PSNR ≥ 28 dB on held-out frames, contrast ratio ≥ 0.95, and the
    reward head's KO/hit AUC on reconstructions within 0.02 of real frames. If the tokenizer loses the KO cue,
    everything downstream is moot.
- **Dynamics.** The existing EDM denoiser (`rl/world_model/model.py`) moves to latent space: 32 context frames
  (3.2 s at 10 Hz, 2.7x v2's context) plus a key-frame slot, a latent from 5-10 s back, as persistent scene memory.
  It uses the same action conditioning, known mask and source one-hot as v3. A Genie-style space-time transformer is
  the follow-up if the U-Net saturates.
  - A latent frame is 9,216 values against 110,592 pixels, 12x smaller, so each step costs roughly 10x less. That
    pays for the longer context and more training steps on local hardware.
- **Reward heads on latents,** trained on real latents plus latents noised the way imagined ones are, then scored on
  imagined rollouts. That imagined-frame AUC is the Phase C gate.

**Expected gains, and the risks.** Sharp decoded frames at every horizon (the decoder never averages), plus 3.2 s
of memory where v2 had 1.2 s. Published latent world models (DIAMOND's CS:GO upsampler, GameNGen, Genie) hold scenes
for seconds with long contexts. The risk is that our 3 h of own footage, in a dynamic courtyard, is too little data
for 3 s consistency even in latent space. The tokenizer gate and a +1 s check catch that early and cheaply.

**Success at +2 s and +3 s on 025230:**
- Sampled PSNR at least 2 dB above copy-last and above full-01's sampled frames.
- Contrast ratio ≥ 0.85.
- Imagined-frame KO AUC ≥ 0.90.

Phase C starts only if all three hold.

## Compute: local first

| Stage | Where | Estimate |
|---|---|---|
| Stage the 3 caches the Mac lacks (203745, 035932, 045729; about 20 GB) from rivals-explore-chunks | Mac | ~0.5 h transfer, Modal egress only |
| Tokenizer, ~20M params, batch 32, 60k steps | Mac MPS (nice 10, taskpolicy -b) | ~4-5 h (an estimate: first timed on a 500-step probe) |
| Encode every frame to fp16 latents (about 450k frames, ~8 GB) | Mac MPS | ~0.5 h |
| Latent dynamics, ~40M params, 32-frame context, batch 64, 60k steps | PC 4080, game closed, polls `Marvel-Win64-Shipping`, checkpoints every 2k steps and yields | ~2-3 h, in one or two windows |
| Eval and video on held-out own footage | PC 4080 or Mac | ~0.5 h |

That is about 5-6 h on the Mac and 3-4 h on the PC, with $0 of cloud spend.

**Optional Modal line, only if local windows don't come.** At today's measured rate (v2-main: $16.11 for a
178-min H100 run including load and eval, about $5.4/h) the paid stages would be:

| Paid stage | Question it answers | H100 time | Cost | Keep it if (stated before launch, checked after) |
|---|---|---|---|---|
| Tokenizer | Can a compact latent keep the scene and the KO/hit cues? | ~1.5 h | ~$8 | Held-out reconstruction PSNR ≥ 28 dB, contrast ratio ≥ 0.95, and reward-head AUC on reconstructions within 0.02 of real frames (KO ≥ 0.97, hit ≥ 0.95) |
| Latent dynamics plus eval | Does a 3.2 s latent context hold a recognisable scene at 2-3 s, with rewards readable in imagination? | ~2.5 h | ~$14 | On held-out 025230, sampled PSNR at +2 s beats full-01's sampled frames (14.6 dB) by ≥ 1 dB, contrast ratio ≥ 0.85, and imagined-frame KO AUC ≥ 0.85 |

Each stage runs only after the one before it has met its keep line. Dynamics is over $10, so it goes to the lead
first. A stage that misses its line is recorded as a failure, and nothing is built on it.
