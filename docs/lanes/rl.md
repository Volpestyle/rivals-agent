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
| **Damage taken** | `RewardTracker`: rise in the deficit (max - hp), both numbers confirmed on two reads | 0 hp lost over 17.5 min of range play (bots never attack), where raw hp differencing found 500: Spider-Man's bonus health decays 300 to 250 with max and current falling together | Range sessions above; the match for real damage |
| **Death** | `RewardTracker`: hp read 0 twice | **3 detected, 3 real** (two agree with the in-match scoreboard at 211 s; the third is on the kill feed, "Zero-Two507 > cowboyboopbop") | The match |

James's rates (range, normal cooldowns): **7.7-8.7 KOs/min and 34-38 hits/min** (61 KOs in 7.0 min; 81 in 10.5 min),
about twice the scripted baseline's 4.2 KOs/min.

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
  matters in AI-only custom games (milestone F); range bots never deal damage.
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
- There is no in-range teleport or reset. Getting stranded off the platform means a lobby re-entry (spawn-room walk
  12-15 s M; one first entry took 15 min; the walk failed 2 of 3 trials; `docs/lanes/reentry.md`, `placement.md`).
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
terminal on a 20 s timeout. Range bots never attack, so damage-taken and death terms are off in the range and switch
on only in AI-only custom games (milestone F). Unknown reads stay unknown, never zero reward.

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

Running (Modal, `rl/world_model/`, commit `dd62726`). Results go here when the run finishes.
