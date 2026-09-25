# scoreboard-fix: the edge head's input, HUD crops after the interval (part B) (VUH-1353)

2026-09-25.
- **Pre-registration:** lane doc "### The edge head's input: HUD crops after the interval (pre-registered
  2026-09-25)", LF sha256 `4247102d1e328b134a51be6d526c18b831c7c4d5daee15abe60944a6230baeb2`. It was sent before any
  code or run and is unchanged.
- **Store layout:** the stores served t1 + 16 without a rebuild. Every row with a complete motion window already has
  the t1 + 8 and t1 + 16 crops; there were 0 missing frames and the same 144,932 train examples as today's arm.
- **Not done:** no commits to main, no Linear, no game input.

## Result against the judge

The judge is part C's protocol on fold 051828: rate-matched thresholds from each arm's own train sessions, the band
off, the landed `idm_eval`, and chance as 20 seeded draws.

| Action | Held-out onsets | **Today:** F1 / chance / ΔF1 / AUC | **Lag (t1 + 8, t1 + 16):** F1 / chance / ΔF1 / AUC | Decides |
|---|---|---|---|---|
| **amazing_combo** | 60 | 0.039 / 0.009 / +0.030 / 0.797 | **0.108 / 0.019 / +0.089 / 0.877** | yes |
| **jump** | 361 | 0.104 / 0.057 / +0.048 / 0.733 | **0.069** / 0.060 / +0.009 / 0.729 | yes |
| spider_power | 110 | 0.011 / 0.018 / −0.008 / 0.562 | 0.059 / 0.029 / +0.031 / 0.609 | yes |
| web_cluster | 226 | 0.022 / 0.040 / −0.018 / 0.602 | 0.041 / 0.040 / +0.001 / 0.609 | yes |
| web_swing | 83 | 0.077 / 0.018 / **+0.059** / 0.631 | 0.013 / 0.009 / +0.004 / 0.655 | yes |
| get_over_here | 27 | 0.000 / 0.006 / −0.006 / 0.606 | 0.000 / 0.000 / +0.000 / 0.580 | no (< 30) |
| team_up | 24 | 0.000 / 0.007 / −0.007 / 0.698 | 0.000 / 0.014 / −0.014 / 0.707 | no (< 30) |
| move_forward | 151 | 0.006 / 0.034 / −0.028 / 0.546 | 0.020 / 0.033 / −0.014 / 0.564 | yes |
| move_left | 183 | 0.028 / 0.026 / +0.002 / 0.546 | 0.027 / 0.031 / −0.004 / 0.541 | yes |
| move_back | 132 | 0.041 / 0.022 / +0.019 / 0.500 | 0.042 / 0.020 / +0.022 / 0.531 | yes |
| move_right | 156 | 0.006 / 0.031 / −0.025 / 0.457 | 0.029 / 0.034 / −0.005 / 0.436 | yes |

**The pre-registered reading: the lag arm "helps".**
- **amazing_combo** (the only one of the three abilities with ≥ 30 onsets on this fold) now clears chance by
  **+0.089** F1, where today's input gave +0.030. Its AUC rises from 0.797 to 0.877.
- **Jump's F1** falls by 0.036 (0.104 → 0.069), within the 0.05 allowed.
- **The movement keys are unchanged, as expected:** ΔF1 stays between −0.03 and +0.02 in both arms, and AUC 0.44–0.56.

## My call, beside the rule

The rule is met, and the direction is what the mechanism predicts. The HUD crops after the interval see an ability's
cooldown start. amazing_combo's lag is 0.3–0.5 s, so a +133 ms crop catches only its early part; its AUC still gains
0.08. spider_power moves the same way (AUC +0.05, ΔF1 −0.008 → +0.031).

**Three caveats before anyone relies on it:**
1. **One seed, one fold.** The yaw tests showed how much seeds move a result here. An F1 of 0.108 at an onset rate
   of 0.24 % is a small absolute number.
2. **Jump's margin over chance nearly vanishes** (+0.048 → +0.009) even though its F1 drop stays within the rule. Its
   AUC is unchanged (0.733 → 0.729), so its ranking is intact, and the loss is in where the rate-matched threshold
   lands.
3. **web_swing loses its margin over chance** (+0.059 → +0.004), while its AUC rises slightly (0.631 → 0.655).
   web_swing is not one of the three judged abilities, but it is a supported action that got worse at the decision
   threshold.

**What would settle it** (a proposal, not run): the lag arm at seeds 1 and 2 on the same fold, plus the 205528 fold
where team_up (42) and Get Over Here! (35) have ≥ 30 onsets, pre-registered with the same rule. That is about 4 fits
(1.4 h).

## Hashes (checked across the wire)

**Lag-arm run** (`C:\Users\volpe\repos\rivals-agent\data\idm\runs\b-lag\`, gitignored, with `b.log` / `b.exit`):
- 3 epochs, seed 0, plain loss, MPS, 1,212 s, 422,403 parameters.
- The config records `hud_offsets: [8, 16]`; `git_commit` is `b3112fc`, clean.

| File | sha256 |
|---|---|
| Checkpoint | `721c841dd0f9235984942c9ffd8ac5c2353408f717f49b1f9f7645eb83acfbdf` |
| report.json | `d7c15e7a14b925351f154173c4f377060de725609599b994c15b6c2c36bcefbc` |

**Lag-arm probabilities** (`scratchpad\idm-diag\press\b-lag-on-<session>.jsonl`):

| Session | sha256 |
|---|---|
| 051828 | `f8c55d1a96cab955fcaa4b46576064bb3a0e39ddfa3f3462ccc29a1f400b71b0` |
| 171533 | `0d28ad1025e7cb5eff169fcad48539a6f722aa991571acb3bc2d99b36a7b1f7f` |
| 200129 | `e1e106f589d2ead219f7d7a5850049ae4ad245d0ad3b3b8f8f07cdc0663b3d6c` |
| 205528 | `4850bd47162877a69d3806e1a84feed560b8de361a04892f2e01391cfd8a1abc` |

**Today's arm:** `loso-051828` (checkpoint `11d0b912…`) with its part-C probabilities `051828-on-*.jsonl` (hashes in
`idm-thresholds.md`).

**Scripts and outputs:**

| File | sha256 |
|---|---|
| `judge_b.py` | `ceec730403c1281931b3a3bd36179faf22c15df3a166a24d1c58bf1a321884b0` |
| `judge_b-out.md` | `bcb7e33a53b46899e755b4988f3bdf4d7c6c7a451b779a323fd30ce97ae370cd` |
| `judge_b-results.json` | `38ec49df9223fe0392d90ecacf7134efae91926ea4f38611603dbf358027be4d` |
| Mac queue `b.zsh` | `057d637e934137240c277543249d571fb5b57c8d8a55b111cd58e503b74b4e2b` |
| `press_predict_ckpt.py` | `3550e99a8d4f5c73f30b49c1e078e12d6fecdad59dcbd065407695c02336559e` |

## The code (branch, not main)

- **Branch** `idm/edge-hud-lag-20260925` at **`b3112fc59b0ad66ae2c61e54fb576c4a49da97ad`**, pushed. It is one commit
  on `fe5c9ca`.
- **What it adds:**
  - `Config.hud_offsets` (default `()`, validated as positive even offsets within the stored window);
  - `train.hud_frames`, with `Examples` reading 3·(2 + len(offsets)) HUD channels;
  - `--hud-offsets` on `fit`.
- **A default config's `as_dict` has no new key,** so a default checkpoint is unchanged.
- **Test** `test_hud_offsets_default_to_todays_input_and_add_crops_after_the_interval`:
  - default keys and 6 channels, against 12 with offsets;
  - the exact stored crops are read;
  - invalid offsets are refused;
  - a fit plus predict runs.
- **Tests on the branch:** 79 passed (execution group: model, decode, targets and eval; private `UV_PROJECT_ENVIRONMENT`),
  and ruff is clean.
- **Worktrees:** the private PC worktree is `C:\Users\volpe\repos\rivals-agent-idm-edge`, and the Mac worktree is
  `rivals-agent-worktrees/idm-edge`.

## Next on the Mac

A4 (Gate 1 with `--beta-nll`) is running now, chained after B. It will come as `idm-beta-nll-2-a4.md`.
