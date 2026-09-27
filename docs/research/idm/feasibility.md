# VPT-style inverse dynamics at our scale: feasibility memo (2026-09-26)

A read-only research memo. No code was run, and no model was trained or evaluated. Nothing was written to Linear or
committed. No `data/` session media, Gate 2 or sealed file was opened. The sources were read on 2026-09-26: papers
(arXiv HTML and abstracts) and the repo's own lane notes and evidence.

The tags used below:
- **[V]** is checked in a primary source (a paper or official code).
- **[R]** is measured in this repo, cited to its lane note or evidence file.
- **[I]** is my inference or estimate.
- **[U]** is something I could not confirm.

## TL;DR

1. **Yes for camera degrees, and not for the rest yet.** On James's range data, ~45 min already gives a camera head at 0.26° median yaw error and 0.995 direction agreement (dev fold) [R]. What is unproven is the move from range to match and from live play to replay, not the amount of data. Gate 2 settles it, and its pairs are recorded.
2. **Key and ability labels are far below what the literature needs.** VPT needed at least 10 h before any downstream use and plateaued near 100 h [V]. Our edge head is at chance for WASD and for every HUD ability, and only jump shows weak signal [R]. The cause is partly the ±133 ms window, not only the ~3 h.
3. **Label abilities from the HUD event stream, not the IDM.** The HUD readers already produce these events, and on a replay the cooldown start is right there on the ability row. The IDM contributes camera degrees, and later coarse movement and hold state.
4. **Twitch VODs are a second, riskier stage.** Measure the loss first by re-encoding James's own labelled sessions Twitch-style. FOV and sensitivity are handled by predicting degrees. Player, device and overlay shift still need data we don't have: a second logged player and logged controller play.
5. **Latent actions (Genie, LAPA, LAPO) don't replace the IDM for us.** The pad executes semantic actions plus degrees, so latents would still need a mapping learned from the same paired data. With camera motion as a "distractor", latent-action learning degrades unless it is supervised [V]. At most they are an auxiliary for learning representations from VODs.

## 1. How much paired data did IDMs need?

| Work | Paired (labelled) data | What it labelled | IDM quality reported | Source |
|---|---|---|---|---|
| **VPT** (Baker et al. 2022), Minecraft | **1,962 h** of contractor play at 20 Hz, from one recorder with fixed settings (FOV 70°, fixed resolution) | ~70k h of web video | 90.6 % keypress accuracy and mouse R² 0.97 on held-out contractor data. The IDM is ~0.5 B parameters, sees **128 consecutive frames** at 128×128, and is non-causal. The camera uses 11 foveated bins per axis | [V] arXiv 2206.11795 (§4, Fig. 3, App.) |
| VPT data scaling | IDMs trained on 1 h to 1,962 h, judged by the downstream BC agent | the same | "IDMs trained on **at least 10 hours** of data are required for any crafting"; crafting "increases quickly up until **100 hours**", then plateaus. The authors say 100 h would likely have sufficed. The IDM is "two orders of magnitude more data efficient" than BC on the same data | [V] VPT Fig. 9, §4.6 |
| **D2E** (2025), 31 PC games | **259 h** in v1's abstract (the HTML says 335 h; the version or subset is unclear [U]), from 14 annotators at 20 Hz | 1,055 h of YouTube gameplay across 20 titles | Generalist IDM: mouse-X Pearson 0.74–0.84 and keyboard accuracy 61–86 % on seen games. Per-game specialists are lower (Pearson 0.43–0.66, keyboard 29–69 %). Keyboard accuracy is the weakest and falls to 27 % on hard games. **On an unseen FPS (Battlefield 6) the zero-shot mouse scale ratio is 3.13 / 3.56**, which becomes 1.07 / 1.05 with a few-shot in-context prefix | [V] arXiv 2510.05684 |
| **Pixels to Play** (2025), Roblox and DOS | Paid annotators, hours not stated | Public videos | No IDM accuracy published; "a residual gap between full-label and enhanced-label" training | [V] arXiv 2508.14295 |
| **NitroGen** (2026) | **No IDM.** Labels were read from on-screen **input-overlay** videos | 40k h across more than 1,000 games | The overlay extractor: joystick R² 0.84, button accuracy 0.96 | [V] via `docs/research/nitrogen/feasibility.md` F17 |
| **Pearce & Zhu 2021**, CS:GO | A rule-based IDM from server demo metadata (position, velocity, ammo), not pixels; 95 h online plus 0.8–3.3 h clean expert data | the 95 h | Firing from an ammo drop is easy. **WASD from velocity is "an ill-posed problem"**, and the time lags between action, metadata and screen are "inconsistent" | [V] arXiv 2104.04258 |
| **Genie** (2024) | None: an unsupervised latent-action model (8 codes) on 30k h of platformer video | n/a | In CoinRun, mapping latents to real actions needed only **200 expert samples** to match oracle BC | [V] arXiv 2402.15391 |
| **LAPA** (2024) | None to pretrain; 150 labelled trajectories per task to fine-tune | n/a | Beats OpenVLA overall but "underperforms ... on fine-grained motion" | [V] arXiv 2410.11758 |

**Where ~3 h of one player puts us, per action.** These are judgements from the table and our measurements.
- **Camera (yaw, and pitch less so): enough in-domain.**
  - With ~45 min of training, β-NLL, the dev fold gives 0.263° median moving yaw error, 0.995 direction agreement
    and 0.3 % abstention [R] (`inverse-dynamics.md`, the `beta-default` decision).
  - Yaw direction held at 0.94–0.98 on fresh sessions from a later build [R] (the pitch-fix confirmation).
  - Pitch is weaker and seed-fragile: 0.51–0.57° median error, and held-out agreement of 0.62–0.85 across seeds [R].
  - Camera is a geometric problem, and it matches D2E's pattern that mouse transfers better than keyboard [V].
  - Going from 45 min to 3 h should mostly buy coverage of strata (swings, fast flicks, combat), not accuracy on
    ordinary turns [I].
- **Jump: weak signal, well short of usable.** The best fold reaches F1 0.28 with AUC 0.73–0.85 across folds, from
  752–2,186 train presses [R] (`idm-thresholds.md`).
- **Movement (WASD): nothing.** AUC is 0.46–0.58, at chance on every fold [R].
  - The head predicts press onsets, which are the least observable form of a held key. No hold or locomotion head
    exists yet.
  - Pearce & Zhu found movement keys ill-posed even from exact velocity metadata [V].
- **HUD abilities (Get Over Here!, Amazing Combo, team-up) and the fire buttons: at chance.** The edge head never
  clears chance by 0.05 F1 on ≥ 2 of 3 seeds, and adding HUD crops at +67/+133 ms did not help across seeds and folds
  [R] (`idm-edge-input-2.md`).
  - The evidence arrives 0.1–1.9 s after the press, outside the ±8-interval window.
  - VPT's IDM saw 6.4 s of context (128 frames at 20 Hz); ours sees ±133 ms. **For presses, the window and the model
    (420 k parameters, global pooling) are probably a bigger gap than the hours** [I].
- **Ult and melee: unsupported.** There are 9 and 23 presses, under the 50 floor [R].
  - 3 h of range play will not change that, because range play rarely uses them.
  - Only logged real matches produce ults.

**Candidly:** by VPT's curve, ~3 h is below the ~10 h at which a Minecraft IDM became useful for anything that
depended on rarer keys. It is about 30× below VPT's plateau. That paper's action space is broader than ours
(one hero, ~12 semantic actions plus the camera), so the curve is an upper bound on our need, not a transfer [I].
Nothing in the literature suggests that 3 h of one player gives reliable key labels on other players' footage.

## 2. Which labels are recoverable from pixels, and which survive replays and VODs

**The image shows the outcome, and the label we want is the command.** They differ in five known ways, each
independent of the model:
1. **Automatic camera motion.**
   - Get Over Here! pulls and the combo launch rotate the camera with no mouse input, and so do death, respawn and
     spectating [R] (`inverse-dynamics.md`, failure modes).
   - The game will do that again when the agent casts, so labelling it as commanded input would double-rotate.
   - It must be excluded or kept as its own stratum, never relabelled as input.
2. **Aim assist** (controller players only; James's pad runs with it at 0).
   - The rotation you see includes the assist's pull.
   - For our executor that is arguably the right target: the pad must produce that rotation by stick alone.
   - It is still not the stick input, and it is target-dependent [I].
3. **Presses with no visible effect.**
   - Examples: an ability on cooldown, a swing with no anchor, team-up with no teammate (seen on the range), keys held
     during animation locks, WASD in the air.
   - These are irreducible for any IDM. They are also mostly irrelevant for imitation, since a rejected press changes
     nothing [I].
   - Mark them unknown, never "no".
4. **Momentum and air control.** Held WASD has a small, delayed effect while swinging or falling [R].
5. **Server versus client.**
   - The replay shows replicated server state; the live view shows client prediction.
   - Onsets can shift by a tick or two. M1 found no replication kinks or pitch lattice on the replay, but its test is
     weak [R]. Gate 2 measures the shift.

| Label | What pixels show (live, 1440p120) | Native replay (1440p120, PLAYER POV, full HUD) | Twitch VOD (typically ≤ 1080p60, a few Mbps [I]) | Current IDM evidence [R] |
|---|---|---|---|---|
| **Camera yaw** | The achieved rotation: the whole image translates. Unambiguous apart from ability camera and parallax | Likely survives: 96 % fresh frames and no replication signature found (M1). Gate 2 decides | Probably survives in degraded form. H.264 smears the fine texture that frame differences use; 60 fps doubles the per-frame angle of fast flicks; overlays add static content (the M1 failure mode). Degrees need the FOV and aspect ratio (§3) | 0.26° median, 0.995 direction (dev) |
| **Camera pitch** | As yaw, with smaller motion. The gain is derived as equal to yaw's | As yaw | As yaw, and weaker | 0.51–0.57° median; seed-fragile |
| **WASD, held** | Partly: character translation relative to the camera on the ground, and the run animation. Near nothing while airborne or swinging | As live | Worse: small, blurred cues | Onsets at chance; no hold head |
| **Jump** | Yes on the ground (a vertical jump); ambiguous next to wall-crawl and swings | As live | Probably yes on the ground | F1 ≤ 0.28 |
| **Swing hold (Shift)** | Yes: the web line, anchor and arc. Onset and release are visible within ~1–3 frames [I] | As live. Swing mode (simple or aimed) is not visible [R] | The web line is thin, and compression may erase it at distance [I] | Onset ΔF1 ≤ 0.08; no hold head |
| **Get Over Here!, Amazing Combo, team-up** | The HUD cooldown starts **0.1–1.9 s** after the press; the in-world cast is visible earlier | **The HUD survives**, and the HUD-event stream reads it. The replay-side cooldown anchor reader failed its timing and recall bars (`idm-gate2-anchors-results.md`), so exact-frame timing from the replay HUD is unproven | The HUD is legible only where no webcam or alert covers the ability row. A controller player's HUD has a different layout | At chance (all three) |
| **Web Cluster (RMB)** | Ammo counter decrement plus the projectile | The ammo HUD survives | Ammo digits at 1080p are unverified | ΔF1 ≤ 0.02 |
| **Spider-Power (LMB)** | The melee-string animation | As live | Probably visible | Near chance |
| **Ult (Q)** | The cinematic and the ult meter reset: a HUD event | As live | Visible | Unsupported (9 presses) |

**What follows:**
- **Camera is the only IDM head that is recoverable and has evidence.**
- **The abilities are recoverable, through the HUD rather than the IDM.** The event already reaches the HUD readers;
  what is missing is exact press timing.
- **Movement and holds are recoverable in principle but untested.** The heads that would measure them don't exist.

## 3. Transfer risks and what fixes each

| Risk | What goes wrong | Calibration or conditioning that addresses it | Status |
|---|---|---|---|
| **Sensitivity and DPI** | Mouse counts per degree differ by player. An IDM that outputs counts is wrong by an unknown scale: D2E's zero-shot scale ratio was 3.1–3.6 on an unseen FPS [V] | **Predict achieved camera degrees**, not counts. This is already done: the labels are counts × the 360° gain, 10,880–10,892 counts/360° and speed-independent from 1.8k to 12.1k counts/s [R] | Done |
| **FOV and aspect ratio** | Degrees per pixel depend on horizontal FOV and aspect. Stretched or 4:3 resolutions change it | Per-source FOV. Third-party sites say Rivals has a **fixed FOV and no slider** [U, secondary sources only]. If that holds, degrees follow from the aspect ratio and the per-hero camera alone, and a VOD needs only an aspect check (the HUD's geometry gives it). The two-FOV replay re-record was never made (`recording-log.md`), so whether the replay renders at the viewer's settings is still open | Open (M2) |
| **Bindings** | The expert's pull is R, James's is E [R] | Semantic outputs already absorb this | Done |
| **Swing mode** (simple or aimed, hold or toggle) | The same visual swing comes from different inputs | `control_context` per source; swing labels only where modes match [R]. VODs have unknown mode, so give swing labels only as "a swing happened", never as a hold duration | Designed |
| **Mouse to controller** | A controller turns by rate, with a ramp, a turn-rate cap and aim assist; its movement is analog; its HUD has a different ability-row layout | Degrees are device-agnostic, so the camera label stays valid. Label movement as a direction, not keys. The HUD readers need the pad layout (VUH-1346 P2′). **Controller footage is closer to our pad's reachable envelope** than a mouse flick | Only the 15-min DualSense range take exists [R]; whether its pad inputs were logged is [U] |
| **One player to many** | James's movement habits, turn speeds and skill set the support. The support gate (James's p99.5 rate) withholds exactly the expert flicks imitation most wants [R] | **No gate measures this today.** Gate 2 is replay-of-self, the same player. The fixes are a second logged player (D2E used 14 annotators [V]), and James deliberately covering fast flicks to widen the support | Gap |
| **Range to match** | Maps, lighting, human enemies, team fights, ults, deaths, spectator colours [R] | Logged real matches as training and as evaluation. Nine logged live matches exist (2026-09-25), each sealed for Gate 2 or evaluation-only [R] | Partly available |
| **Replay camera versus live** | Reconstructed camera, server timing, x-ray outlines, fixed team colours, follow cuts [R] | The shared `REPLAY_UI_MASK`, colour jitter, the follow and cut detector (`replay_cuts.py` passed S1–S3 [R]), then Gate 2 replay-of-self on two matches | Pairs recorded, not scored |
| **HUD layout and overlays** | Streamer webcams, alerts and Twitch UI cover pixels. The motion estimator locked onto static UI once (M1: 99–100 % zero flow) [R] | A per-window static-overlay mask (`window_overlay`), the border and centre rules; HUD readers fail closed on an unrecognised layout [R]. VODs need a per-channel overlay mask, as `policy/frames.py` has for DayMR | Tooling exists for the replay |
| **Compression and frame rate** | Blocking, smeared fine texture, duplicated frames, 60 fps instead of 120 | Train with the same degradation: re-encode James's sessions to VOD-like settings and add those as augmentation and as an evaluation set. The repeated-frame rule already exists [R] | Not done; cheap |
| **Patch drift** | Kit and HUD change | Build pinning (VUH-1324) [R] | Done |

## 4. Latent actions instead of exact inputs?

**The approach** (Genie, LAPO, LAPA) learns a small code for "what changed between frames" from unlabelled video,
trains a policy on the codes, and then maps codes to real actions with a little labelled data [V].

**Why it is a poor fit as our primary path** [I, except where marked]:
- **The pad needs semantic actions plus degrees.** Latents still need a decoder into that space, trained on the same
  kind of paired data the IDM uses. So latents don't remove the paired-data need; they only move it.
- **Camera motion dominates every frame of third-person footage.** LAPA reports that latent actions "capture camera
  viewpoint changes" [V]. Nikulin et al. 2025 show latent-action learning "struggle[s]" with distractors such as camera
  shake and background video. Supervising with as little as **2.5 %** ground-truth labels improves downstream
  performance **4.2×** [V].
  - In our footage the camera is the action, and ability effects, other players and UI are distractors.
  - An unsupervised model would spend its few codes on camera motion, which we can already measure geometrically.
- **The published wins are at small action spaces** (8 codes in platformers) **or in manipulation**, and LAPA says
  latents underperform on fine-grained motion [V]. Our hard labels are timed presses of specific abilities, which is
  the fine-grained case.

**Where latents could fit:**
- As a **supervised latent** (LAOM-style [V]): an extra head on the IDM, trained with James's labels, that soaks up
  the unlabelled "residual intent" of VOD frames, such as movement style. It would be used for representation
  pretraining of the policy encoder, not as executable labels.
- For the plan's **VOD tactical policy**, which outputs options (intent, target, destination) at 5–10 Hz
  (`docs/plan.md`). Coarse, abstract action codes suit it better than exact keys.
- This is research, and it comes after camera and HUD labels are working.

## 5. Recommendations for our IDM, ranked

### Measure first (existing code and data; no new recording)

1. **The range-to-match gap, with true inputs, before any replay.**
   - Run the frozen camera checkpoint on James's **logged live matches** that are not sealed: `20-06-20` and `20-37-11`
     (reader development), and the reader-validation matches. These have logger inputs, and the IDM never used them.
   - It needs an evaluation-only target build for those sessions. That is an intake decision for the lead.
   - This splits the Gate 2 question into range→match and live→replay, and it opens no sealed pair.
   - Report the camera error by stratum (team fight, ability camera, death, swing), and the support-gate withheld share.
2. **A Twitch degradation test on James's own held-out session.**
   - Re-encode the dev session to Twitch-like settings: 1080p60, H.264 at about 6 Mbps [I], with and without a
     synthetic webcam box over a corner.
   - Score the camera head and the HUD readers against the same true labels.
   - This prices the VOD route for the cost of a few encodes, before anyone collects a VOD.
3. **Per-row camera error by speed band and stratum** on the dev fold, including the fraction of intervals beyond
   the pad envelope (5.3 % [R]).
   - This shows whether the gaps that remain sit in the flicks and swings that matter most.
   - Also check the `extrapolated` σ = 20 % in `idm_targets`. The later multi-speed calibration found the gain
     speed-independent to 12.1k counts/s, so that σ may now be over-conservative [R/I]. The call is the lead's.
4. **A replay dry run on DayMR's 15 alive minutes, no labels exported** (the lane's own plan step).
   - Report the support-gate withheld share per stratum.
   - Measure the agreement of camera rotation with the geometric estimator.
5. **Refit the IDM on the whole ~180-min train campaign** (today's checkpoints use ~45 min), with β-NLL and pitch fix
   A, 3 seeds.
   - This is the checkpoint Gate 2 would freeze.
   - It also gives the first read on whether edge and jump signal grows with 4× data. It is only an indication,
     because the window problem remains.

### Build next (design choices, each pre-registered by the lane)

6. **Hold and locomotion heads** that predict held state (and movement direction relative to the camera), not onsets.
   - Feed them a crop around the character and the flow left after the rotation is removed; the geometric estimator
     supplies the rotation.
   - Onsets are the least observable form of a held key. For the policy, a held state at 30 Hz is what the executor
     consumes.
7. **Ability press timing: the HUD event minus a measured lag, not the edge head.**
   - The replay HUD shows the cooldown start. The press is earlier by a per-action lag distribution measured on
     James's data: team-up about 15 ms median; Get Over Here! 0.47–0.96 s [R].
   - For short-lag actions this gives a label good to about a step.
   - For Get Over Here!, either accept a coarse (±0.25 s) label or add an in-world cast detector (the web projectile)
     with a window of at least 2 s after the press. That needs new stores, since the current ones hold ±16 video
     frames [R].
8. **If the edge head is kept,** give it VPT-like context: a few seconds at a low rate plus the native-rate motion
   near the interval, and at least 3 seeds per arm (the edge results showed seed spread larger than the effects [R]).

### Data to ask James for, in order of value per hour

| # | What | Hours | Why |
|---|---|---|---|
| D1 | **Logged real matches as Spider-Man** (Quick Match, his own play; matchmade modes are out of scope for the agent, not for James), across as many maps as possible, some registered as train | 5–10 h over time; the first 2–3 h matter most [I] | Closes the range-to-match gap, which more range time cannot close [R]. It is also the only source of ults, deaths, team fights and enemy-driven camera |
| D2 | **Replay-of-self for a few of those matches,** each with the two-FOV re-record of 10–20 s | ~20 min per match | More Gate 2 units beyond the two sealed pairs, and settles M2 (FOV) |
| D3 | **Coverage sessions:** deliberate fast flicks at all speeds, isolated strafes on the ground, jumps, swings of varied hold length, wall-crawl | 1 h | Widens the support gate's p99.5 for expert flicks, and gives the future hold and locomotion heads clean positives |
| D4 | **A second person, logged,** on the same client and settings | 1–2 h | The only way to measure one-player-to-many with truth. No gate covers it today |
| D5 | **Logged controller play** (the DualSense), if controller VODs are a target, with the pad state captured | 1 h | Measures the mouse-to-controller transfer of the camera head, and covers the pad HUD layout |

### Labels to trust, in order

1. **Camera yaw in degrees,** inside the support gate, after Gate 2 passes. Pitch next, with fix A's marker and the
   fast-band caveat.
2. **HUD-evidenced ability events** (cooldown start, ult, ammo decrement), from the HUD readers, with measured
   press-lag offsets. Their timing on the replay HUD needs its own check, because the cooldown-anchor reader failed
   there.
3. **Swing and jump as "happened in this window",** once a hold head shows signal. No hold duration on
   unknown-mode footage.
4. **Movement:** last, as coarse direction only, and only if a hold head beats last-value on logged matches.
5. **Melee and ult presses:** from HUD or animation events only. The IDM has no support for them.

### The Gate 2 path

- **The pairs exist** (sealed): Central Park `19-21-09` with its replay `23-49-58`, and Hall of Djalia inside
  `19-28-51` with its replay `10-57-37` [R].
- **Alignment rests on the match timer alone.**
  - It passed T1; T3 failed because of the game display's own jitter; the median-offset rule replaces it.
  - The kill feed was rejected, and replay-side cooldown anchors are out for good [R].
  - `replay_cuts.py` passed S1–S3 and awaits review [R].
- **Order:**
  - (a) the review of `replay_cuts.py` and the timer as a value reader;
  - (b) freeze the checkpoint from recommendation 5, with support thresholds from train and dev;
  - (c) open Gate 2 once, and score the camera per axis on each match separately.
- **Expect edges to be "undecided"** on 7–11-minute matches, under the ≥ 30 onsets per action per match rule [I].
  So Gate 2 will in practice decide the camera only. Ability labels then come through the HUD route (item 7), whose
  replay timing needs its own check.
- **Passing Gate 2 licenses DayMR-style replays only.** Twitch VODs need their own gate:
  - recommendation 2 first;
  - then a small set of hand-audited VOD windows, as `docs/learning-plan.md` asks ("audit a small expert-video
    transfer set before producing training labels").

## Open questions

1. Does Rivals have a player FOV setting at all, and does the replay render at the viewer's FOV? The two-FOV
   re-record answers both. The web claim of a fixed FOV is secondary-source only.
2. Did the DualSense take log pad state, or only keyboard and mouse?
3. Can Rivals replays of other players' matches be obtained at scale, or only a few by hand? This decides whether
   "in-client replays" is minutes or hours of expert footage [U].
4. Do Spider-Man guide videos with **keyboard or input overlays** exist in useful numbers? NitroGen's route [V] gives
   true key labels without an IDM, though not mouse degrees [I].
5. Is audio kept in our recordings and in the replays? Ability sound effects could time casts to a few ms
   independently of the HUD lag [I].

## Sources

**Papers:**
- VPT: Baker et al. 2022, <https://arxiv.org/abs/2206.11795> (HTML and ar5iv read: §4, Fig. 3, Fig. 9, the IDM and
  recorder appendices).
- D2E: <https://arxiv.org/abs/2510.05684> (HTML: the Generalist-IDM tables, the few-shot scale ratio, pseudo-labelling).
- Pixels to Play: <https://arxiv.org/abs/2508.14295>.
- NitroGen: <https://arxiv.org/abs/2601.02427>, via `docs/research/nitrogen/feasibility.md`.
- Pearce & Zhu, *Counter-Strike Deathmatch with Large-Scale Behavioural Cloning*: <https://arxiv.org/abs/2104.04258>
  (ar5iv).
- Genie: <https://arxiv.org/abs/2402.15391>.
- LAPA: <https://arxiv.org/abs/2410.11758>.
- LAPO, *Learning to Act without Actions*: <https://arxiv.org/abs/2312.10812>.
- Nikulin et al. 2025, *Latent Action Learning Requires Supervision in the Presence of Distractors*:
  <https://arxiv.org/abs/2502.00379>.

**FOV, secondary sources only:** <https://deltiasgaming.com/can-you-change-the-fov-in-marvel-rivals/> and
<https://marvelrivalshub.gg/how-to-change-fov-in-marvel-rivals/>.

**In repo:**
- `docs/lanes/inverse-dynamics.md` (design, Gate 1 numbers, β-NLL, pitch fix A, the edge tests, the Gate 2 protocol and
  readers);
- `docs/lanes/idm-gate2-anchors.md` and `-results.md`;
- `docs/evidence/idm-plumbing-20260924/{idm-diag,idm-thresholds}.md`;
- `docs/evidence/idm-beta-nll-20260925/idm-edge-input-2.md`;
- `docs/learning-plan.md` ("Camera motion and inverse dynamics");
- `docs/plan.md` (scope boundary, direction);
- `docs/recording-log.md`;
- `policy/idm/model.py`.
