# Assumption audit: end-to-end behaviour cloning (VUH-1346)

**2026-09-26. Research, read-only.** Asked by James: "make sure we aren't just operating on assumptions we made
before when we had less training data." This register lists the constants, defaults, baselines and dispositions the
range-BC work still runs on, and says which rested on less data (or none) than exists now.

**Scope and method.** I read `policy/range_bc/*.py`, `agent/controller.py` (`Cal`), `docs/lanes/end-to-end-fit.md`,
`end-to-end-fit-interim.md`, `end-to-end-fit-patch-equivalence.md`, `human-admission.md`, `docs/recording-log.md`,
`docs/pad-bindings.md`, `docs/spiderman-kit.md`, `data/calibration/alt-20260926/SITTING.md`, the steering charter, and
the evidence folders `range-bc-plumbing-20260924`, `range-bc-interim-20260925`, `range-bc-selffed-diag-20260925` and
`range-bc-countermeasures{,-2,-3}-20260926` (round 3 through Amendment 3, landed `595753d`). I opened no
`data/human` session file, no sealed, test or validation media or label, and ran no code, training or Linear call.

**Evidence tags.** **V**: I verified the fact in the named file. **I**: my inference, not measured. The verdicts are
judgment calls on V facts; any number marked I needs the re-check before anyone relies on it.

**The data then and now (V).**

| Era | Date | Train | Dev | Basis for |
|---|---|---|---|---|
| Design (F1-F8, K1-K10) | 2026-09-23 | ≤ 17 trainable min; no val | none | vocab, classes, model, loss, gates G0-G6, decode |
| Smoke | 2026-09-23 | 051828 (6.97 min) | 171533 | throughput, determinism |
| Plumbing | 2026-09-24 | 051828 + 200129, 33.59 min | 171533 + 205528, 13.64 min | epochs 13, wd 1e-4, stride 64, lag 0; 0.418 / 0.376 baselines |
| Interim | 2026-09-25 | five sessions, 80.53 min | same dev | the recipe "unchanged for the larger corpus"; zero-motion 1.2246°, any-hold 0.699 |
| Rounds 1-3 | 2026-09-26 | the same 80.53 min | same dev | S1-S4, K; idle disposition |
| **Now** | 2026-09-26 | **180.57 admitted** (10 sessions) = 166.93 min trainable with the frozen dev held out (2.07× the interim) | same dev | nothing yet |
| Validation | admitted 2026-09-25 | 15.58 min (212646), unread | | nothing yet |

The 180.57 includes the two dev sessions (94.18 = 80.53 + 13.64; `human-admission.md:1509`). The three sessions admitted
after the interim are 203745 (45.98 min, new build), 045729 (10.26, alt account) and **035932 (30.15, main account,
mouse acceleration off)**. Dev is two 2026-09-23 old-build sessions. One of them, 171533, is a 2.6-minute take of
"full-ammo combos with waited cooldowns, pulls at the end" (`recording-log.md:20`), not ordinary play.

## TL;DR: the five riskiest assumptions for the current failure

The failure is that self-fed rollouts sit near idle (almost no presses or hold onsets) and the self-fed camera equals
zero motion (1.2246°). Ranked by how much each could be causing that:

1. **The output side was fixed before any data and has never been re-derived.** The decoder starts a hold only when
   an *unweighted* hold BCE crosses 0.5 at the exact step. `pos_weight` (capped at 20) applies to press and release,
   which cannot start a hold (`executor.py:39-54`, `train.py:244`). The camera is the *median* of 31 classes
   (`vocab.py:86`).
   - A median returns zero whenever the model is unsure of the turn's *sign*, even when it is sure the camera moves (I).
   - Self-fed, P(yaw = zero class) is 0.82-0.89 and the median is never non-zero (V, `fit-selffed-diag.md:47-52`).
   - Round 1's history-free arm B held almost nothing: any-hold 0.19 against the human 0.70 (V).
   - Round 3 removes the history but keeps this decode and this loss. So H can fail on holds and camera for this reason
     alone (I).
   - **RE-CHECK:** re-decode existing checkpoints, inference only (item C3 below).
2. **"Idle-target imbalance is not a factor (0.51 %)" measured a different quantity from the one that collapses.**
   The 0.51 % is *physical* idle: no key held, no raw mouse delta, in runs of at least 30 steps. It is counted after
   admission had already cut the step-away and AFK spans.
   - The collapse is *semantic*: no live hold and a zero camera class, with onsets rare against continuations.
   - That onset-to-continuation imbalance on the unweighted hold heads was never counted.
   - The design itself calls the 0.51 % "a scope/budget disposition, not a measured causal finding" (V).
   - **RE-CHECK:** a stdlib count on train (C2).
3. **The recipe comes from 33.59 minutes and from a from-scratch model *with* history.** That is 13 epochs, lr 3e-4
   with a 500-step warm-up, batch 8, stride 64, a 96-step window and the IMPALA/LSTM-512 size (plumbing p1 and p5,
   2026-09-24).
   - The interim carried the recipe to 80.5 min "unchanged". Its argmin epochs were [13, 13, 12] of 13: the fit sat at
     the cap, not past an optimum (V).
   - Round 1's history-free B underfit on it: seed 0 never trained, and seeds 1-2 were still falling at epoch 13 (V).
   - Round 3's H, I and W are history-free or weak-history arms, and they keep 13 epochs. Its 32-update smoke measures
     timing, not convergence (V).
   - **RE-CHECK:** a longer explore run (C6).
4. **The interim cohort and the frozen dev set every baseline and bar.** S3's 1.2246°, S4's 0.699, the 0.418 / 0.376°
   camera references and the "10 live actions" all come from 13.64 min of old-build dev: two sessions, one of them a
   drill. Dev has been read roughly eight times (V).
   - Rounds 1-3 train on 80.53 of the 166.93 trainable minutes, by a budget decision (V).
   - Data did help teacher-forced: TF camera went 0.967° → 0.588° from 33.6 to 80.5 min, and the F1 gap opened (V).
   - Whether the self-fed collapse persists at 2× the data is untested.
   - Whether dev's human figures are typical of the pool (the main account, the new build) is unmeasured.
   - **RE-CHECK:** C4 and C7.
5. **The camera classes and class-coded history were fixed before the calibration take.** The REPS grid and the
   one-hot camera class in the previous-action input set a quantisation floor. That floor was never measured.
   - The baselines use exact degrees: persistence 0.418° and ar2 0.376°, against G3's bar of 0.8 × 0.376 = 0.30°.
   - My rough estimate is a floor near 0.1-0.25° on yaw (I), which would take a large share of G3's margin.
   - This may explain part of "TF camera worse than persistence" (0.58-0.60° against 0.418°).
   - **RE-CHECK:** a stdlib pass on train (C1).

The rest of the list is mostly settled. The **mouse gain** is now measured well: at speeds up to 12.1k counts/s, in
both directions and on both accounts. The code's "linearity unverified" caveat is out of date (it errs toward caution
and does no harm). The **pad maps** (415 / 99 °/s, focal 465) are **stale** for the alt's 247/124 profile, but they
matter only to the live pilot. Offline they only set the self-fed saturation caps.

## Full register

Columns: where it lives; the date and the data it rested on; M = measured or J = judgment; what has changed since;
the verdict. Line numbers are at `595753d` (range_bc files are unchanged since `5c3f74e`).

### A. Cohorts, splits and baselines

| # | Assumption | Where | Date · data | M/J | Changed since | Verdict |
|---|---|---|---|---|---|---|
| A1 | Rounds 1-3 train on the 80.53-min interim cohort, not the admitted pool | `round3-design-a2.md` §"Data decision" (:36-42); prereg-a2 §2 | 2026-09-25/26 · 80.53 min, 5 sessions | J (budget: "sacrifices a data-scale conclusion") | 166.93 trainable min now (V); adds a main-account session and 203745 | **RE-CHECK** (C4). Sound for comparability *within* round 3, but no experiment tests the collapse at 2× the data |
| A2 | Dev = 171533 + 205528, frozen "through the real fit" | `end-to-end-fit.md:832-840` | 2026-09-23 · rule chosen before content was seen | J | Both are old build and 2026-09-23; 171533 is a 2.6-min drill take; no main-account or new-build dev; read ≈ 8 times (plumbing, interim ×3, diag, R1, R2, R3) | **RE-CHECK** (C7). The charter already tags dev "heavily reused". Representativeness is unmeasured (I) |
| A3 | Persistence 0.418° and ar2 0.376° TF camera references | `end-to-end-fit.md:994-1004`; `fit-interim.md:78-84` | 2026-09-24 · dev; ar2 refit on the 80.5 train gives 0.37623 | M | Dev unchanged, so the numbers are still exact *on this dev* (V) | **STILL VALID on this dev.** Must be recomputed for any new eval set (round 3 design :42 says so) |
| A4 | Zero-motion camera 1.2246° (S3 = 0.95×) and human any-hold 0.699 (S4 band) | prereg-a2 :184; `fit-countermeasures-prereg.md` | 2026-09-25 · dev, 24,556 rows | M | Dev unchanged | **STILL VALID on this dev.** Dev-specific (C7 checks typicality) |
| A5 | S1 ≥ 0.05, S2 [0.5, 2] and 6/10, S3 0.95×, S4 [0.5, 1.3]×, K (seed-range slack) | `fit-countermeasures-prereg.md` "Pass rules" | 2026-09-25 · from the diag's probes and dev human figures | J, anchored on M | None | **STILL VALID as a detector of collapse.** S3 is self-described as weak (still far worse than ar2) and K as deliberately weak. Neither bar can say "good"; that is correct for a collapse test |
| A6 | Validation from dedicated takes "at the start of two later sittings" (F6) | `end-to-end-fit.md:43, 287` | 2026-09-23 · none | J | 212646 was recorded *after* the 48-min train take 203745, in the same sitting (`human-admission.md:1382`) | **STALE** as stated. The one val take is not sitting-independent of train; the real-fit pre-registration must state this or record another take |
| A7 | One kit version across the fit (patch equivalence) | `end-to-end-fit-patch-equivalence.md`; `steps.py:116` | 2026-09-24 · patch notes | M (notes) | Builds 25364676 and 25501035 are both "Season 10 / 20260911" | **STILL VALID.** Re-check at each Steam update (minutes, reading patch notes) |
| A8 | The main-account session (acceleration off) is motor-equivalent to the alt | `human-admission.md:1419, 1493-1518` | 2026-09-26 · turn take 060921: mean +0.064 %; slow turn +0.159 % failed the scripted ±0.08 % | M, with a J tolerance (±0.25 %) | Its header identity `a8dea3ba` is an equivalent profile, not the literal settings | **STILL VALID** for the gain. Not in the interim cohort, so no fit has seen it yet |

### B. Action space, camera and calibration

| # | Assumption | Where | Date · data | M/J | Changed since | Verdict |
|---|---|---|---|---|---|---|
| B1 | Yaw 0.0330738 °/count (= 0.0175 × 1.89) | `steps.py` header doc; calibration v2 | 2026-09-23 · slow 360° turn | M | Multi-speed 030045: speed-independent from 1.8k to 12.1k counts/s (`human-admission.md:1236`); left turns match to +0.011 %; main account +0.064 % | **STILL VALID**, now well measured. Above ~12.1k counts/s (≈ 13°/step) it is unmeasured. Human p99 is 431-641 counts/step (13-19k counts/s), so roughly 1-2 % of moving steps sit above it (I) |
| B2 | `DEGREE_CAVEAT`: linearity "unverified above slow speed"; `speed_curve` refused | `vocab.py:47-56`; `executor.py:81-84` | 2026-09-23 · slow turn only | J | Superseded by 030045 and the left-turn take | **STALE** text (the measurement now exists). Harmless; cleanup only |
| B3 | Pitch gain = yaw, `derived_equal_sensitivity` | `vocab.py:51-52`; `human-admission.md:1035` | 2026-09-23 · sweep failed; equal sensitivities | J | Alt pitch sweeps recorded 2026-09-26 (11-26-48); one pitch control failed; not used as a measurement | **RE-CHECK**, low priority. A wrong pitch gain rescales pitch labels and targets alike, so it barely moves the ratios to the baselines (I). Owner: admission-owner, if the 11-26-48 sweeps are usable |
| B4 | 31 camera classes, REPS 0.05-40°, dead zone 0.025°, clamp 40° | `vocab.py:58-66`; `end-to-end-fit.md:152-156` | 2026-09-23 · "pre-registered before the calibration take"; review's 17-min count percentiles | J | Real gain 0.0331 (2.5× the synthetic 0.0132 used then); 180 min exist | **RE-CHECK** (C1). The quantisation floor against exact-degree baselines is unmeasured. The clamp covers the human maximum except about 46° (1,384 counts) |
| B5 | Camera decode = median class ("MAE-optimal") | `vocab.py:86-94`; `train.py:330, 624` | 2026-09-23 · none | J | Self-fed P(zero) 0.82-0.89; humans start moving from still in 22 % of steps, the model in 2 % (`fit-selffed-diag.md:33, 47`) | **RE-CHECK** (C3). MAE-optimal for one step, but under sign uncertainty it outputs zero, so it can never start a turn (I). The charter's "camera as a coherent multimodal output" explore bet targets this |
| B6 | Previous camera fed to the model as a one-hot *class*, not degrees | `steps.py:678-697` | 2026-09-23 · none | J | Baselines persistence and ar2 use exact degrees | **RE-CHECK** (with C1). The model cannot reproduce persistence exactly; part of its 0.58° against 0.418° may be encoding, not skill (I) |
| B7 | `SIGN_MIN_DEG` 0.3°, `ONSET_PREV_DEG` 0.075° "≈ the review's 20 and 5 counts" | `metrics.py:22-26`; `end-to-end-fit.md:336` | 2026-09-23 · synthetic 0.0132 °/count | J | At the real 0.0331 °/count they are 9 and 2.3 counts, not 20 and 5 | **RE-CHECK**, low priority. They affect G3's onset-sign part only. Stated in degrees, so still defined; the counts rationale is off by 2.5× |
| B8 | 15 actions, `LIVE_MIN_PRESSES` 50, `PREREGISTERED_UNSENDABLE` = {ultimate, melee, team_up, goh_targeting} | `vocab.py:19-45` | 2026-09-23/24 · 33.59-min counts (simple_swing 3 counted presses) | J (+M counts) | Pad now follows the alt's custom binds (`514a8f7`); the pad has Simple Swing unbound; the pool is 2× | **STILL VALID.** Recount the live list on the new cohort when it changes (it is computed, not assumed) |
| B9 | `swing_mode` header = {automatic_swing false, hold_to_swing true}, equal to the pad's | `vocab.py:97-107`; `human-admission.md:966-970` | 2026-09-23 · saved profile; "automatic swing ↔ `UseSimpleSwing` is my reading" | J (a mapping) | The alt controller tab changed (Hold to Wall Crawl ON); the keyboard tab is unrecorded (`recording-log.md:65`) | **RE-CHECK** (C9: one keyboard-tab screenshot). It gates `web_swing` live; not part of the offline collapse |
| B10 | 30 Hz step (`STEP_S`, `step_ns` 33,333,333) | `executor.py:21`; `steps.py` doc | 2026-09-23 · none (matches IDM) | J | The live loop has run at ~51 Hz; a 30 Hz cadence is still unmeasured live | **STILL VALID as the contract.** It sets the onset-to-continuation ratio; the charter's action-chunk bet (H=4/8) is the test |
| B11 | Lag 0 until frame-to-send latency is measured | `end-to-end-fit.md:864, 935` | 2026-09-24 · p4: lag 1/2 had *lower* dev loss (1.4232 / 1.4077 against 1.4310) but lower F1 | M (loss), J (decision) | Latency still unmeasured; only 71 ms acquisition-to-consumption exists | **STILL VALID** offline. RE-CHECK when the live harness measures latency (pad-binds) |

### C. Model, loss and training recipe

| # | Assumption | Where | Date · data | M/J | Changed since | Verdict |
|---|---|---|---|---|---|---|
| C1r | Model size: IMPALA (16, 32, 32), embed 256, LSTM 512, global 256×144, crop 128² | `model.py:21-33` | 2026-09-23 · none; the throughput bench | J | 2× data; round 3 swaps the encoders, not the LSTM | **STILL VALID** for comparability. Never scaled; a size sweep belongs in the explore track |
| C2r | Epochs 13, wd 1e-4 (p1 argmin), stride 64 (because E* > 10) | `range-bc-plumbing-20260924/preregistration.json`; `end-to-end-fit.md:971-975` | 2026-09-24 · 33.59 min, the no-HUD arm *with* history | M on the plumbing dev | Interim argmin [13, 13, 12] of 13 (at the cap); round 1 B underfit and still falling; round 3 H/I/W are history-free, frozen-feature and augmentation-free | **RE-CHECK** (C6). The stride-64 fallback was a *compute* rule for 2.5 h of data, applied to a curve from 33.59 min |
| C3r | lr 3e-4, 500-step warm-up, clip 1.0, batch 8 | `train.py:283-287, 1069-1070`; `end-to-end-fit.md:191-193` | 2026-09-23 · batch 8 from MPS memory (32 needed 97 GB) | J (+M memory) | CUDA (Modal) is now allowed for round 3, so batch 8 is no longer forced there | **STILL VALID** for round-3 comparability. RE-CHECK for any real fit; batch 8 was a memory constraint, not a choice |
| C4r | Window 96, burn-in 32, `MIN_RUN` 48; eval and live carry the LSTM state over whole runs | `steps.py:124-127`; `end-to-end-fit.md:110-111` | 2026-09-23 · none | J | Self-fed collapse from step 1; `warm30` locks into its step-30 state | **RE-CHECK** (C8). Trained on ≤ 96-step gradients, evaluated over thousand-step runs; the horizon mismatch is untested (I) |
| C5r | Loss weights 1 : 1 : 1 : 0.5; hold BCE *unweighted*; press/release `pos_weight` = neg/pos capped at 20 | `train.py:33, 244`; `steps.py:927` | 2026-09-23 · none | J | TF jump predicted 3,516 against 575 true (press inflated); hold onsets started from idle in 2.0 % | **RE-CHECK** (C2, C3). The asymmetry (press weighted, hold not) is the TL;DR #1 mechanism (I) |
| C6r | Previous-action dropout 0.2 | `train.py:710` | 2026-09-23 · none | J | Round 1 showed dropout feeds "unknown", not known-idle; W uses 0.8 | **STILL VALID** as A's control setting; its role is now tested by W |
| C7r | Augmentation: ±10 % brightness/contrast, DrQ ±4 px on global | `train.py:34, 150` | 2026-09-23 · none | J | Round 3 disables augmentation in H/I/W | **STILL VALID** as recorded. Round 3's H against A contrast includes an augmentation difference; the design says so |
| C8r | The no-HUD arm is the candidate (P2 failed; +0.05 margin, later "P2′ and not worse") | `end-to-end-fit.md:540, 591-612`; `round3-design-a2.md` | 2026-09-23 · 603 pad stills at the *default* pad binds and 265/75 | M (P2 fail) | The pad now uses the alt's custom binds: combo B, GOH RB, swing A, team-up R3 (`recording-log.md:41`; `514a8f7`) | **STALE** for any pad-HUD pixel claim (the `hudmap` slot swap was measured on the old layout). The candidate choice itself stands: the real fit is no-HUD only |
| C9r | Idle downweighting: fully *physical* idle runs ≥ 30 steps weighted 0.1; "not a factor at 0.51 %" | `round3-design-a2.md:7-9, 92`; `idle_sidecar.py:26` | 2026-09-26 · interim train sidecar: 753 / 148,963 rows; fully idle rows 11,689 (7.85 %) | M (counts) + J (disposition) | Counted after AFK and step-away cuts (021320's two ~55 s spans were cut at admission); semantic-idle and onset shares never counted | **RE-CHECK** (C2). A true count of a quantity other than the one the model collapses to (I). k = 30 and w = 0.1 are VPT-inspired judgments |

### D. Decode, executor and pad

| # | Assumption | Where | Date · data | M/J | Changed since | Verdict |
|---|---|---|---|---|---|---|
| D1 | Hold/tap decode: hold iff `held_p` ≥ 0.5; tap iff not held and press and release ≥ 0.5; a lone press is never executed | `executor.py:39-54`; `metrics.py:15` | 2026-09-23 · none | J | Self-fed: `press_p` ≥ 0.5 on 1,602 step-actions, none executed; no hold crosses 0.5 in 24,556 steps. `presshold` latches; sampling over-presses up to 6× | **RE-CHECK** (C3). The diag showed the threshold is not the *only* cause, since blanking the history lets A act (F1 0.079). A train-fixed per-action threshold was never tried (round 1's third candidate) |
| D2 | Pad yaw map to 415 °/s, pitch to 99 °/s, focal 465 | `agent/controller.py:302-317`; `executor.py:8-11` | 2026-09-21 · 265/75, Linear, aim assist 0 | M (then) | Alt is 247/124, aim assist 100 (Spider-Man page); only +0.45 → ~161 °/s measured; focal UNKNOWN (`SITTING.md:137-143`) | **STALE**, marked so in code. Blocks any pilot (VUH-1384). Offline it sets the self-fed caps 13.8° yaw and 3.3° pitch per step (D3) |
| D3 | Self-fed feedback saturates the camera at the pad cap from the default `Cal()` | `train.py:321-326, 624` | 2026-09-23 · D2's maps | J (+stale M) | Caps now unknown for the alt | **RE-CHECK**, low priority (C1 counts how many human steps exceed 13.8° / 3.3°). It cannot cause a zero camera (the collapse is at the zero class), but it biases self-fed pitch (I) |
| D4 | `press_s` 0.033: a one-step tap registers | `agent/controller.py:324`; `executor.py:57-59` | 2026-09-21 · A (jump) 8 ms 6/6 on the old profile | M (then) | Alt sitting: jump 6/6 at every duration; Web Cluster 4/6 at 16-120 ms with readiness uncontrolled (`SITTING.md:249-256`) | **RE-CHECK** at the next PC sitting (pad-binds). A pilot risk, not an offline one |
| D5 | Low-end map and deadzone unmeasured (K3); minimum rotation 0.62° yaw / 1.43° pitch per step | `end-to-end-fit.md:513`; `executor.py:87-95` | 2026-09-23 · D2's maps | J | Still unmeasured; human non-zero \|dx\| median 20-40 counts = 0.66-1.3°/step | **STALE** numbers (they derive from D2). The fact that a large share of human moving steps sits near or below the pad's measured low end is still true (I) |
| D6 | Pilot pad settings 265/75, Linear, assist 0 (Pilot pre-registration item 1) | `end-to-end-fit.md:538-539` | 2026-09-23 · D2 | J | James's alt is 247/124, assist 100; James's settings are not to be changed (`SITTING.md` "Screenshot settings") | **STALE.** Needs a new pilot pre-registration of the pad settings |
| D7 | 10 live actions (the live mask) | `end-to-end-fit.md:1008`; `vocab.py:101-107` | 2026-09-24 · 33.59-min train counts and the old pad whitelist | M | New combat table; 2× data | **STILL VALID** (derived at run time). S2's "6 of 10" assumes the list stays at 10; confirm when the cohort changes |

### E. Process and interpretation

| # | Assumption | Where | Date · data | M/J | Changed since | Verdict |
|---|---|---|---|---|---|---|
| E1 | "Opens": frames matter more with data (ΔF1 +0.007 → +0.036) | `end-to-end-fit-interim.md` | 2026-09-25 · 33.6 and 80.5 min | M (TF only) | Diag: lone-press F1 is not executed | **STILL VALID as stated, narrow.** It is a TF lone-press result; it says nothing about self-fed or executed skill (the lane note already qualifies it) |
| E2 | Scaling rule (b): 3 h would be enough if dev NLL falls linearly in log(minutes) | `end-to-end-fit.md:474` | 2026-09-24 · p5: no-HUD dev NLL *flattens* | M | Interim Δloss closes (−0.001) | **RE-CHECK.** p5 read "flattens", and nobody has computed the implied minutes. "180 min is the target" rests on James's direction, not on the curve (C4 adds a point) |
| E3 | MPS training is byte-deterministic | `end-to-end-fit.md:920-926`; `fit-interim.md` | 2026-09-24/25 · real data, repeated | M | Round 3 may run on CUDA (Modal); new DINOv2 path | **STILL VALID on MPS**. Round 3 re-proves it on its device (prereg §11) |
| E4 | Epoch and model selection by dev *total* loss | `end-to-end-fit.md:861-862, 916-918` | 2026-09-24 · p1 | J | Camera CE dominates the total: 0.5 × 1.83 = 0.91 of the no-HUD arm's 1.43 at epoch 13 (V) | **RE-CHECK** with C6: an argmin driven by the camera head may not suit the action heads (I) |

## Cheapest re-checks first

Every item is offline. Items that read dev are **explore-track** work under the steering charter (full admitted
cohort, frozen dev, tagged EXPLORATORY, no pre-registration). None of them touches validation, test or sealed data,
and none may alter round 3's registered run. The costs are my estimates from the recorded run times.

| # | Check | Answers | Cost | Reads dev? | Owner |
|---|---|---|---|---|---|
| C1 | **Quantisation floor and caps.** Stdlib pass over the train step tables: per-axis MAE of `class_degrees(camera_class(true))` against the true degrees. Also the share of human steps above 13.8° yaw and 3.3° pitch, and above 12.1k counts/s | B4, B6, D3, B1's tail | ~10 min CPU, no model | no (train only) | Policy (r3-impl) or research-methods |
| C2 | **Imbalance census.** On train: per action, the share of steps that are hold onsets, continuations, and releases; the semantically idle steps (no live hold, zero yaw/pitch class) and their run lengths; the same with the admission cut spans restored as a count, from the admission records | TL;DR #2; C5r, C9r | ~15 min CPU | no | research-methods, with admission-owner for cut-span counts |
| C7 | **Is dev typical?** Per train session, dev's human figures: zero-motion MAE, any-hold share, press rates per action, onset-from-still share. Flag 171533 (the drill) and 035932 (the main account) | A2, A4 | ~15 min CPU | no (train human stats; dev figures already on record) | research-methods |
| C9 | **Keyboard-tab swing and wall-crawl toggles**: one screenshot from James | B9 | 1 min of James's time | no | lead asks; admission-owner records |
| C3 | **Re-decode stored checkpoints.** A, D, E and B seeds, inference only. Camera: median against mode against sign-first-then-magnitude, and the share of TF steps where the median is zero while P(non-zero) > 0.5. Holds: per-action start thresholds fixed from *train* press rates | TL;DR #1; B5, C5r, D1 | ~5-10 min per arm on the Mac (A's re-read took ~5 min) | yes, explore | Policy (r3-impl); fit-review reviews |
| C8 | **Horizon mismatch.** The same checkpoints, self-fed with the LSTM state reset every 96 steps against carried | C4r | ~10 min, inference | yes, explore | Policy |
| C4 | **Data scale.** A's exact recipe (no-HUD, seed 0) on the 166.93 trainable minutes; read S1-S4 and TF camera | TL;DR #4; A1, E2 | ~2-2.5 h Mac (A took ~55 min per seed at 80.5 min; 2.07× data) | yes, explore | Policy |
| C6 | **Epoch budget.** One 26-epoch dev curve on the full cohort for A's arm and for one history-free normalised arm; per-head argmin, not total | TL;DR #3; C2r, E4 | ~4-5 h Mac per arm (I) | yes, explore | Policy |
| — | New pad focal, maps, negative directions and deadzone at 247/124 (already planned) | D2-D6 | a supervised PC sitting | no | Live and execution (pad-binds; binds-review) |
| — | Code cleanup: `DEGREE_CAVEAT`, `speed_curve` refusal and the executor docstring numbers | B2, D5 | minutes | no | Policy, after round 3 (touching range_bc now would disturb the round-3 code closure) |

**Order.** Run C1, C2, C7 and C9 first: they need no model and no dev read, and they come back in under an hour. If
C1 shows a floor near 0.2°, G3 needs a representation change before any camera bar means anything. If C2 shows onsets
at about 1-3 % of hold-head targets, the "idle is not a factor" line should be replaced by the measured onset
imbalance. C3 and C8 cost minutes on existing checkpoints and would tell round 3's readers whether an H failure on
holds or camera is a decoder artefact. C4 and C6 are the only runs that answer James's question directly: does the
collapse survive twice the data, and was the 13-epoch recipe ever right beyond 33.6 minutes? Both are explore-track
runs, and both are cheaper than one round-3 arm.

## Limits of this audit

- The ranking is a judgment on the recorded evidence. No recommendation here has been measured.
- The quantisation-floor estimate (TL;DR #5) is a hand calculation from the documented count percentiles and the REPS
  bin widths, assuming a roughly log-uniform spread inside each bin. C1 replaces it.
- I did not read `cm3*.py`, the round-3 implementation, and I did not verify that its defaults match the prereg.
- "Read ≈ 8 times" counts the documented passes over dev; exact reuse may be higher.
