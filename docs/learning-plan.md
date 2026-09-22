# Learning from demonstrations

## Objective and decision

The agent learns Spider-Man decisions and execution from expert demonstrations:
target selection, positioning, engagement, ability sequences, retreat and recovery.
DayMR and ReqMR are James's selected expert sources. Their rank is not independently
verified; channel titles are claims, not leaderboard evidence.

James's September 22 priorities are mechanical execution, finding valuable picks,
escaping effectively, fluent traversal and helping teammates. Traversal means
smooth swings, momentum, bhops and movement transitions, not only route selection.
These behaviors overlap: a player can move and scan while firing or deciding to
help an ally. The policy must not collapse normal play into attack versus standing
still. Neutral output remains a fault/refusal response, not a required human class.

The first mechanical policy learns individual Web-Cluster starts from recent
causal observations, with a fixed visible-target selector and independently
updated scripted aim/movement. The larger policy will learn execution and
movement as well as tactical choices. Jev remains an optional baseline or
annotation assistant; inference alone does not update its weights from outcomes.

Public VODs do not supply exact motor labels. James has now offered expert-level
technical execution demonstrations on keyboard and mouse, so paired motor learning
starts alongside tactical learning. It must keep its action domain separate from the
virtual-pad executor. A policy restricted to the current `State` loses positioning
and temporal context; raw frame history remains available alongside structured observations.

**Quality governs the order of work.** James prioritizes the best-supported path
to capable gameplay over reaching a nominal training milestone sooner. Source
fidelity, observable targets and motion, audited labels, session diversity and
sealed evaluation determine progress. An auxiliary prediction checkpoint is
useful evidence, but does not replace tactical imitation, own-play corrections
or reward-driven learning against opponents that fight back.

This plan follows [the scope boundary](plan.md#scope-boundary): autonomous trials
stay in the practice range or custom games against AI. Matchmade human gameplay is
an offline demonstration source only. The current range guard does not authorize
custom-lobby input; verified lobby navigation and an appropriate guard are prerequisites.

## First visible learned range milestone (2026-09-22)

The refactor is merged on main at `77d5032`, and reviewed event-policy integration
at `8f78ae9`. Six reviewed human event rows have now trained on Mac MPS and
reloaded on Windows CPU. The model reproduces six training labels, compared with
three for an ammo-positive baseline and four for never-start. These two unique
casts and four non-starts remain a tiny, same-recording numerical diagnostic;
independent validation and learned gameplay are pending. The
[fit report](evidence/range-human-fit-v2-20260922/README.md) records exact artifacts
and tracking limitations. Linear carries the active goal:
[VUH-1311](https://linear.app/vuhlp/issue/VUH-1311).

The first executable experiment now learns **Web-Cluster start timing**, using
five causal observations at 10 Hz. `start_web_cluster` requests one bounded pulse;
`no_new_web_cluster` requests no new pulse while aim/movement continue independently.
An ongoing pulse can finish normally. No-new-cast examples can contain scanning,
traversal, recovery or another ability. The controller supplies aim, guarded
approach and pulse delivery; it must not script an offensive fallback. This
experiment does not yet learn full combos, swing control, target value or team play.
The [event contract](lanes/range-policy-reframe.md) names the new version and the
controller boundary that must be implemented and independently reviewed.

The prior Idle/Engage head is a legacy synthetic diagnostic. Its frozen four-row
[visual candidate contract](visual-range-supervision.md) remains historical
evidence: four unknown labels and zero admitted Examples, unchanged. That failed
experiment exposed real perception errors and a poor task definition. It does
not establish that normal moving gameplay lacks useful supervision. VUH-1349's
staged-wait recording request is canceled; stationary neutral support is no longer
a training prerequisite. Old checkpoint classes are never silently reinterpreted.

VUH-1309 admitted six event rows from the already-authorized earlier
22:24:54 normal-resource pre-menu span for this numerical diagnostic. The reviewed
coordinate merge retains 102 unknowns, explicit Luna/Galacta source identities,
and per-window versus continuous-tracking differences. Require observed cast
identity, bracketed onset, full label-interval coverage and the same causal
selected target; retain unknowns. Resource changes are evidence to inspect, not
automatic ability or intent labels. Use independently accepted perception, the
original's accepted timing/build evidence and explicit unknown earlier motor
settings. The unchanged native KBM importer and runtime pad binding remain
separate authorities. A reconstruction-only schema expansion stays parked.

Both recordings share the evening group. A train-only diagnostic may start once
its event examples are reviewed; VUH-1347 remains independent-session validation
for generalization and accepted live reliance, not a prerequisite to the first fit.

Predeclared first pilot: **ten scheduled trials**, each with a verified ready
start and a 20-second deadline, at least eight audited designated-bot completions
and zero scope breaches. Keep all ten in the primary denominator, including
setup failures, interruptions and unknown outcomes. VUH-1319 records target
incarnation, reset epoch, observable KO evidence, all failure reasons and timing.
Run matched scripted trials over the same declared scenario bins and settings;
retain original videos, checkpoint/controller hashes and uncertainty. Compare
James's reference only where starts and outcomes are comparable. This is a
feasibility threshold, not professional-level parity.

The initial consumer runs on Windows CPU; measure acquisition-to-input latency
and game cost before accepting placement. Train on Mac MPS. Each episode starts
with fresh policy history, retains the existing range/focus/watchdog guards and
disables scripted warmup/idle keep-alive attacks. Model refusal stays neutral.
New admission and live-input behavior require independent review. The old eight
input findings (VUH-1325) were already fixed and independently accepted; they are
not a continuing blanket freeze on unchanged reviewed paths.

## Paired human execution: current work

James's new demonstrations change the data bottleneck, not the historical results.
Keep the audited DayMR/ReqMR tactical pipeline, recorded experiments, range guards,
tracker and virtual-pad controller. Add a native keyboard/mouse execution path:

1. Record with the OBS input logger: original video plus raw key/button transitions,
   relative mouse counts, monotonic input times and per-packet composition times.
   The recorder lives separately in `obs-input-logger`; it does not choose examples.
2. Import one finalized session explicitly, with reviewed gameplay intervals, patch,
   cooldown regime, sensitivity/DPI/bindings and a session-group split registry.
   Review imitation suitability separately for each interval: accepted, rejected or
   unresolved, with a reason. Only accepted intervals supply training samples;
   visible gameplay alone does not establish that an action should be imitated.
   Match decoded video PTS to packet PTS. OBS can log stop-tail packets the muxer
   never writes, even when B-frames place their PTS among earlier packets.
   Verify timing against an independently recorded muxer-offset anchor; fitting an
   offset to the same frames is inspection evidence and cannot establish identity.
3. Build causal frame/input history and distinct future action bins. Focus loss,
   pauses, raw-input errors and missing timing do not become neutral controls.
   OBS composition is not the player's observation clock: any alignment assumption
   or measured bound is recorded. A passed importer does not prove reaction latency.
4. Fit a small temporal execution baseline and compare on separate recording sessions
   against held-input persistence and fitting-set action statistics. Report held
   controls, press/release edges and mouse error separately, including unsupported
   controls. A short successful fit checks plumbing; it does not prove gameplay.
5. Inspect transfer failures before connecting learned execution to the existing
   guarded loop. A keyboard/mouse checkpoint cannot drive a virtual pad. Reusing
   learned visual features or semantic skill supervision across domains is a later
   measured experiment; copying mouse counts into stick axes is not an adapter.

The immediate software contract is in [human-demo-schema.md](human-demo-schema.md).
This advances A and E in parallel with B. It does not wait for every VOD HUD negative
to become observable. The existing four future-behaviour forecasts remain auxiliary
signals, not executable actions or an already-trained tactical controller. Whole-match
autonomy still needs learned target/position decisions, corrections, reliable episodes,
AI-only custom-game guards and the outcome evaluations in F.

Use PyTorch for the new execution consumer so the same checkpoint can be exercised on
the Windows RTX 4080 SUPER and the M5 Max (128 GB) through CUDA/MPS/CPU. The historical
MLX experiments retain their implementation and fingerprints. Train on the Mac while
the game uses the PC GPU; use the PC for training only when it is free. Choose live
inference placement from measured capture-to-action latency and game frame-rate cost.
The durable [machine contract](machines.md) covers each machine's responsibilities,
bidirectional SSH, checked relocation of original recordings and checkpoint return.

## Roadmap and advancement gates

Demonstrations initialize behavior; they do not limit what the agent may learn.
After a competent bounded imitation policy and measured outcomes exist, permit
reward-driven exploration of its executable choices. Keep improvements only
when they transfer to untouched starts or encounters. The first web head can
discover timing changes, but cannot discover swing or bhop techniques while
those controls are fixed. E therefore expands learned execution and movement
parameters; F adds ally/threat/objective context. Avoid a permanent library of
fixed combos masquerading as learned mechanics, and avoid rewards for novelty,
constant movement or damage farming in place of useful outcomes.

This imitation-to-RL direction has precedent in [VPT](https://arxiv.org/abs/2206.11795);
combining reference behavior with task objectives is also demonstrated by
[DeepMimic](https://arxiv.org/abs/1804.02717). These inform the design, not a claim
that their results or data efficiency transfer to this game. Measure usable
episodes per hour on our real game instance before choosing the RL algorithm or scale.

The roadmap advances on evidence, not footage hours. Current evidence includes
two inspected pilot clips, nine acquired guides (about 106 minutes), and about
60 raw minutes from four VOD sessions; raw duration is not accepted training
duration. The aligned two-window annotation rerun agrees on coarse tactical
purpose, but exposes event-extractor defects. The HUD lane produces event format
5 with separate occurrence and evidence-availability clocks; accepted loader and
policy seams preserve unknowns. Reader findings still qualify individual labels
(VUH-1306), including HP changes at bonus-maximum transitions.
The policy lane has an offline DINO encoder / GRU intent-training pipeline;
on the two multi-intent normal-cooldown sessions it beats the majority baseline
but not repeating the previous decision. Transition weighting worsens held-out
change accuracy; further tuning waits for better examples. This is scripted-brain
distillation evidence, not an accepted gameplay policy. RL is not implemented or
accepted. The next deliverable
is a small trustworthy training/evaluation set and a first imitation baseline,
not an exhaustive archive.

| Milestone | Concrete result | Gate before advancing |
|---|---|---|
| A. Trust the examples and measurements | Corrected HUD events, per-frame visibility, reviewed imitation suitability, whole-session splits; paired human keyboard/mouse demonstrations and repeatable range episodes | Hand-check VOD event classes and timing; preserve unknowns. Verify human input/video alignment, focus continuity and recorded settings. Demonstrate start, terminal outcome, interruption and reset alignment on recorded episodes. Data quality gates imitation; episode/reward quality separately gates RL. |
| B. First imitation policy | A temporal mechanical event policy, initially learning web starts alongside independently running aim/movement | Compare supported starts/non-starts, onset timing and rare-event behavior with never/always-start and comparable scripted baselines on held-out sessions. Measure runtime latency and actual range outcomes. No standing-idle class requirement. |
| C. Corrections from our own play | Reviewed execution/navigation corrections and a retrained imitation checkpoint; combat retreat/recovery examples require F's fighting environment | Compare against B on untouched evaluation sessions and bounded live scenarios. Accept demonstrated improvement; ambiguous failures stay out of positive imitation labels. This loop continues alongside later milestones. |
| D. First reinforcement-learning experiment | Fine-tune a trainable option policy on one bounded range encounter, starting from an imitation checkpoint with demonstrated range competence | Reward audit below passes; reset and episode recording work; freeze perception/controller/target selector for comparison. Retain the RL checkpoint only if held-out encounter outcomes improve over its starting checkpoint, not merely its training return. |
| E. Learned execution, target choice and fluent traversal | Trainable ability sequencing, aim/movement, swing release/jump timing and bhop transitions through measured executors; observable targets/destinations | Evaluate each learned output separately, including smooth transitions, observed momentum retention, arrival, time, charge use and collisions/falls. Transfer to new starts. Explore better execution within that controllable space; guide narration cannot supply motor labels. |
| F. Tactical learning in AI-only custom games | Opportunity selection, pick commitment, injured escape/re-entry, teammate assistance and objectives through imitation then RL | Verified AI-only lobby/guard and episode/outcome flow; observed ally/threat context. Evaluate peel/protection and missed support, survival and objectives alongside wins. Kill counts alone cannot certify team value. |

These are dependencies, not six serial waits. Reward measurement starts during A;
E's recorder and controller work also starts now. D can test narrow range learning
without waiting for expert-level swinging. An initial F intent-only trial can use
the fixed selector, but cannot claim E's target-choice or positioning capabilities.
E's offline box-annotation and camera-motion feasibility probes below run alongside
these prerequisites; the first narrow policy does not defer all work on game sense.

B has a pipeline prerequisite under VUH-1311: cache encoder embeddings and train
a temporal head to imitate the scripted brain on our own logged sessions, with a
held-out-session comparison against the majority baseline. This establishes a
working training/inference path, not learning from Day/Req or improving the
teacher. Expert footage may supply embeddings without supplying trusted action
labels. The separate coarse tactical-purpose head still needs A's audited labels;
its metrics and claims stay separate from scripted-brain distillation. Any
`--brain learned` integration retains the scripted policy's execution guards.

### B0: auxiliary pretraining by predicting observed ability events

The current reference experiment predicts **per-ability event occurrence**, with
unknown labels masked out. It uses five seconds of causal frames at 10 Hz and a
fixed one-second future horizon. A shared frozen encoder and temporal head forecast
`get_over_here`, `swing`, `uppercut`, `web_cluster_fired` and `teamup` independently;
several may occur in one horizon. This is auxiliary video pretraining under
VUH-1311, not a controller policy, global first-action ordering or completion of B.

**Why independent channels.** The retained global-next-event diagnostic under
`data/experiments/b0/` has 22 Day and 96 Req eligible windows, all negative, and
zero eligible positive events. Requiring every channel to be observed across every
cast discards the positive examples; fitting those constants would teach nothing
about event choice. The revised task preserves a verified cast on one channel
without asserting that an obscured different channel had no cast. The failed
build remains evidence; it is not a trained checkpoint or a completed fit.

**Target contract.** Per ability and horizon `(t, t+1]`, there are three outcomes:

- Positive: at least one audited event interval is wholly inside the horizon.
  Other channels may be unknown. Charge and countdown evidence corroborating the
  same cast is deduplicated; web-ammo expenditure proves a shot, not a burst.
- Negative: that channel satisfies the HUD lane's complete observed/stable/no-event
  rule, including prior-read, confirmation and segment-edge margins. No verified
  event alone is insufficient. Normal cooldown provenance and known slot identity
  are required; availability blips do not count as casts.
- Unknown: neither is established. Exclude that channel from the loss and score,
  not the whole window when another channel has a supported label. An interval
  crossing a boundary is not a positive; it prevents a negative unless separate
  evidence resolves the ambiguity. Do not convert unknown to zero.

The classifier uses five binary outputs and a per-channel loss mask, not a sixth
"none" class. A channel with no positive or no negative fitting examples is
unsupported for fitting and comparison. A model seeing only an unsupported channel
must not be called trained on that ability. Source gameplay, complete five-second
history, no hard cuts and a clean future gameplay segment remain required. A
short cut-free scoreboard gap can appear only in masked preceding context.

Timing has its own mask. Train a class-conditional delay only where a unique first
verified interval within that channel is identifiable, with no potentially earlier
boundary-crossing interval; multiple/ambiguous evidence may still label occurrence
positive while leaving timing unknown. Score distance outside `[t_from-t,t_to-t]`,
zero inside, and report interval widths. These are verified-event intervals, not
exact button times or a claim that no unobserved cast occurred earlier.

**Observability and bias.** Raw outputs of unchanged frozen readers for the two
accepted training clips live under `data/experiments/b0/`, using the event file's
recipe and clip clock. Apply the HUD lane's
[per-frame contract](lanes/l2-hud.md#per-frame-observability-contract-for-b0).
Do not infer lockout versus unreadability from a dim icon alone. The HUD lane's
read-only check of these two sources finds no raw state that reliably separates
lockout from unreadability: dim-without-countdown is not consistently enriched
after another ability's cast. It supplies no mechanics-based negative labels;
these cases remain unknown. Any later recovery needs a separately checked signal.
The 10 Hz sampling limit and undetected Day icon-overlay contamination remain
limitations; contamination prevalence is unknown, not zero.

The label mask is **not missing at random**: calm scenes more often supply clean
negatives, while fights obscure or lock slots. Report positive/negative/unknown
counts per channel and session, unique positive events, timing support, and the
same counts split by whether any verified event was confirmed in the preceding
five seconds (a sampling diagnostic, not a tactical label or model input).
Scores describe the observed subset, not all gameplay. Keep sample exclusions
and selection bias visible rather than increasing volume by guessing negatives.

**Inputs and comparison.** The reference policy remains frames-only: the shared
embedding/present/masked feature prefix, with `events=None` and no State or future
outcome features. Raw HUD observations and offline events supply labels and
explicitly separate diagnostic baselines, not neural inputs. The event-input
prefix-causality gate is still unproven; do not add those inputs implicitly.

Fit only the two lead-promoted TRAIN sessions through `Demos.load_split` and
explicit cache IDs. Run Day-to-Req and Req-to-Day development folds; every learned
quantity comes from the fitting session alone. Creator and session effects are
confounded. Sealed evaluation sources and unresolved-overlap uploads stay out of
all fitting, tuning and evaluation here. Per-source kit/patch and normal cooldown
provenance, accepted segmentation, masks and reader-version gates remain binding.
Cross-patch pretraining and the later tactical head do not delay this reference fit.

Compare each channel on identical masked held-out support against always-negative,
fold-local prior/majority, recent-use persistence and a HUD-resource baseline.
For the latter, use only raw readings at or before t: known cooldown remaining,
charges and time since an observed ready transition, with explicit unknowns.
A small predeclared bucketed predictor fitted on the training session is sufficient;
no hyperparameter search or unseen-field imputation. Report that it has structured
HUD information the frames-only model lacks. Any event-derived persistence signal
retains its unproven online-extractor causality limitation; it is an offline
reference, not a deployable result. Compare timing with the fitting-only median
interval midpoint on the exact same class-supported rows.

**Support and acceptance declared before fitting.** A channel needs at least
20 distinct verified positive events and 20 non-overlapping one-second negative
horizons in a held-out session for a directional improvement claim. This is a
screening minimum, not a statistical guarantee. Below it, show descriptive metrics
and mark that channel inconclusive. Report positive-class precision/recall/F1,
per-channel confusion and probability error, plus timing error/width/coverage.
Report all-channel descriptive macro F1 separately from the supported-channel
comparison; zero-support channels cannot generate a pass. A claim across both
creators requires support and improvement in both directions.

Use one predeclared configuration, fixed thresholds and the final epoch only;
no tuning or checkpoint selection on these held-out folds. Save source/reader/cache
versions, masks, source counts, exclusions, actual fit command and code fingerprints,
seed, elapsed time, predictions and reloadable checkpoints. Preserve the immutable
configuration declaration separately from actual execution provenance. A negative
or inconclusive trained result completes this bounded probe; a zero-positive data
build does not. Improvement requires beating the strongest applicable baseline on
supported channels and matching timing comparisons, not just reducing training
loss. No live deployment or gameplay-competence claim follows B0.

**Measured reference.** The local `b0-multilabel-v1` experiment contains two
40-epoch final checkpoints with the fixed two-layer 128-wide GRU. It fits 1,414
Day windows or 1,836 Req windows with at least one supported label; held-out
metrics use the per-channel masks across 2,305 Req or 1,937 Day windows.

| Development direction | Supported-channel model F1 | HUD-resource F1 | Model timing error | Training-median timing error |
|---|---:|---:|---:|---:|
| Day to Req | 0.512 | 0.597 | 0.178 s | 0.132 s |
| Req to Day | 0.554 | 0.390 | 0.193 s | 0.148 s |

Req team-up has only 17 distinct positive events and is excluded from that
direction's supported-channel F1. Timing uses identical supported interval rows
for model and median. No channel clears the combined occurrence-and-timing
improvement gate. These are observed-subset development results from one session
per creator, not sealed-test results or evidence of game sense. The checkpoints
reload to identical predictions over both complete held-out folds with the
recorded evaluation batch size of 128. Artifacts and the reproducible command
live under `data/experiments/b0-multilabel-v1/`; implementation and provenance
are described in [the policy lane](lanes/policy.md).

**The archived B0 labels contain confirmed duplicate casts.** The read-only
[HUD measurement](lanes/l2-hud.md#gap-resumption-casts-measurement) finds 17
duplicates, six valid casts and one unknown in 24 inspected cases from 246 casts
across the two train sources; this targeted sample is not a population error
estimate. A two-frame-or-longer digit dropout becomes `off`, so the same countdown's
return is emitted as a new cast. Removing confirmed duplicates alone takes Day
team-up from 20 to 19 distinct positives, below the declared support gate; Req
team-up is already below it. The table above retains its original support
definition and numbers, not a corrected supported-channel comparison. Both model
labels and the HUD-resource baseline are affected. Four Day histories contain
spectated-HUD frames and seven Req histories contain an unmasked brief scoreboard.

The repair belongs in the extractor: unknown readouts do not establish readiness,
and a continuing cooldown remains the same cooldown through missing observations.
New casts require valid transition evidence under the source's kit and charge
rules, not simply a reappearing numeral. On multi-charge abilities, another use
can occur during recharge; continuing countdowns alone neither prove nor disprove
that use. Ambiguous gaps remain unknown. Regression evidence includes the 17
confirmed duplicates, six valid controls, charged-slot second-use/recharge cases,
the spectating/short-respawn transition and brief scoreboard, while preserving
the existing false-killcam rejection.

The primary2 outcome pass, eight-window comparison and format-5 writer repair are
complete. Accepted writer `21a390f547eb` and regenerated manifests supply the corrected
experiment; frozen event/annotation packets remain unchanged as evidence. Future
regeneration keeps manifests identical to event segments. Inventory the regeneration's source IDs first; sealed
sources are not implicitly authorized by a batch-wide command. Rebuild affected
reader sidecars and derived windows under the new fingerprints, preserve the
original artifacts, and independently review provenance, masks and event validity
before recounting support. No extra upload-wide measurement is needed to establish
this already reproduced defect.

The corrected recount includes **one-second support as a diagnostic**;
the archived one-second fit remains unchanged and no one-second refit is pending.
The accepted fit already uses **per-channel masks**; the abandoned global
all-five-known build is not its eligibility rule. Reduced all-channel visibility
does not measure corrected B0 support.

**Separate two-second occurrence experiment, declared before corrected support
counts or model scores.** Whole-second countdown observations have roughly a
one-second quantization band before sampling/tolerance; requiring that whole band
inside a one-second target makes many countdown labels structurally ineligible.
Use exactly `(t,t+2]`, twice the displayed time quantum, for one new experiment
after writer/consumer acceptance. This predicts casts, not when OCR confirms them.
Keep the same five-second history, channels, per-channel masks, session folds,
architecture, hyperparameters, seed, threshold and final-epoch selection. Scale
the timing output to the two-second horizon and recompute every baseline on the
identical corrected support, with train-only fitting/normalization. The support
floor remains 20 distinct verified positives and 20 non-overlapping negative
horizons per held-out channel; those negative horizons are now two seconds.
Keep prior-read, confirmation and segment-edge margins. Unsupported channels stay
inconclusive; no supported channel or constant fitting labels means stop before
fitting. No further horizon search is authorized.

Count distinct-positive support conservatively: within each segment, select disjoint
occurrence intervals separately per evidence kind, then take the largest count,
not the sum across cast and charge witnesses. Sum those lower bounds across segments.
Unresolved cross-kind pairings are reported and never credited twice; matching
physical uses is not established by disjoint evidence bounds. A numeric ability
negative requires a common expiry interval across every sample, using the writer's
whole-second rounding band and frame tolerance; its width must exceed 1e-6 s so a
frozen H1 window cannot pass by floating-point noise. Also reject upward resets
(the tolerance can admit a small upward step), with constant validated charges on
charged slots. Ammo remains constant. Every sampled read must be observed;
a missing or ended countdown is unknown. This replaces raw-value constancy, which
cannot certify a whole-second countdown over the declared horizon.


Save a separate run specification and output directory, identifying this as a
changed task. Compare models with baselines within that task; its F1/timing scores
are not directly comparable to the archived one-second results. Report occurrence
interval widths and coverage with timing errors; a wider zero-error band is not
improved timing precision. One-second support remains visible even if unusable.
This authorization replaces the pending same-horizon refit, not its archived
results or acceptance claims.

**Corrected H2 result: complete, no joint improvement.** The unchanged five-output
experiment has two final-epoch checkpoints under
`data/experiments/b0-multilabel-format5-h2/`. Only web-cluster firing meets the
held-support floor in both directions: distinct-positive lower bound / independent
negative horizons is Day 84/58 and Req 101/69. Team-up has no verified positives;
other channels remain inconclusive. There is no horizon search or further B0 fit
authorized by this result.

| Supported WEB measure | Day → Req | Req → Day |
|---|---:|---:|
| Model F1 / strongest declared baseline F1 | 0.730 / 0.703 | 0.762 / 0.722 |
| Model / median timing interval error, seconds | 0.471 / 0.292 | 0.417 / 0.310 |
| Joint improvement gate | not met | not met |

Both saved checkpoints reproduce exactly with the recorded batch grouping, and
baseline outputs and metrics match. Occurrence F1 is higher on the observed subset;
timing is worse. This is neither statistical evidence of generalization nor a
controller ready for deployment: two development sessions confound creator and
session, masks are nonrandom, and no tactical or gameplay outcome is evaluated.
[The policy lane](lanes/policy.md#corrected-h2-result) holds full support, timing-width
and reproduction details. Coarse-purpose imitation remains the main learning
line; the single-charge no-use measurement below is a separate proposed enabler.

Format-5 consumers enforce the following contract. An `ability_uncertain`
interval overlapping a horizon or its confirmation margin prevents a negative
for that channel; it does not discard other channels. An independently verified,
contained cast can still prove occurrence, but possible earlier casts suppress
first-event timing. Preserve event confirmation/availability time separately from
occurrence bounds for causal inputs and baselines. Confirmation delay is not
irreducible cast-time uncertainty: retain tighter bounds only where timer/charge
evidence actually proves them. Whole-source calibration and later timer refinement
must not masquerade as knowledge available at the earlier event time. An observed
countdown maximum does not establish the full duration of a partly seen timer;
kit duration and variant need independent evidence or remain unknown. Uppercut's
short lock is patch-dependent even where its recharge duration is unchanged.
Durations are explicit inputs from a versioned kit table, keyed by source patch
and team-up variant; missing mechanics leave that slot's timer inference uncertain.
Measured countdowns supply contradiction alarms, not modal duration calibration.
This does not erase independently supported charge-decrement events.

When the patch is known and its team-up variant set is complete, an unknown
variant may use the **union of occurrence intervals over all admissible variants**
to bound `ability_uncertain`. Use the existing confirmed-timer evidence and
rounding/timestamp tolerances; an isolated OCR digit is not sufficient. Retain
every compatible variant, including starts before the segment and explanations
involving a continuing cooldown. If the schema stores one interval, use the
union's enclosing interval, never its intersection or the shortest alternative.
Unknown patch, incomplete variant set or contradictory evidence retains broad
uncertainty. A uniquely compatible duration still does not promote this event
to `ability_cast` or certify per-segment variant identity; that needs independently
verified identity evidence. Apply bounds using evidence available at `known_at`,
without later silent narrowing. This optional precision improvement does not
replace the charge-reader correctness gate or change the two-second experiment.

Each event separates occurrence `[t_from, t_to]` from `known_at`, when all evidence
needed for that committed assertion is available. With identical kit inputs,
extracting any prefix must give the same events with `known_at` inside that prefix
as extracting the full sequence, field for field. Future contradiction alarms
cannot silently rewrite earlier assertions while retaining their old knowledge
time. The property must also retain the verified control casts and charged second
uses with finite, evidence-justified knowledge times: empty output, unknown-only
output or arbitrary end-of-file deferral is not a passing repair. This contract
does not require a separate streaming service.

The file-writing path must use the same resolved kit inputs for extraction,
metadata and its regeneration recipe, including an explicit patch override.
Test written outputs for known, missing and unrecognized patches and an override
that differs from the manifest; regeneration must preserve the selected inputs.
Before format-5 regeneration is promoted, loader observations and policy event
features gate evidence on `known_at` (including each historical feature step),
while target construction retains occurrence bounds. Missing format-5 knowledge
timestamps fail loudly, never fall back to occurrence time. Keep archived
format-4 experiments unchanged.

**Positive glyph evidence is admissible for measurement, not yet certified.**
An explicit per-frame match to the expected ability glyph is different from
"lit, no digit". Keep it as a named, switchable observation with reader/version
provenance; absence of a match is unknown. Validate against native-frame labels
per creator and slot, including visible countdowns that digit OCR misses, chat,
dark scenes, effects and prohibition states. Zero matches on OCR-readable
countdowns alone does not measure false positives on the unreadable cases this
signal is meant to recover. Record denominators, false matches and unknowns;
freeze thresholds before the audit and retain conflicting glyph/digit evidence
as unknown. Enabling it for labels requires the measurement's acceptance.

Its immediate claim is **glyph displayed / no countdown drawn**, not ready or
no cast. The native review reports Day uppercut charges dropping at 46.7 s while
the glyph still identifies at 46.8, before the lock appears at 46.9. Putting the
cast after the last glyph would exclude that real use. Fix the MK charge reader
against the seven legible badge transitions and retain charge evidence as the
primary timing witness there. A glyph-to-countdown transition may tighten cast
bounds only with a verified ability-specific onset relationship, including any
display delay; otherwise it bounds countdown appearance. It does not alone
certify B0 negatives or readiness through missing frames. The existing matcher
returns generic `teamup`, not a partner/variant identity; variant assignment
needs separately verified per-segment evidence or remains unknown. Retain the
declared two-second experiment even if accepted glyph evidence improves precision.

**Post-H2 no-use audit: not supported for training.** The
current ability-negative rule requires a visible running countdown throughout
its horizon; it provides no examples of an available ability deliberately left
unused. The completed H2 run remains unchanged. The frozen audit rejects the
proposed H=2, m=0.5 certificate; no new negatives or glyph-reader activation are
authorized. The stronger gold-state counterexample remains disputed, as recorded
in [the policy lane](lanes/policy.md#goh-hindsight-no-use-feasibility-audit-vuh-1311).
The audited candidate is defined below for interpreting that result.
For a verified single-charge slot, a trusted no-countdown witness at `s` can exclude
use in `(t,t+H]` only when every such use would necessarily have a visible countdown
at `s`. The proposed interval `t+H+m <= s <= t+D_min-m` is conditional on verified
onset/display bounds and a lower bound on effective cooldown duration; `m=0.5 s`
is a hypothesis to measure, not an accepted constant. Require uninterrupted own-hero
play and slot/variant identity through `s`, with normal cooldowns, no reset/reduction
mechanic or edit, and a live HUD. Unknown conditions or conflicting evidence censor.

This is a candidate target certificate, not a readiness certificate at `t` or proof
of tactical intent. Report independently whether availability at decision time is
known; do not rename all new negatives "chose not to cast". Glyph matches must use
the source's accepted slot mapping. First audit native single-charge cast controls
and proposed negatives, including OCR-missed countdowns, overlays, prohibition
states and transition delays, with frozen thresholds and an independent reviewer.
Charge slots are excluded; team-up also requires verified variant identity. No
writer, label, sidecar or fit change is authorized by this candidate alone. If
accepted later, record its look-ahead endpoint for target construction and split
boundaries; future evidence never enters model inputs, baseline inputs or sampling
features. Preserve the current H2 artifacts and describe selection bias in both
the old and newly observable subsets.

Neither a lit icon without digits nor an earlier cooldown expiry proves present readiness through an
unobserved interval. Update loader fields, removed-kind checks and feature
semantics together: retain health `cause`, never encode unknown-cause HP loss as
damage, and do not silently zero renamed event channels. These are semantic
repairs under the fixed experiment, not hyperparameter changes.

Purpose annotation retains its immutable proposals and recorded disagreements;
comparison does not promote disputed event labels to truth. The regeneration also
corrects existing health-transition and icon-state semantics: HP gain/loss alone
is not healing/damage, bonus-pool changes need evidence, and missing evidence leaves
cause unknown. A prohibited/dim icon is a display-state observation, not proved
mechanical availability or a cast. Native regressions cover the reported bonus-health
and prohibition cases. New control-loss and KO-medal readers remain separate work;
manual observations are retained without turning those missing modalities into
prerequisites for the cast repair.

**Coarse-purpose labels remain the next head.** The completed first tranche uses
24 development windows, 12 per creator from accepted train sessions, under
the aligned 10 Hz protocol. Sample across ordinary combat, traversal/search and
recovery evidence, without assigning purpose from those sampling cues. A primary
vision annotator labels them; Codex independently labels eight preselected windows
(four per creator) before seeing that pass. Compare and adjudicate those eight
before expanding the tranche; disagreements remain unknown until resolved against
media. A visible HUD and the correct hero do not establish tactical gameplay:
pre-round spawn-room waits may be marked `unusable: pre_round`. Preserve that
judgment in the frozen tranche; exclude pre-round windows from future candidate
lists rather than silently substituting examples after annotation begins.
Annotators receive phase-filtered observation packets, not full loader objects or
source event streams: context packets contain only the permitted frames, raw HUD
rows and events confirmed by the decision time. Freeze context judgments before
releasing outcome packets. The second pass's accidental full-Day event-stream
exposure disqualifies its four Day context judgments from the clean comparison;
retain the disclosed pass. Their fresh replacement is complete under
`purpose-tranche-1/codex-day-repair/`: four contexts frozen before outcome release,
then four outcome records preserving those contexts byte-for-byte. Hash and
structural checks pass. The original second pass's four Req windows supply the
other half of the comparison below. A valid checksum proves preservation, not
context-first independence or label accuracy. The original primary pass also
fails this boundary in all 24 windows: segment endings and event values confirmed
after the decision were exposed before context judgments. Preserve that pass as
hindsight-exposed evidence and exclude it from clean agreement scores. A fresh
primary pass uses the same phase-filtered packet producer as the independent
pass, with no full-stream or loader-object access. For sequential windows from
one source, save each context judgment before opening a later window; release
outcomes only after the context pass is frozen. Future candidate lists separate
decision times by at least 15 seconds within a source, in addition to excluding
pre-round waits. Existing adjacent selections remain disclosed development
examples, not independent samples.
The frozen `primary2/context/NOTES.md` reports scene-sheet inspection and mostly
one native decision frame per window, with one HUD sheet for pt1-00, rather than
all supplied 10 Hz native HUD strips. Its reported temporal isolation is distinct
from this inspection-method deviation. Preserve the locked contexts; compare
coarse purpose with that limitation stated, not as full aligned-protocol compliance
or detailed HUD-event agreement. The outcome pass inspects all supplied scene
cells and HUD strips. The separate native-evidence audit resolves cast disputes.
The completed comparison is retained in
`data/demos/annotations/purpose-tranche-1/comparison/REPORT.md`, with reproducible
counts in `compare.py` and `metrics.json`. Usability agrees 8/8; preferred purpose
agrees 6/7 usable windows (five engage, one reposition). Pt1-08 remains
reposition/disengage, and pt1-29 is unusable pre-round. Target status agrees only
4/8 (3/7 usable); the sole shared box has IoU 0.4804 and is not accepted as precise
geometry. Outcomes agree on no own death and final HP, but ult use at pt1-05,
health-pack attribution at pt1-36 and target continuity remain unsupported.
These are method-limited development agreements, not accuracy estimates or a
training promotion. No annotation expansion or purpose-head fit is authorized
by the six agreed examples.

Later combat does not prove that an earlier reposition judgment was wrong.
Keep observed movement/attack separate from inferred purpose; ambiguous travel
retains alternatives or unknown. A future-action forecast is a distinct label,
not a hindsight-corrected current purpose. Control loss also differs from inability
to observe purpose: future annotation distinguishes actor eligibility from label
observability. The lead assigns independent annotator seats and owns comparison
and acceptance. This tranche does not block B0.

**Completed audit: format-5 purpose tranche 2.** Both independent passes cover
24 development windows (12 per creator) from the two promoted train sections.
Preferred purpose agrees on **17/24**; acceptable sets are identical on **9/24**
and overlap on **24/24**. Overlap is not correctness or unique intent. Usability
and actor eligibility each agree on 23/24; preferred agreement is 15/22 where both
passes call the actor eligible and the window usable. Search and idle have no
jointly preferred examples. These are sampled, creator/session-confounded
agreements, not accuracy or prevalence estimates.

The accepted development manifest retains **8 ordinary singleton candidates**
(all engage, Day 3 / Req 5), **14 set-valued candidates**, one powered-state
purpose-only window and one frozen/actor-ineligible observation. Alternatives are
neither one-hot labels nor probability distributions. Selected target identity
and geometry are not promoted. The report and per-window inclusion reasons are
in `data/demos/annotations/purpose-tranche-2/adjudication/acceptance/REPORT.md`
and `adjudicated-manifest.json` beside it. Raw passes stay frozen; native-evidence
adjudication does not rewrite agreement numbers. The fresh adjudicator shares a
model family with the primary and is fallible; root's spot checks and exposure
limitations are disclosed in the report.

**Training implication:** ongoing engagement is the strongest supported label in
this sampled set. Recognizing an existing fight does not establish a policy for
deciding to start one. Observable approach toward visible enemies, tracking and
preparation to attack can support an engagement inference before an exchange
begins; they must not be discarded merely because repositioning is also occurring.
Keep compatible behaviour labels separate from inferred purpose and retain unknowns
where the evidence is ambiguous. The tranche does not establish a six-class
training set, a sufficiently supported escape class, or target choice. No fit
follows without a specified task and support gate.

**Option R is accepted as a bounded activity requalification.** The two fresh
context-only passes agree on 15/17 activity judgments. Controls add no examples.
Pt2-05 gains settled-noncombat support and pt2-22 gains ongoing-exchange support;
ordinary support is **Day 4 positive / 1 negative, Req 6 / 0**. At 22 the shared
opponent-directed shot supports the label while incoming-fire attribution remains
unresolved. At 05 settled local traversal does not mean idle intent or no enemies
elsewhere. Pt2-04's special state and 08/13's activity disagreements stay unresolved.
Prior purpose sets and frozen source judgments remain unchanged. The additive
acceptance is `data/experiments/purpose-task-v1/requalification/acceptance/`;
training remains unauthorized and neither gate passes.

**The next expert task forecasts compatible behaviours in `(t,t+2]` from causal
`[t-5,t]` frames.** Approach, attack, moving away and traversal without a visible
enemy have independent present/absent/unknown labels. Context state is frozen before
outcomes; onset and continuation are reported separately. Purpose sets remain intact,
and purging includes the full input, label and confirmation footprint. This is expert
future-behaviour imitation, not another required current-engagement recognition fit.

The four-window native canary has 14/16 channel-state agreement across independent
passes. Three windows share eligibility, contributing four positive and four negative
channel cells, including two attack onsets and a no-attack traversal control. Those
are not eight independent examples. Approach at pt2-10 and moving-away at pt2-05
remain unknown; pt2-22's disputed future eligibility masks its imitation labels
without changing its earlier context-only Option R acceptance. Seat B declares
prior high-level label exposure for 05/22; this is a method check, not blind accuracy.
The frozen comparison and runnable check are under
`data/experiments/purpose-task-v1/next-behaviour-canary/comparison/`.

The full 24-window pass is accepted for a bounded pipeline smoke experiment.
The seats agree on 81/96 channel states, including all 24 attack states; agreement
includes unknowns and does not establish accuracy. Fifteen contexts share ordinary
control eligibility over both input and future (Day 8, Req 7). Their attack support
is Day 4 positive / 4 negative and Req 5 / 1, with one Req unknown. Across all four
channels there are 20 positive and 19 negative supervised cells, not 39 independent
examples. Nine contexts are excluded, including pt2-01 after both seats disclose
unnecessary post-target event-metadata exposure. No replacements occur. Raw purpose,
Option R and context judgments stay frozen. The comparison, exclusions, support and
runnable check are `data/experiments/next-behaviour-v1/admission/`.

The independently reviewed offline consumer is `policy/behaviour.py`. It reuses the
existing frozen visual encoder and temporal head with exact canonical two-source
bindings and per-assertion evidence. Writer and encoder timestamps have separately
validated origins; exact decimal-grid lookup selects all 765 inspected history frames
without future samples or preceding-frame substitution.

The first expert future-behaviour smoke fit is complete under
`data/experiments/next-behaviour-v1/smoke-01/`: seed 0, 40 epochs, batch 64,
Adam .001, hidden 128, final checkpoint, whole-session folds and unchanged four
outputs. Both saved temporal checkpoints reproduce their held predictions exactly.
Attack is the only channel with both fitting classes in both directions.

| Fit → held session | Held attack P / N | Temporal balanced accuracy | Decision-frame baseline | Privileged context persistence |
|---|---|---|---|---|
| Day → Req | 5 / 1 | 0.900 | 0.700 | 0.700 |
| Req → Day | 4 / 4 | 0.625 | 0.500 | 0.625 |

These tiny-sample numbers establish an executable pipeline, not accepted performance.
The Req result has only one negative; the reverse direction ties persistence.
Onset and continuation subsets are reported separately, applying the occurrence
forecast rather than separate heads. Event-rule baselines have unknown evidence and
use the declared fit-majority fallback. Unsupported channels remain excluded, and
single-class held subsets do not earn balanced accuracy. The unchanged 20-positive /
20-negative support gates remain unmet; `performance_claim` is false. Ten-Hz labels
do not certify behavior between samples. More admitted behaviour examples from held
footage, including supported contrasts, are the next data dependency; this smoke
result does not authorize tuning, new acquisition or learned deployment.
Existing `Engage` bundles movement and attack: the proposed joint mapping still has
no fully supported executable example and is not accepted learned control.
Scripted fallback performance is never credited to the model.

The held-footage inventory contains four open Req uploads totaling 76.65 raw minutes.
Both bounded screening passes find own-play candidates mixed with pre-round, replay,
spectator, death and scoreboard material; sampled endpoints establish no continuous
usable duration. Older patches and underlying-session independence remain unresolved.
The new Day extraction stays inspection-only after independent review confirms actor
and scoreboard admissions; visibility masks alone do not certify eligibility. The
two-section capacity ceiling is not exhaustion of held footage or creator archives.
Acquisition remains parked while accepted packets and held candidates are used first.


The authorized next collection qualifies complete `[t-5,t+5]` footprints in the
held Req840 section and newDay section before annotation. It reuses existing
screening and immutable reader segments, with up to 40 candidates per source;
counts are a processing cap, not promised eligible examples or class support.
New decisions are at least 11 seconds apart, leaving disjoint 10-second evidence
footprints; the earlier purpose-tranche's 15-second selections remain frozen.
This changes sampling density without changing full-footprint clustering, purge,
unknown handling or source-group isolation. Req840 and Req1980 share one broadcast
and cannot straddle a fold. NewDay remains inspection-only until window admission;
its date-derived patch and unresolved sealed re-air possibility remain explicit,
with no claimed test independence and no access to sealed material.

The collection contract is
`data/experiments/next-behaviour-v2/CONTRACT.md`. Qualified frames supply identical,
frames-only annotation packets, with context locked before future inspection.
Reader event objects, candidate-selection reasons and prior labels are omitted.
Independent admission/packet review precedes annotation reliance, and support is
recounted before fitting. The model and its support/performance gates stay fixed.

Outcome audits preserve unknown cause at bonus-max-HP transitions: the pt2-12
500/500 to 250/250 change does not establish the shared stream's claimed 250
damage. Raw proposals stay intact and that claim is excluded from damage/reward
supervision. An event's `after` value is an evidence reading, not necessarily a
value displayed at occurrence `t_to`; later confirmation before `known_at` does
not by itself contradict the occurrence interval.

The completed tranche uses the following frozen selection and annotation contract.

A separate packet producer freezes the candidate IDs and input fingerprints before
labelling. For tranche 2, exclude overlap with every prior purpose `[t-5,t+5]`
evidence footprint, including touching endpoints, as well as pre-round waits. The
frozen inventory supplies 12 windows per creator under this stronger exclusion;
retain it without resampling. Retain five seconds of preceding context and five
seconds of outcome in valid format-5
own-play segments with no hard cut, and decision spacing at least 15 seconds per
source. Inventory eligible candidates first; if a creator cannot supply 12, report
the shortfall rather than relaxing spacing, reusing old examples or sourcing more.
Use the existing context-only packet producer after checking its format-5 clock:
events enter context only when `known_at <= t`, with occurrence overlap, and no
segment-ending or future-derived field is serialized. Shared immutable inputs go
to both passes. Freeze all contexts before separate outcome release; no outcome
may revise a context judgment. Inspect all supplied 10 Hz scene cells and HUD
strips; use native frames for ambiguous evidence, and report what stays illegible.

Pre-round screening belongs to the producer, never either annotator. Before
selecting candidates or inspecting their cue mix, scan the two permitted sources'
own-play segments on a fixed 1 Hz native-frame grid. A positive cue is legible
UI explicitly identifying round preparation or a countdown to the round/objective
opening. Record the exact wording and native cue-frame path; a spawn room, closed
barrier, stationary hero, generic match clock or respawn countdown alone is not
proof. Inspect adjacent retained 10 Hz native frames where the cue changes or is
ambiguous. Record confirmed spans and unresolved pre-round transitions separately
in a private producer file, then freeze it before selection. Expand each exclusion
by **1.0 second at both ends**, clipped to the source; reject any candidate whose
full `[t-5,t+5]` evidence window overlaps it. The margin is conservative screening,
not measured transition precision. Report candidate counts before and after each
exclusion and the sampled-screening limitation. No cue found does not prove active
play; annotators may still mark pre-round or unknown, without replacements chosen
after labels are seen. No automatic oversampling is authorized.

Sample a reproducible mix of ordinary play and combat/traversal/recovery cues;
keep cue metadata private from annotators, do not turn it into purpose, and report
missing strata. The vocabulary stays engage / disengage / reposition / search /
idle plus unknown or several acceptable; separate observed actions, inferred
purpose, actor eligibility and label observability. Do not infer damage or healing
from unknown-cause HP changes. Target identity/geometry stays optional and unknown
where unsupported; box-audit progress is not a gate for this tranche.

The lead assigns a fresh-context Opus primary and a fresh-context Astra independent
pass in existing panes; neither sees previous labels, audits, selector cues or
other-pass output. The separate producer owns packet construction, and Codex owns
comparison and acceptance. Report exact preferred-label agreement on jointly
observable contexts, acceptable-set overlap separately, usability and actor-state
agreement, unknown rates, per-creator/class coverage and each disagreement against
native evidence. Retain disagreements; do not majority-vote them into certainty.
Deliver an adjudicated label manifest with inclusion/exclusion reasons and a
recommendation on which distinctions can support training. Freeze that decision
before any later fit specification; no head fit or additional tranche follows
automatically. The box support floor stays unchanged and no box tranche is started
by this decision. The single-charge no-use probe remains separate follow-up work.

```mermaid
flowchart TD
  A[Audited demonstration labels] --> B[Imitation v0]
  V[Audited HUD events and causal frames] --> P[B0 offline event predictor]
  P -. representation and sequence evidence .-> B
  B --> C[Own-play corrections and retraining]
  C --> B
  R[Repeatable episodes and audited rewards] --> D[Bounded range RL]
  B --> D
  S[Synchronized pad video and executable anchors] --> E[Learned targets and movement]
  B --> E
  B --> F[AI-only tactical evaluation and learning]
  E --> F
  G[AI-only guard, resets and match outcomes] --> F
  D -. RL experience informs later experiments .-> F
```

Codex owns the learning specification, curation criteria and reward/evaluation
design. Claude owns dispatch, integration and Linear, assigning implementation
to the existing dataset, HUD and controller owners or a named training owner.
Existing dependencies include VUH-1306 (events), VUH-1309 (paired recording),
VUH-1310 (AI-only lobby), VUH-1314 (tracks) and VUH-1315 (observed option status).
Milestone issues are A VUH-1306/VUH-1319, B VUH-1311, C VUH-1320, D VUH-1321,
E VUH-1322 and F VUH-1323. The live loop records pad state per tick in the loader's
format; the measured frame/input offset remains VUH-1309's acceptance gap.
This roadmap defines acceptance; Linear remains the record of assignment and
completion. James is not required to supply inputs or hand-label at volume.

### Reward contract before reinforcement learning

Imitation learns reviewed choices without a reward function. RL learns from the
agent's own actions and subsequent outcomes; downloaded videos alone do not
provide an interactive training environment. Reward design is a current design
task, while RL execution remains gated.

| Task | Primary objective | Supporting signals and limits |
|---|---|---|
| Bounded range encounter | Confirmed designated-target completion; terminal outcomes are completed, timeout, interrupted and lost-range | Small elapsed-time cost; optional validated outgoing damage contribution. Target identity needs tracks plus associated kill-feed evidence; aggregate KOs alone cannot identify which target died. No combat-death or damage-taken reward is available here. |
| Swing/navigation skill | Reach a specified visible destination or region | Time, resource use and observed collision/fall failures. Do not reward simply pressing swing, travelling far or staying airborne. |
| AI-only match | Team victory and verified objective progress | Combat contributions and avoidable death may support learning only if measured and shown not to encourage kill chasing or hiding. A useful trade ending in death is not automatically a bad decision. |

Range bots do not deal damage, and Practice Settings offers no fighting-bot
option. D therefore tests attack execution/completion, not survival or tactical
retreat. Expert footage can supervise observable retreat decisions offline, but
learning their consequences from our own play and testing their usefulness needs
F. A lost-range termination records why control stops; it is not a claimed death
or a successful disengagement. Reader failure remains an interruption/unknown,
not a fabricated adverse gameplay outcome.

Before an RL run, record the exact formula, weights, discount, episode limits and
reader versions with the experiment. The first experiment below supplies proposed
defaults, not validated weights; tune on development episodes, then freeze the
evaluation and its success criteria.
Optional shaping must have a bounded contribution so damage farming or repeated
partial progress cannot outweigh the actual task. Scoreboard checks are a means
of measurement, not an action deserving positive reward.

Audit range reward extraction against hand-checked recordings of completion,
timeout, interruption, lost-range and reset; add combat death and damage taken
only in an environment where those occur. Each reward component retains its
observation source and validity; unknown does not become zero. Exclude episodes or learning
targets whose required outcome is unobservable. Treat a capture/lobby interruption
as an interruption rather than inventing a gameplay death. Check that repeated
scoreboard reads cannot award the same KO twice, resets cannot produce reward
from counter jumps, and healing/shield decay cannot masquerade as damage.

There is no verified in-range reset, and bot respawn time is unmeasured. A live
run stranded the agent off the platform and needed full lobby re-entry, about
two minutes with a script whose steering still needs correction. VUH-1319's
episode/collection pilot depends on the live loop, tracks and observed option
status; it must measure recovery costs rather than assume cheap resets.

Run that small collection pilot before committing to RL scale: measure usable
episodes per hour, reset time, invalid-data rate, inference latency and training
throughput. This is one real game instance, not a simulator supplying thousands
of parallel matches; rented GPUs accelerate training, not gameplay collection.
Masked PPO is the first-experiment choice below, contingent on a viable collection
budget and trainable action interface. Range option learning starts with the motor controller frozen;
learning sticks and camera is a separate experiment under E.

Each comparison keeps the scenario set, trial budget, perception and executor
fixed, retains failures, and reports every applicable terminal-outcome count and
elapsed time as well as return. In custom games, also report deaths, wins and
objective outcomes.
Claim improvement only at the tested scope; inconclusive results call for more
evidence, not promotion of the highest-return checkpoint. Keep the preceding
working policy available for rollback. Training stays local first, with the
approved initial $100 cloud allowance governed by the compute section below.

### First RL experiment: implementation plan

The detailed option-PPO design below is a historical proposal, not implemented RL
or the current action contract. September 22's event reframe supersedes its fixed
Idle/Search/Engage vocabulary and encoder/history assumptions. Before implementing
D, bind the actual competent imitation checkpoint, reviewed executable outputs
and measured collection budget; retain the reward/reset/credit audit below.
VUH-1325's original input findings are fixed and independently accepted. There is
no blanket freeze on unchanged reviewed paths; changed live boundaries still
require review and the single desktop driver. No alternative launch path bypasses
those constraints. Algorithm selection remains contingent on measured throughput.

The concrete goal is to improve completion of one bounded, designated-target
range encounter relative to the same imitation checkpoint and controller.
The first experiment does not optimize match wins, enemy selection or stick
trajectories. Those are E/F extensions, not capabilities hidden inside the name RL.

#### Policy, observations and actions

Reuse the policy lane's frozen DINO ViT-S/16 encoder, recorded normalization and
causal five-second history. The existing two-layer GRU provides the starting
temporal representation. Add a categorical action head and a scalar value head
(predicted remaining return); train these and the GRU, initially leaving the
visual encoder, perception, target selector and motor controller fixed. Reuse
the audited observation builder; neither cache lookup nor outcome features may
leak frames or events later than the decision time. Add remaining episode time
and observed option status with explicit known/missing bits and a versioned
feature layout. Live event features stay absent until their producer is connected.

Warm-start from an imitation checkpoint validated on the same patch, normal
cooldown regime and executable action vocabulary. The current cooldown-free
scripted-brain distillation is not that checkpoint. Expert tactical labels can
improve initialization, but a range-competent own-play imitation checkpoint is
sufficient for D; D need not wait for full expert game-sense annotation.

The initial candidate vocabulary is `Idle`, `Search`, `Engage`, `Pull`,
`WebStrike`, and the verified burst `Combo`. Only actions with measured executable
preconditions enter the experiment. The fixed selector supplies the designated
target, and an episode never silently switches that identity after occlusion or
respawn. `SwingTo` enters E once anchors are executable; menu/navigation buttons
never enter any learned action space.

At an eligible option boundary, mask invalid actions before sampling, and retain
that exact mask in the rollout. Use the same mask when evaluating the action's
old/new probabilities during training. A single legal choice supplies no actor
learning signal. Neutral `Idle` must actually remain neutral: the existing live
chooser treats idle-like labels as scripted fallback, which cannot be reused as
RL action semantics. Preserve hard screen/focus/input guards independently of
the model. Action masking is a policy constraint, not the input-safety boundary.
See the [action-masking study](https://arxiv.org/abs/2006.14171).

An RL transition starts when the model's sampled option is accepted, and ends
at its observed completion/failure, next eligible choice, or episode end. The
reflex loop keeps running during it. Repeated hold ticks are not new independent
actions. Accumulate their reward and elapsed time into the originating option.
Log proposal, actual executed option, target, legal mask, behavior log-probability,
value estimate, observation times, duration, outcome evidence, policy version
and whether the gate forced/fell back. A rejected proposal must not be trained
as though it executed. Exclude forced-only decisions from actor loss; where
intervention breaks attribution, mark the transition invalid. Report the share
of actual model choices: a policy permanently bypassed by rules cannot learn.

#### Episode and reward v0

VUH-1319 supplies the episode boundary. A proposed initial task is **defeat the
designated visible bot within 20 seconds**, beginning from an observed scenario
bin (location/view, distance band, full target health, own resources, patch and
normal cooldowns). Start timing only after readiness is verified. If full target
health or identity cannot be established, do not assert a comparable start.
The lead reports an observable full-health cue in this arena: an undamaged bot
shows its name without a health bar; the bar appears after first damage. Validate
that cue on the visible designated bot during the collection pilot. A missing
bar alone (for example, with an unreadable name or occluded bot) is not proof of
full health.
The lead reports four five-minute baselines with 21, approximately 4, 20 and 0
KOs: one stalls looking down beside a close bot, another starts on a bot-free
ring. Pooling these as noise around a mean would hide start-state and recovery
failures. A bot-free start fails readiness before the episode; getting stuck
after a verified start remains a real task failure/timeout. Preserve setup
failure counts separately, and never discard difficult valid starts afterward.
Respawn/reset is an observed procedure, not an API that teleports or reseeds the
game. Record reset time separately. Menu re-entry belongs to the guarded supervisor;
it is never an exploratory policy action or part of the learning return.

The lead reports a burst kills these bots in roughly 2–3 seconds, with about
seven seconds of dead time after each KO in the baseline. The first useful
learning signal is therefore expected around approach, acquisition/reacquisition
and recovery from stalled options, rather than a long fight. Measure these
durations separately from burst execution. Episode v0 starts with a verified
visible target: post-KO search/reset outside that episode is collection overhead,
not behavior its reward can improve. Learning the next-target acquisition cycle
requires a separately defined continuation task; do not claim it from v0 results.

Proposed first-experiment reward, once per episode event:

```text
r = +1.00 on confirmed designated-target completion
    -0.25 on the task's 20-second timeout
    -0.20 * delta_gameplay_seconds / 20 on each transition
```

Completion at 5 seconds totals +0.95; at 20 seconds +0.80; timeout totals -0.45.
Each interval contributes elapsed time once, capped at the task horizon; do not
subtract cumulative elapsed time again on every tick.
Success by the deadline takes precedence over timeout; never award both. The
finite task uses discount gamma=1, and remaining time is observable. There is
no damage shaping in reward v0: this avoids depending on damage attribution or
rewarding repeatable damage without task completion. Completion requires track
identity plus associated kill-feed evidence, backed by scoreboard deltas; an
aggregate KO alone is insufficient. Credit a verified delayed display event to
the encounter that caused it, before starting another target/reset. An event
whose occurrence interval straddles the deadline cannot prove a by-deadline
success; preserve that uncertainty rather than backdating its display timestamp.

Runtime stop reasons and learning terminals are different. Completion and the
task deadline are genuine terminals. Capture loss, a guard stop, operator stop,
or ambiguous lost-range is an interruption, not a death/timeout penalty. Stop
input regardless; exclude incomplete outcome-dependent targets. A clearly
observed navigation failure may become a separately specified terminal in a
later task, but must not be inferred from the HUD disappearing. A collector
batch cut with a valid next observation can bootstrap its value; a genuine
terminal cannot. Do not bootstrap from an unknown/black next frame.
This distinction follows [Gymnasium's time-limit guidance](https://gymnasium.farama.org/tutorials/gymnasium_basics/handling_time_limits/).

Keep every interruption in evaluation's attempted-episode denominator and report
its reason. Otherwise a candidate could appear better by generating unscorable
runs. Any input-safety violation stops the experiment; reward tuning cannot
authorize unsafe behavior. Low-HP/death/escape rewards wait for AI opponents
that actually fight back.

#### Update cycle and algorithm

The first algorithm is **masked PPO with a value baseline**, initialized by
imitation. It alternates collection under one fixed policy version with a few
optimization passes on that fresh batch. We choose it for the categorical option
interface and reuse of actor logits, not because it is proven optimal for this
game or sample budget. Older expert videos have no behavior probabilities or
exact executed options; they remain imitation/representation data, not pretend
PPO trajectories. Algorithm basis: [PPO](https://arxiv.org/abs/1707.06347).

```mermaid
flowchart LR
  C[Accepted imitation checkpoint] --> P[Masked option policy]
  P --> G[Independent input guard and fixed controller]
  G --> E[One bounded range episode]
  E --> R[Audited reward and attributed transitions]
  R --> U[Local PPO actor and value update]
  U --> V[Offline checks and fixed gameplay evaluation]
  V -->|accepted candidate| P
  V -->|regression or uncertainty| K[Keep preceding checkpoint]
```

The trainer extends the existing MLX head rather than adding a model server.
Before using game rewards, check the clipped objective and value targets on
small deterministic examples and a toy task; compare numerical results with
an independent CPU calculation. The contract requires masked probabilities to
sum to one, zero probability for invalid actions, initial old/new probability
ratios of one, correct terminal targets, and exactly-once success reward.
Then verify a recorded rollout can reproduce its observations/actions/returns.
These checks prove the learning machinery, not Spider-Man performance.

Initial development defaults: PPO clip 0.2, Adam learning rate 0.0003, four
optimization epochs per fresh batch, value-loss weight 0.5 and entropy weight
0.01. Use complete finite-episode returns minus the value baseline for the
first advantage estimator; this avoids adding a second time-discount scheme
while option durations vary. Normalize advantages only when variance is nonzero.
Track policy KL and stop batch updates above a proposed 0.02 threshold; this is
a diagnostic bound, not a gameplay-safety guarantee. Record all defaults with
the checkpoint and change them only on development data.

Freeze the behavior policy for collection, keep exact old log-probabilities,
and recompute model outputs from complete causal windows for training. Deploy a
candidate only between episodes, with the pad released; never update weights
while that episode is still generating experience. Check that perception/option
versions match before consuming rollouts. Historical rollouts can be retained
for audit or separately justified imitation, but are not endlessly reused as
fresh on-policy data.

#### First experiment budget and promotion

These are proposed bounded experiment sizes, not a claim that they suffice to
learn or a lifting of the live freeze:

1. **Collection feasibility (VUH-1319):** ten observed episodes, at most 30 minutes
   including resets. Hand-check every terminal and every assigned reward; any
   false success blocks training. Report valid episodes/hour, reset distribution,
   interruptions, genuine policy-choice count and inference latency. If the cap
   prevents ten episodes, report that result rather than assuming a faster reset.
2. **Learning smoke experiment (VUH-1321):** at most 40 valid training episodes,
   with batches containing at least eight completed episodes and 64 eligible
   model choices. Allow at most four game-hours including pilot, collection,
   resets and evaluation. If those minima do not fit, stop and revise the
   collection/task design; do not run an unbounded job to fill a buffer.
3. **Evaluation:** initially 20 attempts each for the starting checkpoint and the
   frozen candidate, over a predeclared mix of starts/distance bins withheld from
   training. Interleave their order where practical, restore the same resources,
   retain invalid attempts, and include the fixed scripted controller baseline.
   Test the deployment action-selection rule, not only stochastic training rollouts.
   Report completion fraction, timeout/interruption counts, restricted completion
   time (unsuccessful attempts count as the deadline), and reward components.

Twenty attempts per policy are a smoke comparison, not a generalization promise.
Select candidates on development scenarios; keep a final evaluation set out of
checkpoint selection. Predeclare success rate as the primary metric and report
uncertainty. Promote only with evidence of improvement over the starting policy,
no input-safety violation and no increased dependence on scripted fallback or
unscorable stops. An inconclusive interval means more evaluation or no promotion,
not selecting the best-looking run. If baseline success is already saturated,
predeclare a time-to-completion objective or a harder safe task before training;
do not change the metric after seeing results.

Measure cost from the pilot: collection hours = required attempts / observed
attempts per hour, including resets and rejection. One game instance supplies
experience at real-time speed. The Mac performs training locally, niced, with
the small head/encoder workload measured separately from inference. Runtime
placement must pass PC frame-time and end-to-end latency checks; the known
Wi-Fi tail rules out assuming a reliable Mac round trip. Cloud rental uses the
existing initial $100 allowance only when measured trainer throughput justifies
it; it does not buy more game instances or faster environment time. No rentals
or live experiments are started by this document change.

If the pilot cannot supply useful choices/rewards, fix observability, resets or
the task first. If PPO works mechanically but consumes too many episodes, compare
a discrete replay-based learner under the same measured environment-hour budget;
that is a deliberate second experiment, not a parallel algorithm sweep. If no
improvement survives evaluation, retain imitation plus reviewed corrections.

#### Expansion and patch acceptance

E adds one capability at a time: target choice over validated tracks, then spatial
destination/anchor choice, then motor learning from synchronized inputs. Each
gets its own task/outcomes before joint optimization. F begins with a verified
AI-only lobby and opponent behavior, then controlled fights, then objective play
and complete matches. A starting full-match objective is terminal team win +1,
loss -1, draw 0; objective-progress shaping is added only after its reader and
anti-farming behavior are audited. These are later task proposals, not signals
the current range provides.

The existing brain gate hard-codes low-HP retreat. F must separate such tactical
heuristics from non-negotiable screen/input guards: while a rule always chooses
retreat, the policy cannot claim to learn when retreat is appropriate. Expand
the learner's authority only for the tactical behavior being evaluated; keep
input authorization and neutralization outside the learned policy.

Every source, rollout, baseline and checkpoint records patch plus cooldown regime
(VUH-1324). Acceptance is per patch. After a patch, suspend promotion and
unattended learning until the affected HUD layouts/cast readers, cooldown/charge
behavior, damage/KO attribution, ability preconditions, option completion and
combo timing are rechecked; remeasure aim/movement if their response changes.
Rerun the reward audit and a scripted baseline, then evaluate the frozen policy
before reuse. Old footage remains tagged; mixing patches is an explicit transfer
experiment. Unknown patch stays unknown, and observed cooldowns are a drift
signal rather than unique proof of patch identity.

Claude owns staffing/integration through the existing milestone issues. The
policy owner implements the actor/value update and rollout probabilities;
episode/controller owners supply resets, option status and safe collection;
HUD owners supply auditable outcome evidence; Codex owns this contract and the
independent acceptance review. The completion of VUH-1321 means a reproducible
learning comparison and retained checkpoint or honest negative result, not just
an RL library installed or a loss curve going down.

## Data and labels

### Cross-patch pretraining with explicit kit context

Older demonstrations are eligible pretraining sources, not discarded because of
age. Pretrain on accepted sources across patches, then fine-tune and evaluate on
the verified current patch. This can reuse routes, camera motion and decision
examples; it does not assume tactics are patch-invariant. Damage, movement,
cancel windows, team-ups, other heroes and map changes can alter good decisions
as well as cooldowns. A patch token alone cannot repair an unrepresented rule.

Each sample carries a versioned `kit_context`: patch identity (or unknown),
cooldown regime, per-ability cooldown/recharge seconds and maximum charges,
team-up variant, plus explicit known/unknown masks. Keep measured current availability in the
observation separate from these kit limits. Record evidence and provenance with
each value; missing means unknown, never zero. Known discrete mechanics changes
use named rule flags where the supervised task depends on them; otherwise exclude
that task's incompatible labels rather than invent a complete historical simulator.
Patch identity is categorical metadata, not a numeric chronology to interpolate.

Team-up cooldown fingerprints require **ability identity**. The official
[Version 20260911 balance note](https://www.marvelrivals.com/20260908/41525_1313334.html)
changes Peni Parker's **Parker Power-Up** from 15 to 10 seconds; the
[hero reference](https://www.marvelrivals.com/m/20241123/41360_1195680.html)
lists **Symbiote Bond** separately at 15 seconds. Native train-frame spot checks
match the latter's distinct radial-burst icon: Day `003309.jpg` and Req
`000828.jpg` under their respective `data/experiments/b0/frames/<clip-id>/`
directories. Day also shows its black-spike effect. Thus generic `teamup=15`
does not contradict the date-derived patch labels on these sources. The checks
identify those windows, not every segment: retain unknown elsewhere until
verified, allow variant changes, and never apply Parker's 10-second rule to all
team-up events. Dated patch notes take precedence over stale numerical entries
on the general hero page.

The April-May uploads' measured two-second uppercut does not uniquely identify
their patch or complete kit. Keep their unresolved fields unknown. They become
eligible for audited tasks supported by their pixels and labels, not automatically
accepted training data. Historical casts remain historical facts; old combo
timings and successful cancels are not relabelled as current-patch executable
actions. Cooldown-free examples can support motion/visual pretraining while
remaining excluded from normal-cooldown timing supervision. Suitability, hero,
event and motion-label gates still apply separately.

Kit features must be available at deployment: use independently established kit
configuration or causally observed evidence. Do not turn a whole video's future
countdowns into a time-t input or derive model input normalization from held-out
footage. Offline measurements may establish audited source provenance and labels;
their use as policy inputs requires the same availability contract as other features.

Maintain a separate accepted pretraining source list with explicit allowed patch
and regime combinations. The loader's default refusal to mix stays intact.
Its iterator has explicit mixing flags, but `load_split` currently enforces one
patch/regime: this experiment needs an owned interface change, not merely a flag.
No split, source status or checkpoint is promoted by this design decision.
Whole match/session identity and duplicate checks span all stages, including
pretraining; development-held-out and sealed test sessions supply no fitting
examples, even unlabelled ones. Unresolved-overlap uploads remain excluded.

Compare current-only training with older-source pretraining followed by the same
current-patch fine-tuning on identical current-patch development folds. Predeclare
the sampling balance and compute budget, report per-task/session results and
negative transfer, and retain the simpler baseline if the added data does not
help. Each fold's held-out session stays out of every pretraining stage. Sealed
tests are used only after model selection. Record the context schema, source
patches and current target patch in the checkpoint. The first comparison reuses
audited footage already held; additional older downloads follow a demonstrated
coverage need, not an unrestricted archive expansion.

RL still requires the live-patch legality, controller and reward checks. It may
adapt a valid policy within that environment; it cannot be assumed to discover
or fix changed readers, invalid actions, missing mechanics or incorrect rewards.

### Source fidelity: investigate native replay before expanding downloads

The game's replay system is a candidate source, not a verified acquisition path.
[Replay research](lanes/replay-research.md) finds community support for shared IDs,
player POV and cooldown visibility, plus a first-party outline-setting bug fix
consistent with viewer-side rendering. These are reasons to test the route,
not confirmation of full HUD fidelity, Enemy Color behavior or expert access.
No publicly posted Day/Req replay IDs were found; absence from that search is not
proof that none exist. Replay expiry and patch compatibility remain constraints.
Claude owns replay feasibility and the safe navigation investigation. James may
optionally perform the in-client check, but his availability is not a prerequisite
for existing-footage annotation, auxiliary pretraining or range development.
An agent-operated replay visit requires its own mapped controls and authorization
proofs; the current range controller must not be sent there. Further Twitch
expansion is parked because the proposed eligible source pair is unavailable.
Existing inspected footage remains useful for narration, event-reader testing,
audited annotation and the auxiliary pretraining probe.

Separate **viewer capability** from **expert-source availability**. An existing
accessible match can test the former without proving that Day/Req matches are
obtainable. Record the client build, replay match ID/date/patch, POV mode, relevant
settings and a short native capture with HUD. Prioritize locked player POV, visible
HP/ammo/cooldowns/ult and outline behavior; compare timing at normal playback speed.
Pad-only navigation, frame stepping and the built-in clip exporter are conveniences,
not prerequisites if manual navigation and our existing screen capture work. Do
not create or enter a human match to test replay availability.

The lead's channel check reports a 1080p60 maximum for the inspected Req YouTube
uploads. That rules out a higher-resolution rendition of those uploads, not all
fidelity improvement: bitrate, re-encoding and original capture quality can differ
at the same dimensions. Keep source-quality claims tied to inspected pixels.

Replay adoption requires an accessible expert match ID with patch/session
provenance; recorded-player POV and HUD; checked camera, cooldown and event timing
at normal playback speed; and native capture without streamer overlays. Test
whether enemy colours follow our settings and score target detection on replay
frames. The range green finder's 82/83 precision/recall does not transfer by
assertion. A spectator reconstruction may differ from the original player's
camera, visibility or HUD; identify those differences before treating it as an
expert's observation. Native pixels cannot reveal hidden intent or unlogged inputs.

If these checks pass, prioritize replay-derived demonstrations and retain one
match/session identity across replay and VOD versions to prevent split leakage.
Merge the live/demo perception paths only after a measured entity/observation
contract supports it. Otherwise retain the two-domain design and document the
specific replay limitation. Acceptance of range input guards does not authorize
an unattended replay-menu visit or a new controller launch surface; the viewer
remains unmapped until separately verified.

### Expert practice-range segments

Search the existing development broadcasts for Spider-Man warm-ups and drills.
This is a mechanics source for target order, acquisition, combo execution and swing
routes, with the same arena geometry as our runtime. It reduces the map and task
gap; compression, overlays, outline colours, camera settings, input device, patch
and cooldown settings still differ. It supplies neither exact pad inputs nor
tactical decisions against opponents who fight back.

The first sourcing pass scans only the first hour of development broadcasts
Day `2879354299` and Req `2873352801`, using a low-bitrate rendition near 1 fps.
Calibrate the existing range-banner matcher on streamer pixels before relying on
it; it proposes spans, not training labels. Inspect native frames to confirm the
game, arena and controlled hero, then retain at most one three-minute candidate
per creator at 1080p60, with source timestamps and inspection-only provenance.
If access or banner visibility prevents the scan, report that limitation; a
failed matcher does not prove a broadcast contains no range play. Expansion
follows inspection of this pair, not an automatic full-archive download.

The first-hour scan is complete: 3,600 sampled frames per broadcast. Its local
`data/demos/vods/range-scan/handback.md` records only a brief Req opening range
visit, retained as a 15-second native clip. Independently inspected +1 s and
+2 s stills confirm controlled Spider-Man in the range followed by a Match Found
overlay; the worker reports loading by +6 s. This is accepted as sourcing and
banner-calibration evidence, not a sustained mechanics demonstration or accepted
training window. Cooldown regime stays unknown. Day has no confirmed candidate;
its strongest matcher result is inspected match footage, not proof of no range
play elsewhere. Cross-rendition time zero differs, so scan indices cannot label
native-frame events without alignment. The bounded pass is stopped with no
training promotion or further acquisition authorized by this result.

All segments retain their parent broadcast's split and patch provenance; new
range minutes from a training broadcast are not an independent validation session.
Sealed broadcasts remain unopened, and uploads with unresolved overlap remain
excluded. Record cooldown evidence per segment and ability: an observed countdown
proves that slot has a cooldown, not that every practice override is disabled.
Missing countdowns alone leave the regime unknown. Demonstrated cooldown-free
drills may teach motion and visible sequence order, but cannot establish normal
resource constraints or inter-cast timing from the current event extractor.
Inspect drill suitability instead of treating all warm-up behavior as exemplary.

A detector trained on our range frames is a candidate transfer experiment. Our
green finder supplies weak proposals, not perfect labels; audit them and measure
the detector on separately annotated expert range pixels before trusting boxes.
The enemy nearest the crosshair remains a target hypothesis, especially during
camera movement or ability lock-on. Camera and swing labels retain the camera
probe's observability and held-out error requirements.

| Source | Evidence provided | Missing or uncertain |
|---|---|---|
| Expert VODs | Screen history, visible HUD transitions, tactical examples | Exact inputs, private communications, intent, hidden game state |
| James's synchronized gameplay | Screens and timestamped human inputs | Effective game response must still be checked |
| Scripted pad recordings | Exact commanded pad inputs and frames; initial paired data for a later inverse-dynamics experiment | Commands may be ignored; scripted actions are not expert demonstrations |
| Human annotations | Target/intent judgments, observable outcomes | Ambiguous decisions require unknown labels or multiple acceptable choices |

Expert VODs and James's keyboard/mouse demonstrations are complementary first-class
sources. VOD acquisition and tactical training can proceed independently; paired
execution imitation uses the human recorder's native controls and reviewed alignment.
The absence of exact inputs in a VOD never authorizes invented motor labels.

All our range recordings preceding the real-cooldown baseline have Practice
Settings' default **No Ability Cooldown ON**: infinite ammo, no cooldown numbers
and an observed ult refill around 3.5 seconds. Their dataset provenance must
identify this cooldown-free regime. They can support execution/visual pipeline
work, but cannot establish normal cooldown timing, resource management or legal
combo cadence in matches. The upcoming baseline requires the setting OFF and
observed cooldown/ammo behavior checked before recording. Keep the regimes
separate in training and evaluation; do not silently pool them. For third-party
range guides, settings remain unknown unless source evidence establishes them;
our local setting does not prove the creator used it. The HUD lane identifies
cooldown-free behavior in the inspected Day pull lesson and FFAme Stack windows:
across 9,510 frames neither supplies countdown/charge evidence of casts.
Their lockout flashes cannot establish inter-cast timing. Retain their narrated
technique order and usage advice, with match footage or our normal-cooldown
recordings supplying measured timing. Do not generalize these two inspected
windows' regime to every segment of every guide.

Keep originals under gitignored `data/demos/`, with source URL, VOD ID, creator,
retrieval date, source start/end, resolution, frame timing, hero, visible patch/map
evidence, overlays and splits in a small manifest. Preserve source timestamps across
trims. HLS cuts can carry keyframe preroll; validate actual frames before claiming
frame-accurate alignment. Archive completed broadcasts preferentially; growing live
VODs have changing durations. Do not put third-party media in git or upload it to
Linear. Technical accessibility is not a verified training or redistribution licence.
Acquisition feasibility records distinguish tested access from unresolved usage terms.

Curate contiguous engagements with preceding context and aftermath, including failed
attacks, retreats, no-engage decisions and recovery. Reject menus, other heroes,
spectator views, edits and obscured HUD regions from labels that depend on them.
Do not select only kills or highlight compilations.

Retention, observability and suitability for imitation are separate decisions.
An accurately labelled expert mistake is not automatically a positive action
example. Before policy training, review demonstrated choices for suitability:
accepted examples may enter the action-imitation loss; rejected or unresolved
choices remain available for failure analysis but are excluded from that loss.
This is an acceptance requirement, not an implemented training filter. Codex owns
the review criteria; the dataset/training owner implements the representation.
Model-assisted quality judgments need an audit and do not establish optimality.

Review the decision and its context, not simply whether a death follows. A useful
trade may end in death, and a good escape attempt can follow an earlier mistake.
Preserve successful recovery and retreat examples from losing encounters; do not
label an entire life or match bad. Conversely, survival or a kill does not prove
a good choice. Outcome evidence may guide curation but never becomes a future
policy input. Retaining a failure does not itself teach avoidance: that requires
a justified corrected action, a reviewed preference, or a later outcome-learning
objective. When no better action is supported, keep it unknown rather than invent
a counterfactual target label.

HUD transitions are **inferred event labels**, not ground-truth button presses.
Cooldown changes may lag input; charges regenerate; death, reset, hero changes and
OCR flicker can mimic transitions. Retain evidence and uncertainty. Unlimited web
ammo in the range means an unchanged counter cannot establish whether a shot fired.
Team-up shield decay can lower displayed HP without damage taken; the event extractor
distinguishes `shield_decayed` from `hp_lost`. Low-health red vignettes can defeat HP
digit reads even when the bar remains visible; preserve unknowns and reader provenance.
Never bridge an unreadable interval as though a precise event time were observed.
A red/unavailable ability icon can also mean temporary animation or wall-climb
lockout; it is not sufficient evidence of use. The aligned Req rerun finds
`swing` use proposals during attacks/climbing with charge retained, plus visible
Get Over Here/uppercut changes absent from the supplied events. Treat the event
stream as proposals needing class-specific precision/recall checks. Net HP change
is not damage taken: at +48.1/+48.2/+48.3 the native HUD reads 250/195/220 while the
interval event reports loss 30. Damage and healing can cancel within an interval.
Validate VOD HUD geometry separately: resolution scaling alone may not align a
mouse/keyboard HUD with our controller HUD, and streamer overlays can occlude it.

Each tactical example separates observation history ending at decision time from
the action label and subsequent outcome. Future frames establish separately named
outcome or future-action labels, not a revision to the locked current-purpose label,
and are never inputs at the earlier decision time. Later events and commentary are
not evidence that the player knew them earlier. Split by entire recording/session before extracting
windows; nearby frames and mirrored uploads cannot cross train/evaluation boundaries.

### Annotation ownership and pilot

Codex co-lead owns the initial annotation specification and one independent pass;
the tab-1 lead assigns the second annotator. Model-assisted labels are proposals,
not human ground truth. James is not a required volume annotator. The HUD lane
supplies observed transitions with evidence intervals; annotators infer tactical
choices only where the visible evidence supports them. A human spot-check can
adjudicate important disagreements, but unreviewed disagreements remain unknown.

An uppercut use is not `Combo`, a web shot is not `burst`, and a swing charge spent
does not identify an anchor or prove the `SwingTo` intent. RB-associated cooldown
evidence plus a visible tracer and travel can support pull/strike labels, but a
missing tracer is not proof of untagged. Burst requires the observed sequence,
not one ammo decrement. Record primitive events separately from tactical options.

Pilot format: six decision windows from the inspected samples, four Req and two
Day, including a spectator negative. Each carries source ID, decision timestamp,
the preceding five seconds (or an explicit truncated-context flag), and a separate
next-five-seconds outcome segment. Both annotators first label the context alone:
visible situation, candidate action(s), target bbox in original pixels or unknown,
evidence timestamps, uncertainty and unusable reason. Outcome review is a separate
field, not an input to a hindsight-corrected tactical label. These six examples test
label observability and the contract, not policy quality or a training data budget.
The loader owner implements the representation; this document does not add a
second competing schema. Compare agreement and evidence, retain ambiguity, and do
not treat two models agreeing as independent proof of correctness.

The six-window comparison in local `data/demos/annotations/COMPARISON.md` finds
usable/unusable agreement in 6/6 windows, exact option-set agreement in only 1/6
(the spectator negative), overlap in 4/6, and disjoint options in 1/6. Two outcome
narratives contradict. The sole shared target box has about 0.87 IoU. This does
not pass the gate for scaling tactical labels. The passes used different sampling
rates (1 versus 10 Hz), and the comparison agent did not inspect media: protocol
differences are a plausible cause, not an adjudication of the conflicting facts.

#### Aligned two-window rerun

The aligned rerun covers only Req +30 and +45. Preserve the original passes.
Both annotators use `data/demos/samples/reqmr-2873352801-1920.mp4` and the
frozen event stream at
`data/demos/annotations/rerun-inputs/reqmr-2873352801-1920.events.jsonl`, copied
from `data/demos/events/reqmr-2873352801-1920.jsonl`. This is the MK-layout stream,
not the older `.events.jsonl` beside the sample video.

1. Inspect context from t−5 through t at **10 Hz**, including the decision frame
   (51 samples), with native-resolution HP/ammo/ability/ult strips and access to
   the original frame. Record actual source PTS; choose the frame at or before
   each requested time. Only events confirmed by t are context inputs; retain
   transition intervals rather than inventing instantaneous button presses.
   Name the extraction method and frame index as well as PTS. On this verified
   60 fps source, zero-based frame n = 6i (`select='not(mod(n,6))'`) matches
   accurate seeks pixel for pixel in the Claude annotator's check; plain
   `-vf fps=10` can differ by one source frame. Codex uses decoded PTS to select
   the greatest timestamp at or before each request. Other clips need their own
   PTS check: neither a clean 60 fps grid nor the same sampling phase is assumed.
2. Derive a **per-frame visibility mask** from the event stream's segments, with
   reasons for gaps. Add observed overlay/player occlusion separately: scene,
   player and individual HUD fields can have different visibility. Do not infer
   full visibility just because a frame passes the gameplay gate. Retain the
   truncated-context flag for missing history; a visibility mask does not replace
   it. Never carry a decision across death, spectating, reset or hero change.
3. Record **tactical purpose separately from observed primitives**. Tactical
   candidates are engage (approach/continue fighting), disengage (leave danger),
   search (seek a target), reposition (non-combat rotation/setup), idle, or
   unknown/no-vocabulary-fit with a reason. These are interpretation labels for
   demonstrated behavior, not claims about the optimal next action. `get_over_here`
   is a primitive event with `target_tagged: true | false | unknown`; unknown is
   the default. Do not infer an untagged target from an unreadable tracer or map
   that unknown to a live `Pull`. Keep existing live Pull/WebStrike execution
   checks distinct. Label-to-runtime mapping is agreed before training; this
   pilot does not silently extend `agent/intents.py`.
4. Use explicit target status: visible selected target plus box, no selected
   target, or unknown whether/which target is selected. Unknown does not assert
   that a target exists. Record what is under the crosshair and whether the player,
   scene and relevant HUD fields are visible. Use outline/nameplate evidence,
   not costume colour, for team assignment; preserve unknown team and identity.
5. Save the context judgment before examining the next five seconds at the same
   rate with separate event/HUD evidence. Describe outcome observables with
   timestamps: approach, displacement, attack evidence, target association and
   damage/death evidence. Do not claim a hit or persistent target identity from
   proximity alone. Record later corrections separately, without rewriting the
   context judgment. Both passes have prior pilot exposure; this is a protocol
   repair, not a new blinded evaluation.
6. Keep the **shared stream immutable** as the authoritative record of what the
   extractor reports for its tracked channels, not as infallible gameplay truth.
   An annotator may add `observed_not_in_shared_stream` evidence with the slot,
   before/after values, source frame indices/PTS, interval and confidence. Never
   delete or silently rewrite a shared event. Flag disputed events and visibility
   boundaries separately for adjudication; unresolved disputes are excluded from
   supervision. Additions obey the same decision-time cutoff. The frozen stream
   does not track team-up use; both the coverage gap and the reported use around
   +40.8–41.0 remain explicit rather than becoming a negative label.

The HUD lane owns the requested event-name correction: the shared slot is
`get_over_here`, while icon availability transitions are `slot_unavailable` /
`slot_available`. The frozen pilot stream still uses `pull` and `ability_used` /
`ability_ready`; those legacy names do not establish an untagged pull or a cast.
Cooldown starts and charge expenditure need separate evidence. The rename is a
contract change to coordinate with the loader, not permission to rewrite the
frozen evidence or merge the live Pull/WebStrike execution checks.

The lead's media-backed adjudication finds agreement on tactical purpose in both
rerun windows: +30 engage and +45 reposition, with residual search/setup ambiguity
at +45. Selected target and persistent identity remain unknown in both. At +30,
the +34.0–34.3 frames establish close combat beside a caped, red-marked enemy;
the first part of the outcome alone cannot describe the whole five seconds.
At +45, traversal around the pillar followed by combat is supported, but identity
continuity with the group below is not. This supports the coarse purpose/primitive
split on these two examples, not reliability at scale or observability of every
candidate class. Unknown identity here does not imply all VOD target boxes are
unobservable.

Both passes independently identify missed Get Over Here cooldown starts,
availability blips misnamed as uses, the scoreboard still visible at +43.7, and
HP intervals netting damage against healing. **Scaling annotation waits on HUD
fixes and a hand-checked VOD event sample**, with class-specific precision, recall,
timing and coverage checks. Remaining unobservable distinctions become unknown or
leave the supervised label set. The loader owner owns representation changes;
shared masks must also constrain eventual training observations so annotators
cannot use history the policy will not receive.

### VOD perception and normalization

VOD target labelling is a separate perception problem. The pure-green live finder
does not transfer to arbitrary streamer outline colours; existing YOLO weights
have not been validated on this domain. The pilot uses inspected visual target
boxes, not unchecked detector pseudo-labels. Test target detection on hand-audited
VOD frames before scaling labels, and include both creators/outline settings in
evaluation so policy behavior does not depend on one highlight colour.

L3's hand-checked test on 40 frames from the two retained VOD clips rejects a
global red-colour finder: 210 proposed boxes, boxes on every frame including empty
ones, and essentially no true positives. Both creators use default red enemies,
but Spider-Man's own red suit and permanent red streamer graphics each defeat
colour-only detection. Red architecture, ability/damage effects, scoreboard panels
and defeat overlays add false positives; small, compression-smeared enemies supply
the weakest signal. More threshold tuning does not resolve that ambiguity.

The [live detector lane](lanes/l3-detector.md) reports 82% precision and 83% recall
for the chosen green outline on its hand-checked range set, with 4.4 ms inference
on a native crop on the PC. The old YOLO has about 3% recall on that same range set;
its mAP50 of 0.656 measures agreement with a substantially incorrect auto-labeller,
not trustworthy enemy detection. These range measurements do not establish VOD
accuracy. Off-the-shelf COCO person detection also fails the proposal-only bar on
the same 40 VOD frames. YOLO11 s/m at 1280/1920, with overlays masked and gameplay /
player filtering, produces only 7–12 proposed non-player boxes over 33 gameplay
frames. In the best configuration, six of seven are still the streamer's own hero
and one is a real enemy; closer inspection finds roughly 15 visible characters
across 12 frames. Neither tested size nor resolution solves the domain mismatch.
The tested off-the-shelf paths cannot supply VOD target boxes. Annotators draw the
initial small set; a thin red-versus-blue ring around a supplied box supports
enemy/ally classification in the inspected examples, with unknown retained.

That result limits the current tools, not what expert footage can teach. A detector
fine-tuned on reviewed VOD boxes is a candidate enabler for learned targeting and
relative positioning. Visible camera motion and routes are potential supervision
for aim and swing behavior. Each needs the observability tests below before its
inferred labels are treated as demonstrated actions.

Before any VOD target-labelling pass, exclude non-gameplay viewpoints and
scoreboard-obscured scene frames, then mask person-like streamer graphics. This applies
to every proposal source, including model-assisted annotation: permanent graphics
must not become training targets. Keep excluded intervals explicit in the timeline
and retain original media; an obscured HUD field remains unknown. For box proposals,
do not blanket-mask the chat column: it overlaps real play and costs recall.
The gameplay gate combines `hud.read`, `events.playing_spiderman` and the visible
banner text; a full HUD alone also passes other heroes' spectator viewpoints.

Both domains pass through a common, recorded crop/resize for the scene input.
Read native HUD crops separately into structured events before masking HUD and
known overlay regions in the scene stream; carry visibility masks so missing
pixels are not hallucinated. Originals stay intact. Exact mask bounds and working
resolution are chosen against inspected samples, not inferred from screen height.
Compression, HUD layout, player skins, map, controls and overlays are domain shifts
that remain after normalization and need held-out evaluation.

The passive practice range is out of distribution for team-fight judgment. It
tests mechanics and integration; AI-only custom games are the first venue for
meaningful interactive engage/escape evaluation, though still not human play.

### E enablers: bounded offline pilots

These pilots use retained media and existing workers, with no live input or new
footage collection. Claude assigns execution; Codex owns the label specification
and independent audit. Their outputs are measured feasibility results, not a claim
that a detector or inverse-dynamics model already supplies trustworthy labels.

#### VOD character boxes: 30-frame audit, then at most 150 frames

1. **Sampling and provenance.** Reserve 60 current-regime Day frames, 60
   current-regime Req frames and 30 older-regime Req frames. Retained Day footage
   does not supply an older-regime cell; do not invent a balanced creator/patch
   matrix. Record source, session group, decoded PTS, source frame index, native
   dimensions, patch evidence and cooldown regime. Observed uppercut cooldown
   distinguishes these measured regimes; it does not uniquely identify a patch.
   A source with unknown session identity cannot establish an independent split.
2. **Diverse scenes.** Sample across independent encounters, sizes, maps, skins,
   airborne/grounded characters, crowds, effects and partial occlusion. Include at
   least 20 current-regime gameplay frames with no non-player character (own hero
   may be visible) to measure false positives. Do not fill the set with adjacent
   frames from one easy fight. Gate out death/spectating/scoreboards and hard cuts;
   mask person-like overlays first, preserving mask coordinates. Retain native
   frames and context locally under `data/demos/annotations/boxes/`; no media in git.
3. **Label contract.** Two independent vision annotators draw every visibly
   supported character box, not just the presumed target, on the same native frame.
   Supply a short native-resolution context window at the existing 10 Hz annotation
   rate; neighboring frames may clarify identity but may not fill an invisible
   body with a guessed box. Store visible-extent `xyxy` in original pixels,
   `self/other/unknown`, `enemy/ally/unknown`, optional hero identity, occlusion,
   uncertainty and evidence PTS. `render_mode` is mandatory: `body`,
   `outline_only`, `mixed`, or `unknown`. A normally rendered character with a coloured
   rim is `body`; a character revealed only by an x-ray silhouette through
   geometry is `outline_only`. Box only the rendered extent of either, including
   visibly attached equipment, excluding nameplates, health bars and detached
   effects and chevrons. `mixed` means one character has both directly rendered
   parts and x-ray parts: one box encloses their combined visible extent, with
   the two contributions noted; never box only its legs or split it into two
   characters. Both contributions must be identifiable at the annotated time:
   cite a bounded directly rendered part with character texture/shading and a
   bounded x-ray part belonging to that same character. A coloured rim on a direct
   body is not x-ray. There is no area-percentage threshold: a recognizable hand
   can establish direct rendering, but a few unidentifiable edge/compression pixels
   cannot. If those pixels leave the render mode genuinely unresolved, use
   `unknown`, not an automatic outline-only assignment. Mixed renders are retained but excluded from the first two-class
   detector loss and scored separately. Keep outline renders as separate labels/classes, never body positives
   or automatically shootable targets. Unknown render mode is not forced into
   either class. A short-window track ID is separate from hero class and survives
   only visually supported continuity.

   Allegiance needs a positive, source-calibrated cue. A clearly associated ally
   nameplate/chevron supports ally. A blue/cyan x-ray silhouette also supports ally
   on a source whose mapping is calibrated against marker-confirmed allies in
   that source; no marker is required on every instance. A clearly associated
   enemy marker or a red-to-pink outline following the body supports enemy on
   these default-colour sources. Record the cue and its source calibration; a
   blue glow or isolated blue patch is not a silhouette or an allegiance cue.
   Lack of an ally marker alone proves nothing. A warm effect, reflected light or
   conflicting cues produce unknown; cite native/context evidence rather than
   inferring from colour alone. A different colour configuration needs its own
   cue mapping. Quadrupedal or transformed playable heroes still count: anatomy
   is not a rule for excluding a hero.

   Confirmed objective vehicles, non-player NPCs, summons and dead bodies are
   outside this player-character label set; record the exclusion reason. They
   are hard negatives when visibly resolved, not automatically ignored areas.
   A prone or airborne pose alone does not prove a corpse. Separate uncertainty
   about **existence**, **extent**, **class** and **allegiance**. An uncertain
   allegiance does not discard an otherwise supported character box. Character
   support requires a recognizable anatomical/armoured fragment or silhouette,
   or context continuity to an identifiable player character. On a truncated
   direct fragment, coherent limb/surface texture with a rim following its contour
   is positive evidence; a coloured rim around an otherwise unidentified object
   alone cannot distinguish a hero from a deployable. Name the native-pixel cue
   and any continuity evidence. There is no minimum fraction of a body or demand
   for a visible head; size governs the detector loss, not character existence.
   A supported
   character with uncertain extent gets a low-confidence visible-extent box,
   clipping at the frame edge, plus extent uncertainty; it is never replaced by
   an ignore region merely because it is truncated. Where needed, record a
   supported core and a possible maximum extent; do not guess a hidden full body.
   Unresolved existence or player-versus-summon class gets a tight ignore region
   and reason, not a forced positive or empty background. If even the visible
   extent cannot support a box, retain an explicit character-presence record and
   mark localization unknown; this remains a localization limitation, not an
   absent character. Distinct supported bodies inside any ignore region are still
   annotated. A recognizable world-space player nameplate/chevron with no
   localizable character pixels gets a `marker_only` presence record with its
   marker location and evidence, never a body box or a guessed body-sized ignore.
   If a specific adjacent patch may be a character, add a tight unresolved-existence
   ignore for that patch and state the cue. Kill-feed portraits, scoreboard names
   and overlay text are HUD, not world-space presence records. Audit ignored
   regions for misses and report their area.

   For the first detector experiment, the geometry-positive floor is **40 native
   pixels on the longest side at 1920x1080**, scaled with source resolution before
   any model resize. Retain smaller supported instances as existence/optional-box
   annotations with `below_size_floor`; use them as ignore regions in this loss,
   not as negative background. Preserve their counts and original pilot scores:
   narrowing the detector's scope does not retroactively erase misses. The
   exporter/trainer must actually honor ignore regions or omit affected frames;
   silently dropping ignore metadata into ordinary YOLO negatives is forbidden.
   The VOD proposal detector uses separate `body` and `outline_only` detection
   classes; role and allegiance remain annotated attributes for visual confirmation.
4. **Audit before volume.** Start with 30 frames: ten from each available
   creator/regime group, selected outside the sealed final evaluation set. The
   annotators do not see each other's proposals. Adjudicate against original pixels,
   including missed characters and own-hero/overlay false positives. Report object
   count agreement, matched-box IoU, centre error, allegiance agreement/unknowns and
   error by box size. Agreement alone is not truth. Proposed scale gate: each pass
   reaches at least 90% precision and recall against adjudicated visible instances,
   matching at IoU >= 0.5; report denominators and median IoU separately. If either
   fails, repair the protocol and repeat only failed categories before scaling.
   Report non-self bodies and outline-only instances separately; the large own-hero
   boxes cannot carry the gate. Independent passes use different model families
   with the same input packet and no shared labels. Forks within one pass do not
   provide additional independent votes.
5. **Splits and detector experiment.** Freeze source-session groups before training;
   approximately 60/30/30 current-regime frames go to train/development/sealed test,
   subject to whole-session integrity rather than exact quotas. Keep both creators
   in train and test where available; disclose any creator missing from development.
   All 30 older-regime frames are a separate transfer diagnostic, not silently mixed
   into the first training set. Reuse the detector lane's training path with audited
   boxes; never reuse its inaccurate pseudo-labels as truth. Select thresholds on
   development only. Report sealed-test precision/recall at IoU 0.5, small-character
   recall, own-hero/overlay false positives, and failures per creator/regime. A
   proposed proposal-only gate is >=80% precision and recall on the current test
   set; with this small sample it authorizes assisted annotation, not autonomous
   target selection. Keep human/model visual confirmation of proposals. A failure
   means more targeted labels or a revised detector experiment, not blind scaling.

**Pilot decision: protocol repair is authorized; volume expansion is pending.**
The local adjudication report records 79 matched pairs (mean IoU 0.843), with
Claude precision/recall 95.5/87.6 and Codex 98.9/96.9 against a 97-instance
union-derived reference. Codex's direct-view-enemy result is 22/22; Claude's is
19/22 recall. The original requirement that both passes reach 90/90 is not met.
The reference cannot reveal jointly missed characters; its high recall estimates
are conditional on that incomplete reference. One error among 22 changes the
percentage by 4.5 points, which is not a +/-5-point confidence interval. These
numbers establish neither universal annotator accuracy nor detector performance.

The retained 30-frame pilot and both original passes stay unchanged. The 12-frame
repair uses a fresh cross-family pair after an explicitly exposed protocol
exercise, six frames per creator within the 150-frame cap. Its intended strata
are four crowded/effect-heavy frames, four small-character/outline frames and
four genuine no-other-character gameplay negatives (two per creator); the actual
support and selection failures are recorded below. Further repairs avoid pilot
adjacency and use only development-cleared session groups; uncertain-origin
September uploads stay inspection-only. Missing strata are reported, never
quietly substituted.

Before the adjudicator sees either proposal set, it sweeps **all 12 full frames**
with context and records its own candidate inventory, including ignored areas.
Then reconcile the inventories against pixels, preserving unresolved instances
and reporting sensitivity to their inclusion. This adds a way to discover shared
misses; a third model is still a fallible reference. Apply the revised 90/90 gate
to the declared >=40 px non-self body/outline classes separately, report smaller
instances separately, and report false proposals per negative frame. If a class
has too few supported examples, its result remains inconclusive rather than a
zero-denominator pass. The full set still needs at least 20 current-regime genuine
negative frames. Known payloads/overlays also supply hard-negative examples.

**Repair-audit acceptance: no expansion or detector fit is authorized.** The
12-frame adjudication in VUH-1322 gives resolved >=40 px body recall of 11/13
for Claude and 13/13 for Codex, with precision 11/11 and 13/13. Including four
unresolved bodies changes recall to 11/17 and 13/17; that is a sensitivity case,
not proof those four are characters. Outline-only recall is 3/5 and 5/5, with
precision 3/4 and 5/5: support is inconclusive. No overlay/HUD false proposals or
wrong-side allegiance calls occur in this audit. The two-pass gate fails because
Claude misses supported bodies. Codex meets the resolved-body point threshold,
but neither general annotator accuracy nor robustness to unresolved instances
is established. The nominal one-sided 95% binomial lower bound for 13/13 is
about 79%, assuming independent trials; clustered characters in a few frames
do not establish that assumption. A confidence-bound threshold is not added
retroactively to the original point-estimate gate.

The selector's four declared negatives contain only two genuinely empty scenes,
both Req; one is pre-round and does not count toward the gameplay-negative quota.
There is no demonstrated Day negative in this repair set. A negative requires
a whole-frame and context check for bodies, outlines and sub-floor characters,
with no unresolved character-presence region. Both an unresolved-existence/class
ignore on a specific candidate patch and a marker-only presence record disqualify
the strict genuine-negative quota. Marker-only frames remain useful as a
separately reported hard-negative stratum for a rendered-character detector;
they do not fill the 20-frame quota. Do not create ignores for arbitrary image
noise: record a concrete cue such as a contour, figure-shaped patch or associated
world marker that makes character existence uncertain. A resolved non-character
object does not disqualify a negative. This includes a confirmed payload's
through-wall outline: the exclusion concerns **character** outlines, not every
outlined object. Req `rq-03` at 652.0 s is retained as an objective-outline hard
negative after native-frame/context review; its silhouette follows the DEFEND
payload marker. Marker proximity alone cannot excuse a separate character.
Scarce qualifying scenes are a sourcing
gap, not permission to erase supported uncertainty. Body-class negatives, below-floor
scenes and genuine no-other-character gameplay negatives are separate facts.
Death, spectating, scoreboard and pre-round screens cannot fill the latter quota.
The negative label describes the **exact frame at t**, not a character-free
context window. Context helps resolve a contour, outline or marker actually
visible at t; a character at +/-0.5 s does not disqualify bare geometry at t.
Matching screen coordinates across camera/player motion does not establish the
same world point. If the centre frame has a concrete unresolved presence cue,
keep it unresolved; do not infer a hidden box from neighbouring frames. Apply
this rule to existing acceptances and rejections alike. A completely occluded
teammate with no rendered outline or marker is background for this detector;
the label makes no claim that the world contains no teammate. World occupancy
and target tracking require separate evidence.

Confirmed printed murals, posters and billboards depicting characters are map
art, not character instances. Retain them as scene-art hard negatives and count
them toward the strict quota when the rest of the frame qualifies. Establish
their surface-bound depiction from native pixels/context; an unresolved live
character versus artwork remains uncertain. Report false proposals on scene art
separately from overlay/HUD hits. Fixed-position Run/Crawl/Stop prompts are HUD,
not world-space player markers. Animated depictions on a confirmed in-world
display follow the same scene-art rule: motion alone does not make a live
character. Verify the display boundary/surface and depiction in context; unresolved
display-versus-character remains unknown. An objective marker's attached direction
arrow belongs to that marker, not an ally chevron; attachment must be supported,
not assumed for a detached arrow.

The rendered streamer mascot is overlay art regardless of its size or animation.
It is an overlay hard negative in an unmasked frame, never a character box.
Report which overlays are masked for a detector run: an excluded mascot region
cannot count as a successfully rejected false proposal. Do not change the existing
overlay masks merely to make this audit easier.

The selector records strata provisionally; the blind inventory determines actual
support. Confirmed corpses require identity continuity plus temporal evidence;
a kill-feed entry alone cannot identify a particular body. A continuously
identified live character followed by the same visibly limp/ragdoll/dissolving
body, loss of its attached live markers and a matching kill event is sufficient
even if it leaves view immediately afterward. Later post-death frames are not
mandatory. Marker loss alone may be occlusion and is insufficient; if identity
or the death transition is unresolved, retain the uncertainty rather than calling
it a confirmed corpse.

The exposed protocol exercise establishes no new accuracy. The negative scan in
`data/demos/annotations/boxes/negative-scan/` has 20 provisional strict candidates
(four Day, sixteen Req), including five in `req-840/`, plus two Day marker-only
hard negatives. Sourcing is stopped at its authorized target. Grid exhaustion is not proof that every
intervening frame contains a character. No broad rescan or grid densification is
authorized. Req 80.1 is retained over 79.3 as the documented existing choice;
do not reopen it. For future spacing conflicts, preserve already selected
candidates and examine newly qualifying candidates in timestamp order, taking
the earliest that meets the spacing rule; do not use an undefined "cleaner" ranking.
Retain prior decisions and reasons for corrections. Candidates still require valid own-play
segments under the repaired reader; a stale segment alone proves no eligibility.

The remaining shortfall authorizes **negative sourcing only** from at most one
additional non-overlapping 15-minute section per existing development broadcast:
Day `2879354299` and Req `2873352801`. Inspect Day first to improve creator balance.
Check source/game/hero and timestamp identity before full-resolution acquisition;
reject unsuitable sections without an unbounded replacement search. New sections
remain inspection-only until segment and patch clearance; retain their parent
session groups. They cannot supply independent validation. No new broadcast,
unresolved-origin YouTube upload or sealed media is authorized by this expansion.

Use the same bounded 5-second grid, two-second segment margin and 20-second spacing
between selected negatives; stop at 20 qualifying candidates in total or the two
sections' grid exhaustion. Preserve exclusions for previously supplied annotation
images/context and keep positive-instance exclusions unchanged. Retain up to five
marker-only hard negatives separately; they never fill the strict quota. Native
and context inspection remains required, with all candidates subject to the blind
inventory. No detector fit or new blind tranche is authorized before the support
requirements below are met. Keep sourcing shortfalls distinct from annotator accuracy.
The additional Day probe is rejected for hero/gameplay changes; there is no
replacement authorization. Req's acquired `840–1740 s` section supplies the five
remaining candidates under this bound. The four-Day/sixteen-Req
set meets creator presence, not creator balance: report false proposals by creator
with denominators, without a strong Day-specific accuracy claim. Final support
depends on corrected segmentation and blind inspection; reaching 20 provisional
candidates does not itself pass the annotation gate.
The new section's visual checks at +/-1 s do not replace the required two-second
segment margin; verify that margin under accepted segmentation before admission.
Colour-map/blob-count screens are triage only, never evidence of absence: the
new section's low-blob-count 852.0 s frame contains a distant enemy caught by
native inspection and context. Retain whole-frame inspection even for low-score
candidates; no additional sourcing or blind tranche follows the provisional count.

Before another blind repair is dispatched, freeze its candidate set and support
rule: at least 30 resolved >=40 px instances per evaluated class across at least
10 non-adjacent frames, with both creators represented, plus the full-set quota
of 20 genuine gameplay negatives. These are prospective development support
requirements, not a claim of 90% population accuracy. Each pass still needs the
90/90 point threshold; unresolved sensitivity, creator support and size bands
remain explicit. A class with inadequate support stays inconclusive. All repair
frames count toward the existing 150-frame cap; do not start repeated small
blind audits that cannot meet the declared support. Preserve every frozen pass,
the adjudicator's pre-key inventory and its errata unchanged.

The suggested 60 px proposal floor is an **initial evaluation threshold**, not
measured detector capability. Report <40, 40-59, 60-99 and >=100 px performance
before choosing a deployment cutoff on development data. No detector exists from
this pilot yet. Remaining annotation volume requires the repair audit and accepted
source quality. Replay research runs in parallel: if it yields a validated better
source, prioritize that source; an unavailable replay check does not block audited
existing-footage work or lower its acceptance gates. Freeze final detector
evaluation groups before training; a pilot
or repair frame is development evidence and cannot become a sealed test frame.

Boxes expose candidate targets; they do not prove which one the expert selected.
The enemy nearest the crosshair is a **candidate heuristic to audit**, especially
around a cast. Third-person parallax, leading a moving enemy, target switching,
area attacks and unseen targets can defeat it. Keep candidate sets/unknown, compare
pre-cast context with visible projectile/ability response, and keep later outcomes
separate from decision-time inputs. Kill-feed hero names are outcome evidence after
credit/assist semantics are verified; they do not supply a free persistent target ID.

Position labels begin with supported screen-relative relations (left/right,
above/below, clustering and visible cover), plus uncertainty. Box height is an
apparent-size cue, not a calibrated metre ruler across different heroes, poses,
FOVs and maps. No minimap does not rule out learning spatial behavior from video,
but boxes alone do not establish world coordinates or depth. Evaluate learned
destination choice once the controller can execute the same representation.

#### Camera motion and inverse dynamics: feasibility before inferred controls

The HUD lane's probe uses existing synchronized own-run video and commanded pad
logs, holding out whole runs. Start with visible image displacement/camera-motion
estimation; use the measured stick response as a baseline, not as independent
ground truth for achieved yaw/pitch. Fit any video/input offset on training runs
and freeze it for evaluation; missing or uncertain alignment limits the conclusion.
Stratify stationary turns, movement, ability-driven camera changes and swings.
Report missing strata: a corpus without paired swings cannot validate swing recovery.

Distinguish three outputs: observed screen motion, estimated camera rotation, and
inferred control input. Translation, parallax, automatic ability camera movement,
aim assist and motion blur can produce different motion for the same stick command.
Known pad state is commanded-input truth; the turn-rate map is a calibration model.
Do not label inferred rotation as exact measured camera ground truth. Report held-out
direction errors, command-reconstruction error/lag, coverage/abstentions and variation
across runs; assess uncertainty by run or contiguous block, not correlated frames.
Compare against neutral-input and calibrated-response baselines on the same cases.

The immediate result is whether any control-relevant signal is recoverable, in
which regimes, with what error. A range result does not prove transfer to Twitch
compression, mouse controls or different sensitivity/FOV. A swing cast's camera
direction is only one feature: anchor, momentum, movement and release also matter;
charge/cooldown events do not establish continuous button-hold duration.

The bounded probe reports 97–99% direction agreement on held-out ordinary range
turns at 60 fps, with approximate rate recovery (389 versus the calibrated
415 degrees/s at full stick). The same fast-turn footage sampled at 10 Hz fits
only 34% of intervals and reads a median 83 versus 172 degrees/s. The measured
stick-to-visible-motion offset is 20 ms. These comparisons use the commanded pad
and calibrated response, not an independent camera-angle measurement. No LB use
occurs in the 67,000 logged ticks, so swing recovery remains unvalidated.
The next bounded transfer check uses hand-inspected native 60 fps expert rotation
segments, excluding swings; confirm actual decoded cadence before sampling. Range
scores do not transfer to VODs, Day's animated overlays remain unhandled, and
ability-driven camera rotation must not be relabelled as a stick command.

**Simple versus aimed swing is part of the action contract.** The controller lane
records Simple Swing OFF and Hold to Swing ON for our client. The narrated guide
inventory also describes a separate simple-swing binding alongside manual swing,
including both in one combo; a creator's default toggle therefore cannot identify
every swing's control mode. Preserve `swing_mode = simple | aimed | unknown` per
action when evidenced. A generic HUD swing event proves neither mode nor anchor.
Do not infer the mode from a smooth trajectory or assume all expert swings are aimed.

Record a separate `control_context` beside kit context: input device, default swing
mode, separate-binding availability, hold/toggle release behavior, and known camera
settings, each with evidence or unknown. Settings changes segment that context.
For low-level imitation, use mode-compatible examples or explicitly condition on
the mode and validate both mappings; unknown-mode footage can still supply visible
route/destination supervision without invented anchor or button labels. Automatic
anchor selection must not be labelled as the expert aiming at the selected anchor.
Hold duration and toggle-release actions are distinct input targets. The present
pad executor supports only its verified mapping; simple-swing-specific techniques
remain unexecutable until the controller owner verifies a supported binding and
completion behavior. Do not silently translate both modes to the same LB action.

[VPT](https://arxiv.org/abs/2206.11795) demonstrates the paired-data inverse-dynamics
approach in Minecraft; it supplies a research precedent, not a transfer guarantee
for Rivals. An offline inverse model may inspect future frames to infer an earlier
action, but the policy trained from those labels remains causal. If the probe
succeeds, audit a small expert-video transfer set before producing training labels.
If it fails, retain visible route/destination/timing supervision and identify the
missing paired examples for collection after the live-input freeze lifts.

## Training and runtime

### Configurable playstyle

James wants selectable playstyle through interpretable sliders. The planned
implementation is one policy conditioned on a small preference vector, sharing
the same perception and controller, rather than a separate model per style.
This extends E/F after the base policy and relevant actions work; it does not
block B0 or the first imitation baseline. The sliders are planned capabilities,
not controls implemented by the current policy.

| Initial slider | Lower end | Higher end | Observable behavior to compare |
|---|---|---|---|
| Aggression | Wait for stronger openings | Commit more readily | Engagement choices and delay under comparable health, resources, targets and threats |
| Swing conservation | Spend charges readily | Preserve charges for traversal or escape | Optional swing/cancel spending and charges retained under comparable opportunities |

Combo commitment and target preference are later candidates, not additional
initial controls. Style expresses a preference conditional on the situation;
high aggression is not an instruction to ignore threats, and high conservation
does not forbid a necessary escape. Use the declared slider direction consistently
in labels, model inputs and UI. The neutral setting is an evaluated default.

Training uses audited behavioral examples with style evidence and uncertainty.
Creator identity can identify a demonstration source, but does not establish one
fixed style: the same player changes behavior across encounters. Include ordinary
play, failed attempts and successful outcomes; high movement alone does not prove
aggression. Label observed tendencies over sufficient context, keeping inferred
intent unknown where unsupported. Condition imitation on supported style labels;
an unlabeled example is not automatically the neutral style. Sparse evidence
supports a few evaluated presets before a claim of smooth slider interpolation.

First evaluate low/default/high settings on matched starts or held-out situations,
with perception, controller and patch fixed. Require a repeatable change in the
named behavior, report effects on completion, survival and later match wins, and
check whether the sliders interfere with each other. Aggression and escape claims
need F's fighting venue; passive range bots only support mechanics and resource
tests. A slider that does not change behavior is not accepted. Later RL may use
bounded, explicit preference terms alongside the task objective, with tradeoffs
reported rather than treating style compliance as gameplay success.

Preferences cannot bypass action legality, input guards or executor capability.
Simple-swing cancels become a style choice only after that action works and has
audited labels; exact short-cancel execution is not a prerequisite for initial
style work. Standardize our executor on hold-to-swing. Source hold/toggle settings
matter only when reconstructing inputs; match the observed attachment/release
behavior without implementing a user-facing release-style switch.

```mermaid
flowchart LR
    V[Expert VODs] --> D[Temporal demonstrations]
    H[Human video and keyboard/mouse inputs] --> X[Paired execution training]
    X --> K[Offline keyboard/mouse action chunks]
    K --> A[Domain and transfer validation before live use]
    D --> L[Reviewed intent and target labels]
    L --> T[Imitation training locally or on rented GPU]
    T --> P[Learned temporal policy]
    F[Runtime frames and events: transfer unvalidated] --> P
    S[Planned style preferences: aggression and swing conservation] -.-> P
    P --> I[Intent plus fixed target selector]
    I --> G[Current-state validity checks]
    G --> C[Calibrated controller]
    C --> E[Range or AI-only custom evaluation]
    E --> R[Reviewed failures and human corrections]
    R --> D
```

Policy v0 learns the existing intent vocabulary; a fixed targeting heuristic selects
among current live detections, and evaluation holds that selector constant across
policies. This isolates intent learning while VOD target labels are expensive.
A small annotated target set measures observability and supports later learned target
choice; v0 does not claim to learn expert target selection. Spatial
directions or anchors need an agreed representation and working executor before they
become outputs. Unknown abilities and invalid targets stay guarded at execution time.
An option's completion or failure is distinct from the brain's guessed hold duration.

Two policy domains remain explicit. The **range execution policy** uses live
`State`, calibrated ranges and the controller; shared track IDs (VUH-1314) and
observation-derived option status (VUH-1315) are queued work, not assumed inputs
already delivered. The **VOD tactical policy** uses frame history and HUD events,
with target supervision only where annotators draw boxes. These domains do not
share a validated enemy/identity channel. Keep their datasets, labels and metrics
separate until perception establishes comparable entities; any integrated v0
trial is a measured transfer experiment with the fixed live selector.

Target choice and positioning are explicitly **open goals after v0**. `Engage`
hides substantial Spider-Man skill inside the engineered controller: approach
geometry, movement, aim, range management and attack execution cannot be claimed
as learned from VODs merely because a model chooses that option. Restoring learned
target choice, spatial setup/escape choices and finer execution requires observable
labels, an executable interface and separate evaluation. The narrow v0 measures
intent selection; it does not satisfy the full game-sense objective.

Swing execution is part of that limitation. VODs and guides show routes, momentum
setups, release/cancel sequences and their visible results, but supply no exact
stick/camera/button labels. In v0, the controller executes swings; watching more
VODs does not train its trajectory control. Learned swing timing/anchor choice
needs a spatial output contract and executable anchors. Later motor learning needs
synchronized video and native input labels, with demonstrated response checked.
James's keyboard/mouse recordings now supply this motor-learning source; transfer to
the virtual-pad controller remains unproven and is not inferred from expert video.

HUD events provide relatively cheap supervision for ability use and observable
outcomes. They do not prove engage, disengage, no-engage or a complete combo choice:
those labels still need reviewed temporal context. Primitive sequence learning and
tactical intent learning retain separate labels and metrics; reliable HUD extraction
does not establish reliable tactical annotation.

Behavioral cloning predicts reviewed demonstrated choices; it needs no reward function.
Class imbalance matters: constant movement or idle frames must not swamp rare retreat
and engagement decisions. Measure a simple baseline before choosing model size. The
Mac is the default training environment, niced; James prefers using his local
hardware wherever practical. The existing tactical experiments prefer MLX when the
selected architecture has a suitable implementation, otherwise PyTorch/MPS. New paired
execution training uses PyTorch across Windows and Mac, as specified above. The PC GPU
belongs to the live game.
Runtime placement is measured against latency and game performance before adoption.
The policy lane's current offline baseline uses a frozen DINO ViT-S/16 encoder
and a two-layer GRU head in MLX; the encoder choice is provisional and its
reported held-out results do not establish gameplay improvement. Independent
data-pipeline review and runtime validation remain acceptance gates. The RL
actor/value plan above extends that baseline rather than choosing a large VLM.

James approves an initial $100 cloud-compute budget (2026-09-20). Local hardware
is a starting point, not an architectural limit: rent a GPU when measured throughput,
memory requirements or iteration speed justify it. Track spend against that initial
allocation and revisit funding before exceeding it; $100 is not an estimate for
the complete project. Hosted annotation and storage costs are estimated separately.

The [local-model measurement](lanes/local-jev.md) is a concrete placement constraint:
the 35B-A3B server answers in about 85 ms median on the Mac but 175 ms median /
531 ms p95 from the PC in the reported run. A tiny kept-alive health request takes
63–90 ms across that path versus 0.4 ms locally. These are measurements of the present
network, not an unavoidable LAN cost; wiring and remeasurement may change them.
Frame transport is unmeasured. The reported server occupies 20–32 GB and roughly
69% Mac GPU at 10 Hz, so serving that configuration and training are scheduled
separately. The server is parked; no further Jev infrastructure is on the critical path.

## First acceptance and evaluation

The first range skill approaches and executes an attack; choosing whether to
engage, continue or escape under threat requires AI-only custom evaluation.
Mechanical execution is the first measurable slice, not the whole goal.

1. Inspect real samples from both creators and establish which labels are observable.
2. Hand-label a small set of contiguous decisions and HUD events. Report event precision,
   recall and timing error, plus unreadable coverage, against those human labels.
3. Train a first intent policy with the fixed target selector and evaluate on held-out sessions against a simple
   majority baseline and the scripted policy where its required inputs are available.
   Report confusion by action, invalid choices and abstentions. Report selector errors
   separately on annotated examples; learned target choice needs its own later comparison.
4. Compare integrated policies in repeatable range scenarios with the same perception,
   controller, start conditions and budget. Inspect actual successes and failures.
5. Evaluate richer tactical choices in AI-only custom games once navigation and guards
   work. These results do not establish expert-level play against human opponents.

The first complete engage-to-outcome evaluation is a bounded AI-only encounter set,
preregistered before trials begin: start positions, opponent composition, patch,
cooldown regime, encounter time limit, trial cap and held-out starts. Include both
appropriate-engage and no-engage situations, followed by continuation or escape under
threat. Compare the learned policy with frozen scripted and simple fixed-choice
baselines using the same perception, executor and guards. Score engage/no-engage
choices separately from attack execution and continuation/escape outcomes; report
failures, interruptions, unknown outcomes and uncertainty across repeated trials.
This is a planned acceptance experiment. Verified AI-only lobby guards, reproducible
resets and observable outcomes are prerequisites; range damage alone cannot pass it.

Gameplay outcomes remain separate from imitation agreement. A different action is
not necessarily worse, and a copied expert action is not necessarily appropriate for
the executor's capabilities. Record recovery examples from the agent's own failures
and obtain human corrections rather than only collecting more clean expert wins.

The controller lane confirms that BACK opens a range scoreboard with damage and
KOs. The lead reports 9/9 values read on a reference frame and an automatically
parsed 1 KO / 275 damage in a 30-second integrated run. That cooldown-free run
holds 57 Hz reflex and 10 Hz decisions with zero reported over-budget ticks;
it is not the real-cooldown baseline. Counter deltas, broader coverage and
episode/reset alignment still need validation before becoming rewards.
Designated-target completion additionally needs VUH-1314's identity tracking
associated with the delivered kill-feed reader; either component alone does not
prove that the selected target died.

RL is not active. It requires dependable episode boundaries, reset, outcome labels and
a trainable policy. The reward contract above limits range outcomes to confirmed
completion, timeout, interruption and lost-range; passive bots supply no combat
death or damage-taken signal. Elapsed time is a small cost; outgoing damage or hits
are optional shaping only when measured reliably. No numeric weights are accepted yet.
Disappearance is not a kill, ult charge is not damage, and missing evidence is unknown.
Manually adjudicated evaluation is valid while automatic outcome readers are incomplete.

## Sources

**Conditional source candidate: Falores.** James recommends Falores as a strong
Spider-Man player. Identity, channel, footage and suitability are unverified. Revisit
only if already-held footage leaves a named coverage or independent-session gap;
this recommendation does not authorize acquisition or change the current source scope.

### Acquisition evidence, 2026-09-20

Installed `yt-dlp` lists recent videos for both Twitch channels and downloads
bounded public sections without cookies or login. `ffprobe` confirms 1920x1080,
60 fps for the inspected samples. `data/demos/samples/manifest.json` names nine
sample frames and their clip-relative timestamps; images and clips are local only.

| Source | Inspected sample | Finding |
|---|---|---|
| [Req, VOD 2873352801](https://www.twitch.tv/videos/2873352801) | Requested 32:00–33:00; local duration 60.083 s | Spider-Man combat, death/spectating and return. Chat intermittently obscures rightmost abilities/ult; HP and web ammo visible. +15 s is a different hero's spectator POV. |
| [Day, VOD 2879354299](https://www.twitch.tv/videos/2879354299) | Requested 6:00:00–6:01:00; approximately 60 s locally | Spider-Man traversal and combat. At +5/+30/+45 s, HP is 250/242/99 and ammo 5/4/4. HP, ammo and ability icons visible; avatar and sponsor overlays need masks. |

The six pilot decision times are clip-relative: Req +5, +15, +30, +45 seconds;
Day +30 and +45 seconds. Source windows are already present in the two retained
clips. Req +15 is a deliberate spectator negative. The manifest names the clips;
the Day pilot uses the `-21600-60s.mp4` file, not the earlier ten-second probe.

Req's metadata reports a 5:49:42 broadcast, uploaded September 13. Day's September
20 broadcast is still growing when inspected (8:03:36 at the initial probe), so
that duration is not final. Other Day samples contain hero selection, another hero,
a break screen, a tournament co-watch and another game. Channel/title is insufficient
to establish that a segment is the creator playing Spider-Man.

The Day YouTube candidate `yF2fr6wSkqE` identifies Day and links `daymr`, but its
media download returns HTTP 403; no access workaround is attempted. Twitch samples
provide the required pixels. Rank claims are not independently verified. The
[Twitch terms page](https://legal.twitch.com/en/legal/terms-of-service/) returned
only a navigation shell to the reader, so this feasibility pass establishes no
training licence or permission to redistribute. No full archive or training run
is performed in this pass.

### Additional raw VOD batch

`data/demos/vods/manifest.json` records four approximately 15-minute 1080p60
sections from four broadcasts: Day 2879354299 (6:01–6:16) and 2877719252
(0:30–0:45), Req 2873352801 (0:33–0:48) and 2871472478 (1:30–1:45).
The batch contains 59.98 minutes of raw video, 2.8 GB. The HUD lane's fixed-reader
pass identifies 39.6 minutes of own-Spider-Man play (62–69% per section), 202
segments and 4,652 events; own-hero play duration is not accepted imitation-label
duration. Nine sparse stills per clip confirm Spider-Man
play alongside scoreboards, death/killcam, hero selection and other exclusions.
Day's newer section includes a browser co-watch; the older section includes a
lost match and break screen. Req's sections include low-HP combat and recovery.

The raw acquisition inventory remains `inspection_only`; event outputs live in
`data/demos/events/sections/`, keyed to decoded PTS. The two broadcasts
outside the original pilot are reserved evaluation candidates; keep whole-session
groups separate and check for duplicated matches before assigning final splits.
The newer Day cut has nonzero first video PTS (1.616 s); stream-copy source offsets
are requested, not frame-verified. Construct clip time from decoded PTS before
extracting temporal labels. Collection continues independently of the HUD-fix /
hand-checked-event gate; raw acquisition does not pass that gate.

Median play segments span only 3.8–12.1 seconds per section because scoreboard
checks interrupt fights. Bridging gaps shorter than one second produces 15–31
runs per section with 7–27 second medians, but the intervening scoreboard frames
must retain their visibility masks. This is a proposed loader policy, not a
claim that bridging is implemented or that all gaps are safe to bridge. Never
bridge death, hero change or editorial cuts. Budget about 0.66 own-play minutes
per raw minute for these four sections only, and measure accepted causal windows
after masking/history requirements rather than extrapolating from footage hours.
The HUD lane's full-rate scene-cut detector provides `hard_cut` / `after_cut`
boundaries for edited uploads; its measured threshold remains source-dependent
evidence, not permission to assume every cut in a new upload is detected.

### First split and bounded collection decision

`data/demos/splits/s10-normal-v0.json` is a proposal, not a training authorization.
Its initial counts are 18.3 usable minutes from the two pilot broadcasts for train,
23.5 minutes from the September Req uploads for validation, and 21.0 minutes from
the two reserved broadcasts for test. These counts remain provisional while the
HUD lane corrects the newer Day section's Doctor Strange false-positive interval.
Overlapping windows are not independent examples; report session counts as well
as window counts. All sources remain `inspection_only` until their gates pass.

**The proposed validation assignment is not accepted.** Pixel checks exclude
duplication of the retained Twitch sections, but not another part of the reserved
Req broadcast. Validation influences checkpoint and hyperparameter selection, so
an unresolved shared session also compromises a sealed test when assigned to
validation. Keep those uploads inspection-only until provenance resolves the
overlap; the exception is not made safe by keeping them out of gradient updates.
The two reserved broadcasts remain untouched final evaluation candidates.

The Twitch expansion proposal is bounded at four 15-minute sections from four
additional current-patch broadcasts: two per creator, one per creator assigned
to train and one to validation before fitting. Exclude existing and reserved
session groups. Record normal cooldowns, own-Spider-Man visibility, source dates
and observable map identity (otherwise unknown). Spot-check the first two sections
with the HUD lane before completing the batch. Expected usable duration is a
collection estimate, not an acceptance threshold. More sessions address the
current creator/editing imbalance and session dominance; more minutes from the
same sessions do not establish independent validation.

The local `data/demos/vods/batch2/handback.md` records a sourcing blocker: the
2026-09-20 public Req archive listing contains the existing and sealed broadcasts
plus `2833877598`, dated 2026-07-31. It provides neither additional current-patch
Req session required by the proposal. The attempted Day `2876184005` section
(00:30–00:45) is rejected: all nine worker-inspected stills show another game;
Codex's independent still check also finds no Rivals gameplay HUD. This classifies
the sampled section, not the entire broadcast. No new HUD-ready pair or accepted
validation session exists from this attempt. Acquisition of additional independent
match sessions is parked on this source shortage; existing or sealed sessions are
not substitutes. The bounded expert practice-range scan uses existing development
broadcasts for a different purpose, while replay feasibility proceeds independently.
Neither investigation requires an action from James.

The initial 18.3 minutes can support a bounded first fit and a learning-curve
probe after label acceptance. There is no evidence yet that this amount suffices
for generalization, or that a particular larger duration will. Acquisition does
not delay a ready pipeline experiment or waive the event/label audit. Compare
majority and repeat-previous baselines, report transitions and per-session results,
and select models only on an independent validation set.

### Req YouTube gameplay batch

`data/demos/youtube/reqmr/manifest.json` inventories six complete uploads from
Req's verified source channel `@reqmr1`, acquired 2026-09-20: `yjc51uOjKEQ`,
`d0C8RMBnFfA`, `ftnk5SVycXY`, `Cf_2goe1snQ`, `V6iaq9dP8FQ` and `G7HmV8zyEh8`.
They add approximately 104 raw minutes at 1080p60. The existing Req narrated
guide remains in `data/demos/guides/` and is not duplicated.

Nine inspected stills per upload show Spider-Man combat, traversal, low HP,
victory/defeat screens and exclusions including spectating, scoreboards and
outros. HUDs are generally visible in sampled gameplay; alternate skins, chat
overlap and damage vignettes remain perception concerns. Two uploads are from
September 2026 and four from April/May; retain patch provenance. Full uploads
are not necessarily continuous matches: segment editorial cuts as well as game
state changes before constructing temporal examples.

All six remain `inspection_only`, without new event/action labels or a verified
usable duration. Match/session deduplication against Twitch and other uploads
precedes split assignment; a YouTube upload ID is not an independent session.
The loss-focused video visibly ends in defeat, but individual decisions still
need suitability review. Acquisition expands coverage without passing the label
audit or training gates.

### Guide demonstrations

[Narrated combo inventory](lanes/combo-arsenal.md) records nine locally acquired
and automatically transcribed guides from Day, Req, MatchuXD and two targeted
supplementary sources. Source timestamps distinguish range demonstrations from
match commentary. `data/demos/guides/manifest.json` records media properties and
transcript provenance; raw media and transcripts stay local. Narration supplies
semantic order and usage conditions, not exact pad inputs or current cancel
intervals. The Sekkombo pull binding and Stack timing remain live-verification gates.

### Research references

- [VPT](https://openai.com/index/vpt/): action-labelled demonstrations support inference
  of actions in additional video; the scale of its Minecraft result is not a promise
  about the amount of Rivals data needed.
- [DAgger](https://proceedings.mlr.press/v15/ross11a.html): iterative expert correction
  addresses states reached by the learner's own actions.
- [DayMR VODs](https://www.twitch.tv/daymr/videos) and
  [ReqMR VODs](https://www.twitch.tv/reqmr/videos): technical availability checked
  2026-09-20 with the installed `yt-dlp`; local sample evidence accompanies the manifest.
