# Executable policy reframe — lead direction, 2026-09-22

**Build a first mechanical policy that requests individual Web-Cluster
starts, alongside independently running scripted movement/aim.** Learn
`start_web_cluster` versus `no_new_web_cluster`, with unknown supervision masked.
The second value says nothing about movement, other abilities or tactical intent.
Neutral remains a runtime refusal/fault response, not a required human class.
This is a new event contract, not a rename of Idle or an all-Engage workaround.

James's five priorities below govern the destination. The first mechanism covers
one small part of mechanical execution; it must expose rather than absorb the
missing tactical capabilities. VUH-1349 and stationary-wait support are no longer
prerequisites. The lead adopts this direction; implementation and independent
review remain outstanding. No code, data or candidate annotations change by this
decision. Root owns this document after the producer's design handoff.

James clarified that routing means fluent traversal: smooth swings, momentum,
bhops and movement transitions, as well as getting into position. Movement
quality and timing must become learned outputs, not remain permanently inside a
fixed macro. The first atomic cast is a delivery step, not the final action space.

Demonstrations supply an initial policy and useful behavior, not a ceiling.
VUH-1321's bounded outcome-driven experiments may discover better cast timing;
VUH-1322 extends that freedom to measured movement and execution parameters.
Fixed combo order, fixed swing duration or fixed camera trajectories cannot
produce discoveries in those dimensions. Expand the action space as each
executor becomes observable and controllable, preserving independent guards.
Compare discovered behaviors on new starts and outcomes, rather than rewarding
novelty or resemblance alone. Team assistance and escape require fighting and
ally/threat observations under VUH-1323; bot farming cannot establish team value.

## Five capabilities, evidence and evaluation

| Capability | Existing affordance and evidence | First scope and evaluation |
|---|---|---|
| Mechanical execution | Controller has separate web, melee, uppercut, pull/strike and swing primitives, but `Engage` chooses their starts by script. James's short native source shows attacks, web-ammo depletion and ability countdowns. Exact motor controls are a separate KBM domain. | **First:** learned Web-Cluster start timing during a scripted, target-visible range encounter. Measure onset precision/recall/timing, missed opportunities, unsupported/refused decisions, executed pulses and designated-bot completion. No claim of learned aim, full combo, or expert parity. |
| Opportunity / committing picks | Fixed causal selector and target tracker exist. Nearby/distant disagreement was reproduced; detector repair improves candidate20021 correspondence but does not annotate intent or target value. | Keep the reviewed designated target fixed for the mechanical experiment. Later require visible alternatives, commitment/switch reasons and outcomes from suitable existing expert play. Evaluate picked-target identity, premature swaps, completion and time spent without useful action; proximity alone is not value. |
| Escaping when hurt | `State` has HP; the brain has a low-HP rule. Current `Disengage` turns 180 degrees, then walks/jumps. Passive range bots do not supply convincing threat/escape outcomes. | No learned escape claim. Need visible threat, HP trajectory, departure and a verified safer endpoint in fighting demonstrations/rollouts. Evaluate escape success, damage/death and re-entry opportunity under comparable threat; a blind turn is not a safe route. Fighting evaluation stays behind the plan's AI-only scope/guard prerequisites. |
| Fluent traversal / routing | James means smooth swings, momentum, bhops and movement transitions. `SwingTo` and a fixed swing primitive exist, but a one-second LB+forward sequence cannot learn release/jump/camera timing. The 26 current features omit scene topology, destinations and obstacles. | Learn measured movement timing and control from source-specific demonstrations, then optimize outcome in bounded traversal trials. Measure destination success, speed/momentum retention where observable, unnecessary stops, collisions/falls, time and charges on new starts. Rollouts after respawn are one application; map-waypoint selection alone does not satisfy this capability. |
| Teammate support | Current `State` classes are enemy/target/anchor; no ally state, teammate objective or support outcome is represented. Range evidence cannot establish team benefit. | Later require observable ally/threat/objective context and reviewed support choices from suitable expert play. Evaluate protection/peel, objective contribution and missed support opportunities in authorized fighting scenarios. No invented ally labels or team metrics in the first range mechanism. |

These are extensions of the existing learning-plan A/B/E/F gates, not a parallel
roadmap. The plan's current Idle/Engage paragraphs and visual-supervision document
are stale under James's correction; root should revise those explicitly. No
standing-idle example or unnatural new recording is requested.

## One next implementable contract

**Task:** from five causal observations at 10 Hz, predict whether the human begins
a visually confirmed Web-Cluster cast in `(t,t+100 ms]` toward the same causally
selected target. This predicts an upcoming semantic cast event, not a raw button
or exact physical input-delivery time. Runtime converts an accepted request into
one calibrated pad `web_cluster` pulse. That cross-domain semantic/execution
projection needs its own review and measured timing; it is not KBM-to-pad identity.

Proposed new format: `rivals-range-skill-events-v1`; head
`web_cluster_start`, outcome vocabulary `no_new_start | start`. Every example
has a separate observed/unknown label mask and evidence interval. No class from
`rivals-range-options-v1` transfers by index or name.

Independent contract review accepted this direction with these rules, adopted
by the lead before constructing examples or the controller boundary:

- Pin a 10 Hz grid to the source segment before locating events. Select actual
  decoded frames causally at those ticks and record tick versus acquisition time;
  never move a bin to make an observed onset fit. Positive onset interval
  `(last_proven_not_started, first_proven_started]` must lie wholly inside the
  decision horizon `(anchor, anchor + .1]`. Ambiguity spanning two bins masks
  both; it cannot manufacture a negative next to an uncertain positive.
- Anchor targets are the actual causal selected detections. Keep earlier selector
  outputs as observed; target switches or disagreement stay masked when identity
  is uncertain. Future victim annotations never repair causal features.
- Every positive carries a stable event ID and onset bracket. Every label carries
  a complete observed exposure interval, mask/reason and latest confirmation time.
  Include confirmation in purge footprints; overlapping views do not create extra
  casts. Count unique events and observed bins separately, and use one-to-one event
  matching for timing metrics. Report the full grid and any sampling policy.
- One reviewed onset and one reviewed non-onset can establish fit/reload plumbing.
  Useful timing claims additionally need resource-legal, target-visible non-onsets;
  positive-ammo starts versus empty-ammo negatives may teach only resource gating.
  Sparse support is a measured limitation, not a request for staged waits.

- **Positive:** directly observed new Web-Cluster execution toward the selected
  bot, with a bracketed onset and supporting animation/projectile/resource
  evidence. A held generic attack, melee, E/F press or target being hit by an
  unidentified source is insufficient.
- **Negative:** the whole label interval is observable and contains no new
  Web-Cluster cast. The human may move, scan, swing, melee, use another ability or
  recover. Those actions are not changed into global Idle labels. Repeated
  frames of a single already-started cast are not repeated positive starts.
- **Unknown:** occluded weapon/action evidence, ambiguous cast identity or onset
  spanning a bin edge, target disagreement, missing focus/clock proof, network
  snap, unsupported overlapping events, or incomplete label coverage. Mask the
  affected event label; don't infer absence solely from unchanged/zero ammo or
  an unavailable-looking icon. A failed/attempted raw press is distinct from a
  visually executed cast and is not silently merged into this task.

Use the current pixel-derived State/target value+known features and causal window
checks first. No human control values, future target annotation, future resource
changes or reconstructed outcome enters features. The target at each history
step remains the actual causal selector output. Keep source/profile, recording,
segment, observation `available_t`, label onset bracket and latest confirmation
time; purge using that full footprint. Loss is masked per event head, with
training-only weighting. Do not add controller phase to the model unless a
comparable causal human-side observation is actually available.

**Why one pulse, not start/continue/terminate for every primitive:** a confirmed
visual cast can support an atomic Web-Cluster start. The existing video packet
does not establish exact hold/release or cancellation intent for the 1.3-second
`melee_combo`, swing or burst. Inferring those transitions from animation would
invent motor supervision. Add hold/terminate heads only when separately reviewed
native controls or visual event boundaries actually support their semantics.

## Controller boundary root must implement and review

Proposed typed intent, passed through the existing decision timestamp path:

```python
RangeSkill(target, web_cluster_request, decision_id, valid_until, resources)
# web_cluster_request: "start" | "no_new_start"
# target: current causal Detection; valid_until: decision anchor + one period
# resources: immutable decision-scoped ammo value and its observation timestamp
```

The current reflex `State` omits ammo; the decision `State` contains the HUD
observation. Root carries that immutable decision resource snapshot, without
retimestamping it as a new reflex measurement. Validate its value, observation
time and age independently of the fresh target/aim observations. Unknown or
stale ammo prevents a start; it never creates a guessed zero or an automatic shot.
Request IDs are monotonically increasing within one fresh episode/controller;
accepted and rejected IDs remain consumed through intervening target/no-new changes.
Mutated duplicate IDs or backwards requests refuse. The 100 ms deadline is separate
from the loop's legacy one-second decision-staleness rule.

Its controller branch has two independent responsibilities:

1. Continuously update target following/aim and the explicit scripted movement
   baseline. Reuse `_follow`, `_aim`, same-target measurement, stability and
   approach guards. Do **not** call the offensive selection part of `Engage`.
   A healthy `no_new_start` continues that movement/aim. Continuous here means
   independently updated, not forced nonzero stick when unsafe. For the first
   experiment, use a verified same-platform, target-visible approach/track
   scenario; current approach does not detect ledges. Target loss, post-kill
   relocation and free roaming need their own reviewed movement handling or an
   episode end, not an implicit Search substitute. No learned movement claim.
2. Start `primitive("web_cluster")` only for a fresh, unconsumed model `start`
   request on that target, with current target/aim/stability and known-ammo
   legality. Consume the decision ID once; do not hold an unready request to fire
   later. A later valid `no_new_start` neither schedules another shot nor resets
   the normal, bounded pulse already running. It never starts uppercut, melee,
   pull or burst as a fallback. A stale/fault/refusal decision cancels offensive
   execution and produces neutral through the existing refusal path. Screen,
   focus, watchdog and decision-age gates retain independent authority.

Every start is terminally consumed on its first acceptance or rejection, including
busy/unaligned/unknown-resource rejection. For this first implementation, reject
late starts unless the full calibrated press can fit before `valid_until`;
do not silently extend authorization past the decision deadline. Normal no-new
may complete only an owned new-mode pulse. Expiry/refusal/target loss cancels it;
log interrupted presses as truncated, not completed calibrated executions.

The pulse duration/release remains calibrated scripted execution; only its start
decision is learned. Pulse spacing/resource gates may reject a proposal, but
must not generate one. Log proposal, mask, acceptance/rejection, actual press and
release, target ID, controller/movement source and decision ID atomically. Human
labels supervise the proposed semantic event; forced runtime actions must not be
fed back as if the model selected them.

This needs an actual branch and sequence-ownership change. Today `Controller.step`
lets a playing `seq` override Search output; `Engage` starts uppercut/melee/web
automatically. `LearnedRangeBrain` also returns some scripted `brain.gate` early
intents, which cannot become fresh learned attack authorization. Separate those
selection/safety results from learned event requests. Clear legacy attack
sequences on entry, target switch and refusal; forbid a burst or old sequence
from bypassing the new branch. Don't just map `no_new_start` to `Search` or `Idle`.

Review tests must exercise moving+no-new-start, moving+one-start, repeated
decision IDs, expiry before alignment, active pulse completion, sequence leakage
from Engage/Search, target switch/coast, missing detector/history and refusal
release through the real pure Controller. Confirm all offensive starts in the
mechanical episode trace originated in an accepted learned request.

Root's smallest code assignment: `agent/intents.py` (typed request),
`agent/controller.py` and `tests/test_controller.py` (separate movement and pulse
authorization), `policy/range_policy.py` and `tests/test_range_policy.py` (new
event schema/head/masks/format), `agent/learned_range.py` (consumer and refusal),
`agent/loop.py` (explicit mode, version pin and trace). Reuse the GRU, causal
window checks, portable train/save/load, source/runtime identities and external
deployment receipt; do not reuse the old action semantics or rewrite frozen
candidate rows. Admission owns a newly versioned semantic-event producer and
independent example review, alongside root's plan/CLI integration.

## Existing source, exact missing evidence and next experiment

The best immediate source is still James's original
`20260922T032454-642Z-24328-1`, normal-resource pre-menu gameplay approximately
11.0–22.25 seconds. Its established visual-only profile and its own +21 ms mux
offset preserve unknown motor settings. Our already inspected native frames
show web ammo 1 at 19.921 and 0 at 20.021 while attacking nearby Galacta. That is
a concrete cast-review locator, **not yet an admitted onset label**. Moving,
other-ability and recovery periods in that same source are candidate per-web
non-onsets; they never needed to be stationary. No new corpus was read for this
proposal. Both existing recordings share the evening group; the later source's
unknown regime/settings cannot be borrowed or pooled as equivalent.

The exact missing first-fit evidence is admission's reviewed event packet:
bracket the visible web cast at that locator; inspect an observable contrasting
no-new-web interval during normal play; establish causal target correspondence
under the independently accepted perception versions; retain source timing,
focus/suitability, uncertainty and semantic projection receipts. Count actual
accepted starts/non-starts and unknown reasons. If either contrast is absent,
inspect the remaining already authorized normal-resource span and report the
specific ambiguity. Do not lower observability rules, substitute scripted labels,
train a constant-start head or request staged idle footage.

Once that packet is admitted, a train-only fit may proceed on Mac without waiting
for independent validation. Compare event behavior with never-start, always-start,
training-rate and recent-event/resource baselines on their comparable observed
rows; report event counts, onset precision/recall, timing error, legal-opportunity
strata, refusal coverage and the masks. Baselines remain diagnostics, not labels.
A same-session fit is a plumbing/fit result, not evidence of generalization.

Acceptance/live reliance still needs independent-session semantic evaluation
(VUH-1347) and the new controller/semantic/runtime binding review. Keep the
existing bounded range-completion/episode audit and matched scripted reference,
but state that only web-start timing is learned and all scripted movement/aim
is held fixed between comparisons. Range kills, retries, time and refusals are
the live outcomes; no success on this task establishes escape, routing or team
support. Sparse or constant predictions must remain visible in both offline
metrics and the actual accepted-start trace.

## Legacy checkpoint disposition

Keep the existing binary checkpoint as a **legacy synthetic diagnostic** with
its original `idle/engage` meaning. Before enabling the new mode, root should
explicitly revoke deployment eligibility of `rivals-range-options-v1`, pin the
new format/semantic revision in load and external deployment binding, and test
that old checkpoints/receipts reject. Preserve offline loading for historical
diagnostics if needed. Class 0 is never reinterpreted as movement, scanning,
per-ability silence or tactical patience. This document itself changes no loader
or receipt and grants no deployment approval.
