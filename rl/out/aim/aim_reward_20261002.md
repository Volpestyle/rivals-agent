# Dense aim reward, offline validation, 2026-10-02 (VUH-1321)

**Result: built and wired in (opt-in). The signal is real but weak and sparse.** In the 1 s before a hit or KO the
aim shaping is positive 1.7x more often than in other windows (57% vs 34% of windows that have a term, binomial
p = 0.003). That comes from 35 clustered events, mostly from scripted runs. In the RL sittings a frame-to-frame term
exists on only 24% of retained frames, because the finder flickers, abstains and switches. Oscillation nets exactly
zero. Offline only: no game input, decode, GPU or cloud. Cost $0.

Code: `rl/aim/reward.py` · wiring `rl/online/data.py` (`reward_aim`, `aim_known`), `rl/online/update.py`
(`aim_weight`), `rl/online/sitting.py --aim-weight` · tests `tests/test_rl_aim_reward.py` (11) ·
[contact sheet](aim_reward_20261002_sheet.jpg) · [numbers](aim_reward_20261002.json) ·
scripts [scan](aim_reward_scan_20261002.py) (per-frame reads, [jsonl](aim_reward_scan_20261002.jsonl)) and
[analysis/sheet](aim_reward_20261002.py).

## Design

- **Potential.** Phi = -min(d, 1). d is the distance from the crosshair (the screen centre) to the centre of the
  guarded target vector's *nearest* box (`policy.bc2.target_features.extract`), measured in half screen widths (640 px
  at 720p). Phi is 0 on the crosshair and -1 at the side edge. "Nearest" depends on the frame alone, so when two
  persistent bots swap as nearest, both are the same distance away at the swap and Phi stays continuous.
- **Shaping.** F = gamma * Phi(s') - Phi(s) between consecutive retained frames, with gamma = 1 by default. Any
  unbroken run of F sums to Phi(last) - Phi(first), so oscillating or holding still earns nothing.
- **None, never zero.** No term (None) is given, and the chain re-anchors, in these cases:
  - unknown target (door abstention or no detection);
  - the first known frame after an unknown one, or after a gap of more than 0.5 s, so reacquisition is never paid;
  - a **switch**: the nearest box moves more than 0.25 half-widths or changes height by more than 1.6x between two
    frames.

  The switch gates come from the measured step distribution on these frames. 90% of steps move under 0.11. Pad turns
  are at most about 2.6 deg (~0.04) per decision. The jumps above 0.3 are box flicker and full-stick period turns. A
  switch covers a box appearing or vanishing: a KO'd bot disappearing is not a penalty, and a new bot appearing near
  the crosshair is not a reward.
- **How the update uses it.** Do not add F to the discounted Monte-Carlo return. There it telescopes to -Phi(s_k)
  plus a distant end term (proved in a test). That is a state term the constant AWR baseline does not cancel, so it
  would favour steps that *start* off target. `update.aim_advantage` instead adds `aim_weight x` (the sum of F over
  the next 0.5 s), which is Phi(k+0.5 s) - Phi(k): "did the camera bring the target closer". In effect Phi acts as a
  heuristic critic over a short horizon. Each F is credited to the decision at the start of its interval.
  `reward` (sparse) is unchanged, and `aim_weight = 0` reproduces the old weights exactly (tested).
- **Cost.** The guarded extract costs **18 ms per retained frame single-threaded at below-normal priority** (scan
  median, p95 21 ms). It costs about 2 ms with OpenCV's default threads. The hit and KO readers add 1.4 ms. It runs
  in `data.episode` between episodes, not in the live loop. A real 20 s episode (138 frames: JPEG read, hp, markers
  and aim) took 2.5 s in total.

## Validation (4,805 retained 1440p JPEGs, 46 runs)

Sources: RL sittings 01/04/07 (excluded episodes 07-008/012/015 skipped), compat learned-01-a, the `data/l1` range
runs and the alt-20260926 camera-period frames. Denylist and exclusions were checked. The frames are 5-17 Hz. Readers
found 46 hits and 3 KOs; only 3 of those hits are in RL sittings.

**1. Hand inspection** ([sheet](aim_reward_20261002_sheet.jpg), 19 tiles; yellow = raw finder boxes, magenta =
chosen nearest target, with Phi, F and the reason under each tile). What it shows:
- The door (01) and empty views (02, 03) give None.
- Tile 00 is an abstention on **green foliage with no door in view**. The teacher's green-share rule also suppresses
  real bots in that part of the courtyard.
- Two-bot frames (04-06) pick the box nearest the crosshair. Tile 05 picks a hero bot at the far right.
- Small or partial bots (07, 08) are found. Tile 07's +0.12 is a correct turn onto a distant bot.
- 10 and 11 are a real turn toward a bot (+0.115) and the target drifting off (-0.174).
- Switches (12, 13) are cut. Tile 14 reacquires on what looks like a railing box (a false detection).
- **At the hit frames themselves (15, 16) the finder changes the box: hit effects trigger a switch cut.** At the KO
  (17) the dying bot at the crosshair has no box, so the nearest is another bot 0.43 away. Both are cut, so neither
  is penalised.

**2. Does it mean something?** The test sums F over the 1 s before each hit or KO onset. The baseline is every other
1 s window that does not overlap an event.

| | windows | with a term | positive (>0.005) | given a term | negative given a term | mean given a term |
|---|---:|---:|---:|---:|---:|---:|
| before a hit/KO | 49 | 35 | 20 | **0.571** | 0.257 | +0.023 |
| other windows | 3,979 | 1,861 | 623 | **0.335** | 0.298 | +0.001 |

Binomial p (20 of 35 at 0.335) = 0.003. The ratio holds at stricter thresholds: 0.37 vs 0.21 at >0.02, and 0.20 vs
0.10 at >0.05. Phi at the event frame has a median of -0.046, against -0.106 for the baseline; 64% vs 49% of frames
are within 0.1. **Caveats:**
- The events are clustered: 12 come from one scripted run and 10 from another, so they are not independent.
- 34 of the 35 events with a term come from scripted or older learned runs with explicit aimers. The RL sittings
  contribute 1 event with a term, and its sum is -0.02.
- 14 of the 49 events have no term at all.
- Pre-hit sums are small (median about +0.01), because aimers already sit near the target.

**3. Farming.**
- **Replayed oscillation**: 61 real unbroken runs, each played forward and back 5 times. Net is 0.0 in every case
  (median gross 1.37).
- **Synthetic sweep**: a ±200 px sweep for 500 frames with a finder flicker every 7th frame. Net is -0.30 against a
  gross of 42.5, so flicker gaps add no systematic gain.
- **Camera-period runs** (continuous turns past the same bots): net between -0.002 and +0.12 per run. Most frames
  there are switch cuts.
- Holding still pays 0.
- The residual exploit is bounded. Only a cut can change the books: a box vanishing near the crosshair and the agent
  then climbing onto another. Across all runs, the cut Phi differences sum to -3.98 (|.| 28.75), against 18.5 of
  gross paid shaping. In other words, **flicker moves Phi more than the paid terms do**, and cutting is what keeps
  that out of the reward.

## Weight

Start with **`--aim-weight 0.3`** per unit Phi: a full edge-to-centre acquisition is worth 0.3 of a hit. On the RL
sittings, 0.5 s aim windows have std 0.057 (p95 |0.13|), so at 0.3 the aim advantage has std ~0.017. A single hit
gives a 20 s episode a return std of 0.24, about 14x larger, so hits and KOs still carry the outcome.

**Note:** `weights()` normalises advantages by their pooled std. With no hits in the buffer, any `aim_weight > 0` makes
aim the whole signal, at a strength set by `beta`. That is intended early on, but watch the KL.

## Limits

- Sparse on RL data: there is a term on 24% of retained RL-sitting frames (the target is known on 30%). Spawn-room
  door and foliage abstention, and empty views, dominate.
- The finder misses partly hidden and dying bots, boxes some scenery (tile 14) and fragments boxes.
- It is nearest-box aim with no identity and no line-of-sight check, and box centres are not hit boxes.
- `persistent_sitting.py` does not pass `aim_weight` yet.
