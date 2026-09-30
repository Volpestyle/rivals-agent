# RL and emergent behaviour (VUH-1321)

**Status (2026-09-30): CURRENT.** Owner: rl. Status lives on [VUH-1321](https://linear.app/vuhlp/issue/VUH-1321);
scope is [the plan](../plan.md) (practice range and AI-only custom games, pixels only, no memory reading); gates are
[the learning plan](../learning-plan.md) ("Reward contract before reinforcement learning", milestone D). This note
holds the lane's measured facts and design. Code: `rl/` (readers `rl/rewards.py`, offline scanner `rl/scan.py` and
`rl/audit.py`, world model `rl/world_model/`), tests `tests/test_rl_rewards.py`, `tests/test_rl_world_model.py`.

## 1. Reward readers from pixels

Validated 2026-09-30 on James's own non-sealed training takes (range: `20260923T051828`, `20260925T203745`,
`20260926T045729`; match: Quick Match `20260927T052001`, his own play, read offline). Hand checks are by the rl agent
from native crops, not by James. Labels: `rl/labels/hit_ko_crosshair_20260930.json`.

| Signal | Reader | Result | Sample |
|---|---|---|---|
| **Hit** | `hit_marker`: four white diagonal strokes round the crosshair (screen centre); bright-ridge runs on at least 3 of 4 arms | **Precision 1.00, recall 0.98 per frame** (158 TP, 0 FP, 3 FN, all faded tails of the marker; every hit's onset is caught) | 900 frames at 30 fps: three 10 s windows from three sessions, labelled blind, disagreements adjudicated at full zoom |
| **KO / elimination** | `ko_marker`: the red ring (r = 54 px at 1440p) round the red KO diamond, tested against its two sides so the red suit crossing the crosshair never fires | **142 of 142 detected KOs are real** (every event checked by eye). Every one of 120 kill-feed arrivals has a KO ring within 2 s, or 2.5-4 s earlier where the feed flickered off and on (5 cases), so **no KO was missed** | Two whole range sessions, 7.0 + 10.5 min at 10 fps; plus 4/4 in the 900 labelled frames |
| **Own hp** | `perception.hud.read_hp`, unchanged | **35/35 current and 32/32 max reads correct**; 5 and 8 unread (None), never wrong | 40 random hp-change frames from the match (the hard cases: hits, bonus health, shields) |
| **Damage taken** | `RewardTracker`: rise in the deficit (max - hp), both numbers confirmed on two reads | No false damage over 17.5 min of range play, where raw hp differencing found 500: Spider-Man's bonus health decays 300 to 250 with max and current falling together | Range sessions above; the match for real damage |
| **Death** | `RewardTracker`: hp read 0 twice | **3 detected, 3 real** in the match (two agree with the in-match scoreboard at 211 s; the third is on the kill feed, "Zero-Two507 > cowboyboopbop"); 2 range deaths checked by eye, both falls | The match; range below |

**All ten non-sealed range training takes, 186 min of James's play** (scanned 2026-09-30; per-frame scans in
`D:/rivals-agent-evidence/rl-reward-scans-20260930/`, event labels in `rl/labels/range_rewards_20260930.json`):
1,307 KOs (**7.0/min**, 3.9-8.7 per session), 5,795 hits (**31/min**), about 1.7x the scripted baseline's 4.2 KOs/min.
The 65 kill-feed arrivals with no KO ring within 2 s are all explained: 59 feed flickers after an earlier KO, 1 own
death, 3 scoreboard openings, 2 `is_killfeed` false positives on pale sky. None is a missed KO.

**Spider-Man does die in the range: by falling off the courtyard.** 10 deaths in 186 min (3.2/h), each a straight
250 to 0 on the hp digits, "SPECTATING" for about a second, then a respawn in the spawn room at full hp (~1.0-1.3 s
from the 0 read). James was back to his next KO 6-14 s later (median 8 s). The older records ("hero respawn
unmeasured and probably impossible", `placement.md`) predate this. A fall is both an RL penalty and a free reset to
the spawn room. **Bots rarely deal damage too:** two 25 hp hits in 186 min, one checked by eye (red damage flash
and direction arrow, 250 to 225).

**Floating damage numbers are not on James's screen** in any range or match footage checked; the setting appears to
be off, so they are not read. Turning them on for RL sittings would move the frames away from every BC training
frame. Outgoing damage comes instead from (a) hits, as a bounded proxy; (b) the range scoreboard
(`perception.scoreboard.read_scoreboard`, exact damage and KOs on native frames), read at episode boundaries with one
button press; (c) the kill feed, which also names the victim (GALACTA BOT, GALACTA BOT ULTRA, a hero), so a KO can
be tied to a target.

Limits and open points:
- **The kill feed is on screen in the range**, contradicting the older `perception/evalread.py` note, which was
  checked on other runs. `perception.scoreboard.is_killfeed` sees its presence; `killfeed_geometry.row_candidates`
  row counts are noisy in the range (2-3 rows while no feed is up) and are not used.
- In a match, after a death the crosshair and hp belong to the spectated teammate. The tracker drops every read until a
  respawn at the pre-death max hp, and needs `own` (`perception.events.playing_spiderman`, `rl/scan.py --hero`) to be
  safe when a teammate has the same max; the portrait check is fooled by the scoreboard's Spider-Man row. This only
  matters in AI-only custom games (milestone F); range bots almost never deal damage (§1).
- The KO ring marks our final blows. Whether the in-game "KOs" scoreboard column counts the same thing (rather than
  participation) is unchecked.
- Geometry is 16:9, scaled by frame height, checked only at 2560x1440 and on the keyboard/mouse HUD. The crosshair
  markers do not depend on the HUD layout; hp on the pad HUD layout is unchecked here.
- Offline scanning (`python -m rl.scan VIDEO OUT.jsonl --crops DIR`, then `python -m rl.audit OUT.jsonl`) runs at about
  real time on an idle PC; it decodes only the crosshair, feed, hp and portrait regions. Readers cost under 1 ms per
  frame, except `--hero` (~50 ms). Don't bulk-scan on the PC while the game runs.

## 2. Live episodes per hour (estimate from existing records; no live access)

Facts (M = measured, E = estimate):

- No reset is needed between range encounters: a Galacta bot is back at full health within ~4 s of a KO
  (M, `docs/evidence/galacta-pilot-20260923/README.md`, `docs/lanes/placement.md`), and the designated pair stands
  ~5.2 m apart, so the agent can switch bots instead of waiting.
- There is no in-range teleport or reset command, but falling off the courtyard kills and respawns the hero in the
  spawn room ~1 s later (M, §1, 10 falls in James's 186 min). From there the walk back is 12-15 s (M) and failed 2 of
  3 scripted trials (`docs/lanes/reentry.md`, `placement.md`); James needed 6-14 s from death to his next KO.
  A lobby drop still needs full re-entry (one first entry took 15 min).
- The idle drop needs ~10 min without a move or attack (M, `rivals-live-game` skill). A policy that moves never meets it.
- Scripted time-to-kill is ~3 s (M). A 5-minute scripted run made 21 KOs (4.2/min), but 2 of 4 runs stalled at 0 KOs
  (M, `docs/lanes/l4-controller.md`), so recovery, not resets, is the real overhead.
- Live stack: decisions 10 Hz, reflex 55 Hz, capture ~30 Hz, game at its 240 FPS cap with inference on
  (M, `docs/evidence/live-fps-20260928b/RESULT.md`). Supervised sittings so far ran 20-40 min.

Estimate for the one supervised game instance (rented GPUs speed training, not collection):

| | Per hour of sitting |
|---|---|
| Usable play after entry, settings, stalls and recovery (assume 75-85%) | 45-50 min |
| 20 s bounded encounters (the range-benchmark episode) | **~135-150** |
| KO-terminated encounters of 10-20 s including ~4 s respawn or switch | ~150-250 |
| Policy decisions at 10 Hz | ~27-30k |
| Frames at 30 Hz (world-model data) | ~80-90k |
| KOs (reward events): scripted 4.2/min to James's 7.7-8.7/min (§1) | ~190-430 |

That is ~1e5 environment steps per 3-4 sittings: enough to fine-tune a pretrained policy, and three to four orders of
magnitude short of learning Spider-Man from scratch with model-free RL. The design below follows from that.

## 3. First algorithm: offline-to-online advantage-weighted fine-tuning with a KL anchor to BC

**Pick: AWR-style advantage-weighted regression from the BC checkpoint, with an explicit KL-to-BC penalty, trained
offline first and then online (IQL-style expectile value learning, AWR policy extraction).** PPO with a KL penalty
(VPT's recipe; the learning plan's masked-PPO proposal) is the fallback once live throughput is proven.

Why this and not PPO first:

1. **It can start before any live sitting.** The readers label rewards on every recorded session (§1), so James's
   ~3-5 h of paired play becomes reward-labelled offline RL data today. Step 0 fits an expectile value function (no
   out-of-distribution action maximisation) on those rewards and re-weights the BC loss by `exp(A/beta)`. It must beat
   plain BC on held-out sessions before it goes live.
2. **It reuses the BC trainer unchanged**: the same LSTM model and data loader with a per-step weight, plus a critic
   head. PPO needs on-policy rollouts, a recurrent-state-aware trainer and roughly 10x the samples.
3. **It is off-policy and tolerates small data.** Each sitting's rollouts join the replay buffer with the human data,
   and every update uses all of it. At ~30k decisions per hour, on-policy PPO would discard most of its data each
   iteration.
4. **The KL to BC keeps the policy human-like and executable on the pad** (VPT and AlphaStar both anchored RL to the
   imitation policy to avoid collapse). Beta and the KL weight are the exploration dials: loosening them is how
   emergent behaviour is allowed, deliberately and measurably.

Reward (proposed defaults under the learning plan's reward contract; recorded with each run and tuned on dev
episodes): `+10` per KO, `+1` per hit capped at 20 per encounter so damage farming cannot outweigh KOs, `-0.01/s`,
terminal on a 20 s timeout, and `-10` plus termination on a fall death (the one range death, §1). Bot damage in the
range is too rare (two 25 hp hits in 3.1 h) to shape; damage-taken switches on in AI-only custom games (milestone F).
Unknown reads stay unknown, never zero reward. Step 0 uses the reader labels already made for all ten train
takes (`rl/labels/range_rewards_20260930.json`, 1,307 KOs, 5,795 hits, 10 falls), aligned to the step tables by
logger ns.

Acceptance, as the learning plan requires: KOs per encounter on untouched starts improve over the starting BC
checkpoint (and the scripted baseline's 4.2 KOs/min), not merely training return.

## 4. World-model track: practise in imagination

**Aim:** an action-conditioned world model of the practice range, trained on our paired frames and inputs, in which
the policy practises and emergent behaviour is searched cheaply; live sittings then only confirm candidates. This is
the novel, publishable piece: a playable neural model of a commercial hero shooter learned from a few hours of one
expert's play, with rewards read off pixels, used to discover behaviour that transfers back to the real game.

Precedents and what we borrow:
- **DIAMOND** (Alonso et al., NeurIPS 2024): a pixel-space diffusion world model; agents trained entirely in
  imagination on Atari 100k, and a playable CS:GO model from 87 h of human play. We borrow the EDM denoiser conditioned
  on past frames and actions, few denoising steps, and agent training on short imagined rollouts seeded from real
  frames.
- **GameNGen** (Valevski et al., 2024): Stable-Diffusion-based Doom at 20 FPS, where noise augmentation of the context
  frames stops autoregressive drift. We borrow the context-noise trick.
- **Genie / Genie 2** (Bruce et al., 2024): latent actions from unlabelled video. For us the IDM labels James's and
  expert VODs in our own action space instead, so unlabelled footage can extend the world model's data.

Plan, in order (each step ships a visible result):
1. **Prototype (now):** a small model with a short horizon, trained on Modal from James's paired range sessions; an MP4
   of real versus imagined rollouts from the same start frame and the same logged inputs, scored against
   copy-last-frame and an action-shuffled control (§5).
2. **Reward heads:** predict the §1 reader outputs (hit, KO) from imagined frames, so imagined rollouts carry reward;
   check them against real reader output on held-out sessions.
3. **Scale:** DIAMOND-style diffusion at 128x72 or higher, longer context, all train sessions plus IDM-labelled
   footage. Measure imagined-rollout fidelity by horizon and by the reward heads' agreement with the real readers.
4. **Imagination training:** actor-critic inside the world model from the BC initialisation with the KL anchor
   (DIAMOND / Dreamer recipe, horizon ~15 steps seeded from real frames), with an ensemble-disagreement penalty so the
   policy cannot farm model errors. Search for emergent behaviour there: novelty over action n-grams and combo orders,
   and population search over beta and the KL weight, keeping only candidates whose imagined gain is confirmed live.
5. **Loop:** every live sitting's rollouts retrain the world model where the policy went (Dyna / MBPO style).

## 5. World-model prototype result

**full-01 (2026-09-30, EXPLORATORY): the model beats copy-last-frame and the logged actions help, but it only holds
the scene for ~0.5 s.** By ~1 s an imagined rollout dissolves into a purple haze with the HUD intact.

- Model: DIAMOND-style EDM next-frame denoiser, 29.7M parameters, 72x128 at 10 Hz. It sees 4 context frames plus the
  step's action (15 held + 15 pressed semantic actions, camera yaw/pitch degrees), with context-noise augmentation.
  Code `rl/world_model/` (`dd62726`).
- Data: the frozen `caches15`/`steps15` train cohort already on Modal volume `rivals-range-bc`: six sessions (~93 min)
  for training, `20260925T025230` (3.7 min) held out for dev loss and every rollout. No sealed data.
- Run: 32k steps, 62 min on one H100, dev loss 0.113. Checkpoint on the Mac at `~/dev/rl-wm/runs/full-01/model.pt`
  and on volume `rivals-rl-wm-20260930`. Modal cost ~$5-6 (estimated from H100 minutes; another lane's app shared the
  billing window). Apps stopped; no containers of ours left.

512 rollouts of 1.6 s from the same held-out start frames with the same logged inputs (`rl/world_model/out/full-01_eval.json`):

| Rollout | PSNR dB +0.1 s | +0.4 s | +0.8 s | +1.6 s | mean MSE |
|---|---|---|---|---|---|
| copy last frame | 15.8 | 13.7 | 13.1 | 12.7 | 0.0464 |
| model, mean prediction | **20.1** | **16.8** | **15.9** | **15.1** | **0.0245** |
| model, shuffled actions | 16.9 | 15.0 | 14.8 | 14.6 | 0.0319 |
| model, zero actions | 17.8 | 15.0 | 14.4 | 14.2 | 0.0337 |
| model, 3-step sampled | 17.0 | 15.1 | 14.8 | 14.6 | 0.0315 |

Real actions beat shuffled ones by 3.2 dB at +0.1 s and 0.5 dB at +1.6 s, so the model uses them. Sampled frames are
sharper but score below the mean prediction, as expected. Visual: `rl/world_model/out/full-01_real_vs_imagined.mp4`
(6 clips; real | sampled | mean; 0.4 s of real context then 3 s imagined) and a 5.1 MB GIF of the first three.

Limits: a short-horizon predictor, not yet a simulator; at 72x128 the bots are a few pixels, so the §1 readers cannot
run on imagined frames (hence reward heads, §4 step 2); one held-out session and one seed; mouse degrees use one
calibration constant with acceleration on; actions are pooled over three 30 Hz steps.

Next, in order: longer context (4 frames is 0.4 s); a bigger model and more steps (loss still falling); the newer
admitted sessions; training on its own rollouts so errors do not compound; reward and termination heads on the §1
labels; then BC-policy rollouts in imagination with the KL anchor, checked against real footage.

## 6. Offline AWR step 0 on bc2 (2026-09-30, EXPLORATORY)

**Result: the pipeline works and the shift points the right way, but it is tiny.** Advantage weighting raises the
held-out likelihood of James's high-advantage steps relative to his low-advantage ones, on dev and on val, for both
betas; the controls do not. BC metrics do not collapse. Effect size is ~0.01-0.04 nats with a rank correlation of
~0.014 and no confidence interval yet, so this is a working step 0, not a better policy.

Setup (`rl/awr.py`, `rl/awr_modal.py`, commit `3cb83f3`; run `step0-01` on one H100, ~17 min):
- Base: policy's `bc2-dt-s1-hybrid` camera model, run `d-dt-bs8-s1` (sha256 `728dadbe…`, checked against the bundle).
  Same train/dev/val split as `policy/bc2/cloud.py`; nothing selected on val (212646).
- Rewards from the §1 labels: KO +10, hit +1, fall -10; 99.4% of events land on an eligible step. Returns use a 2 s
  half-life inside each run.
- Value head: an MLP on the frozen bc2 LSTM state, cross-fitted over 4 session folds. Out-of-fold R² 0.39 on train,
  0.46 on dev, 0.47 on val; advantage std 2.8. The smoke run showed why cross-fitting is needed: a head fitted on its
  own sessions reached R² 0.999 and left advantages as noise.
- Fine-tune: 6 epochs from bc2, lr 1e-4, weights `exp(A/beta)` clipped at 20 with mean 1, plus KL 1.0 to the frozen
  bc2 outputs.
- Arms: awr (beta = 1 std of A), awr-hot (0.5 std), uniform (weights 1, same KL: fine-tuning alone), shuffled (awr
  weights permuted within each session: same distribution, no signal).

| Arm | val: high-minus-low A, Δ log-lik | val Spearman(A, Δ) | dev: high-minus-low | val press macro F1 | val yaw MAE (median / mean decode) | val onset sign (mean decode) |
|---|---|---|---|---|---|---|
| bc2 (base) | 0 | – | 0 | 0.267 | 0.845 / 0.833 | 0.763 |
| awr | **+0.011** | +0.014 | **+0.030** | 0.279 | 0.846 / 0.829 | 0.764 |
| awr-hot | **+0.012** | +0.013 | **+0.043** | 0.273 | 0.841 / 0.827 | 0.753 |
| uniform | -0.005 | +0.003 | +0.006 | 0.275 | 0.838 / 0.818 | 0.772 |
| shuffled | +0.002 | +0.005 | +0.002 | 0.280 | 0.838 / 0.821 | 0.768 |

"High-minus-low A" is the change in log-likelihood (arm minus bc2) of James's actual held, press and camera targets,
averaged over the top advantage quintile minus the bottom one. The quintile means are not monotonic.

Action-level shift (val, mean predicted press probability versus bc2): awr raises jump (+4%), web swing (+3%) and
Spider-Power (+3%), and lowers Web-Cluster (-5%) and Amazing Combo (-4%). The controls also lower Web-Cluster and
Amazing Combo (uniform -5% and -3%; shuffled -13% on Amazing Combo), so only the mobility rise (jump, swing) is
specific to the advantage weighting.

Why the effect is small: one expert's advantages mostly measure the situation (a bot in reach), not a choice between
his own better and worse actions; the value head explains under half of the return. There is also no exploration
offline, so AWR can only re-weight what James already did.

Limits and next steps:
1. **Uncertainty:** block bootstrap over runs, and 3 seeds. Neither is done yet.
2. **The live hybrid bundle takes its buttons from the incumbent NitroGen head, not bc2.** A button shift here only
   reaches play if policy adopts the Policy2 buttons, or if AWR is applied to the buttons head. Policy has a stronger
   base coming (hidden 1024, val yaw ~0.81, press F1 0.29-0.31); rerun on it.
3. **The real test is online:** KOs/min against bc2 in the range, collecting on-policy data with the same readers
   (§2, §3). Offline AWR is the initialisation for that, not the product.

Cost: about $1.5 on Modal (smoke plus step0-01, ~20 H100-minutes). No containers left running.
