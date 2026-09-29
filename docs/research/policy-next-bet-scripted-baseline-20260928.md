# Policy direction: reuse the scripted controller and focus on learned decisions

2026-09-28, 19:24 CDT. Outside evaluator, requested by herdr-lead.
Advisory only; no dispatch, live-input or compute authorization.

**Revision, 2026-09-28 21:07 CDT, after James questioned repeating the early
controller work:** withdraw the standalone ten-scripted-encounter campaign as
the next research bet. The early `plaza30` record in
[l4-controller.md](../lanes/l4-controller.md) already reports two KOs in 30 s;
the later Galacta KO is additional evidence. Re-establishing scripted kills
alone does not address the learned policy's yaw or source-label limitations.

The current recommendation is to finish the required current-profile camera
calibration and verify only the changed control behavior with a brief live
compatibility check. Reuse the existing controller and accepted evidence.
Reserve the fuller matched encounter comparison for a named learned candidate
and a decision it can answer. Do not make a new scripted 8/10 result a gate for
policy research or IDM/source qualification. The existing learned-policy
advancement gates remain unchanged; no current calibration sitting is canceled.
The proposal below is retained as the superseded 19:24 recommendation.

**Choose the scripted perception/controller path, with learned replacements
tested against it. The next deliverable is repeatable, current-profile bot
acquisition and combat, not another fit.** This advances the independent
autonomous-episode stream. James's end-to-end learned policy remains the product;
scripted kills do not meet its learning acceptance.

Why this bet now:

- [NitroGen caching](../evidence/nitrogen-vl-cache-20260928/REPORT.md) preserved
  outputs but missed the runtime cutoff. Honor the stop; no further speed sweep.
- The [confirmed no-history policy](../lanes/explore-policy.md) improved button
  prediction, but yaw MAE remains worse than zero. Another fast custom fit needs
  a new, discriminating data/objective hypothesis; speed alone supplies none.
- The [September 23 pilot](../evidence/galacta-pilot-20260923/README.md) contains
  an independently confirmed scripted Galacta KO. It also stopped after three
  allocations because placement needed a human. The learned web head made
  three hits without a KO. These are useful components, not a reliable agent.

The overlooked dependency is [VUH-1319](https://linear.app/vuhlp/issue/VUH-1319):
its latest disposition waits for an end-to-end policy before reviving episodes.
**A scripted comparison can become usable before that policy exists.** It would
separate perception, aiming, actuation and reset failures from learned-decision
failures, and provide the comparison the next policy will need anyway. This is
already one of the two outcomes in AGENTS.md and the learning plan.

There is a real prerequisite: the existing controller is not calibration-free.
`agent/controller.py` explicitly retains its 465 px focal and old 265/75 camera
maps for offline use. Its search re-leveling also contains timed pitch behavior.
Use the current VUH-1384 calibration/profile and the required live-input delta
review/rebinding. Do not revive old defaults or treat today's small-model
12.9 Hz timing result as a measurement of another model. Reuse unchanged accepted
controller evidence; do not rebuild its entire validation packet.

Proposed bounded attempt, through the lead and existing live owner:

1. Allow **at most two hours of additional owner preparation**, separate from
   the already-owned calibration work, and **one 30-minute lead-operated sitting;
   $0 cloud and no training**. Stop preparation if this requires a new navigation
   system or a broad legacy rewrite. Report the missing prerequisite instead.
2. Predeclare **ten 20-second scripted encounters** using the existing scorer
   and recording path, normal cooldowns, a designated bot and starts on usable
   ground. Include visible targets initially left and right of the crosshair,
   with near/mid starts that existing setup tools can reproduce. A bot already
   centered cannot supply the evidence that it turns toward a bot.
3. Keep all ten allocations, including refused, interrupted and unexecuted ones,
   in the denominator. Retain visible acquisition/alignment, designated KO or
   unknown, time, target loss, interventions and reset time. No human aiming or
   combat during an encounter, and no James hand-placement between attempts.
   Lead-operated reset tools are allowed; report their cost rather than claiming
   unattended continuous play.

**Continue only with at least eight of ten designated completions within
20 seconds, demonstrated acquisition from both sides, no scope breach, and
setup/reset fitting within that sitting.** This is a proposed investment test
for the scripted baseline, not a pass of the learned-policy gate. Existing live
stop rules apply immediately. Stop at the preparation/sitting limit or a failed
criterion; no same-sitting tuning, replacement trials or expanding the task to
all-range navigation.

**If it passes:** freeze that baseline. The next learning proposal should make
one controlled replacement at offensive initiation, keeping target selection
and aim identical between conditions. First consider the already-fitted
no-history policy's supported combat outputs, subject to its own runtime and
interface qualification. Compare actual outcomes against the scripted baseline;
do not silently rescue learned offense with scripted casts. This tests whether
the button-learning signal is useful when yaw is supplied by working feedback.
It neither restarts the old web-only milestone nor authorizes a fit automatically.

**If it fails:** end this attempt and identify the first binding failure from
its trace: detection, acquisition/aim, execution, outcome reading or reset.
That supplies the next repair decision. Do not fund another policy on the
assumption that a larger model will repair an unmeasured executor failure.

Keep additional IDM refits/reader work parked for this decision cycle, preserving
full03 and the frozen support artifact. Reconsider at this attempt's verdict or
when a source-qualification prerequisite changes. **IDM resumption does not
depend on the scripted baseline passing**; its job remains trustworthy labels
and coverage for corpus expansion.

The research rationale is established but limited: [DAgger](https://arxiv.org/abs/1011.0686)
addresses errors on the observation distribution induced by a policy's own
actions; [residual control research](https://arxiv.org/abs/1812.03201) demonstrates
combining feedback control with learning. These motivate a usable closed-loop
comparison and staged replacement, not a claim of Rivals sample efficiency or
authorization for RL. Consumer: herdr-lead through VUH-1319/VUH-1384; VUH-1346
keeps the whole-policy learning goal and its existing gates.
