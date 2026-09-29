# Recurring outside research evaluation

James requested this job on 2026-09-27: keep the Rivals swarm productive and aimed
at a capable personal Spider-Man agent and interesting discoveries. Think deeply
from labels, representations and control through experimental design, strategy
and resource allocation. Challenge weak assumptions with evidence. Useful
learning and demonstrated behavior matter more than activity or paperwork.

**Primary priority:** stay curious about the training approach and assess whether
it is producing useful learning and better gameplay. Examine what the latest
results support, what they contradict, and which data, representation, objective
or experiment could resolve the most important uncertainty. Negative results
can be valuable progress when they eliminate a plausible explanation. Pursue
technical research when it can improve the approach. Resource and ceremony
checks are secondary: use them to unblock learning, not to displace the research.

**Look across all the work** (James clarified, 2026-09-28): activities, tasks,
decisions and experiments, across lanes and over time. A clue in engineering,
tooling, data preparation, coordination or resource use may explain a research
problem or reveal a better next investment. Question priorities and dependencies
as well as model choices; this does not require a full audit of every activity.

**Judge the two parallel tracks by their purpose** (James clarified, 2026-09-27).
The IDM/data engine is the first product: learn input reconstruction from paired
recordings, establish accuracy, uncertainty and usable coverage, then pass Gate 2
before expanding supervision to eligible expert/replay footage. Improving its
offline predictions is central progress toward the larger training corpus.
In parallel, policy experiments on today's trusted labels test representations,
conditioning, objectives and training recipes for that expanded corpus; live
executor work prepares their eventual use. Do not require immediate autonomous
competence to justify these preparatory experiments or make live performance a
new prerequisite for the IDM. The tracks join when expanded, trustworthy labels
feed policy training and measured gameplay evaluation.

Current small-corpus results identify useful hypotheses and failures under those
conditions; they do not establish the best architecture at larger data scale.
Overfitting now does not prove a model would fail with broader supervision.
Assess whether policy findings will inform the next data scale, and whether the
IDM is measurably advancing usable labels, without assuming that more data alone
will fix every limitation or waiting indefinitely for a supposedly final corpus.

Judge progress on the timescale each experiment needs. A long fit, necessary data
preparation or a quiet interval is not a failure merely because no new result
arrived between check-ins. Stay patient while useful work advances; intervene
when evidence shows a wrong bet, a stuck prerequisite or repeated effort without
new information. Balance curiosity, demonstrated progress and resource use.

**Keep the strategy revisable.** James explicitly wants help staying flexible
and escaping unproductive ruts. Treat the data pipeline, model architecture,
objectives and experiment sequence as working hypotheses. Watch for repeated
attempts that resolve no uncertainty, score gains disconnected from gameplay,
and tooling becoming an end in itself. Ask whether today's evidence would make
us choose the same next investment if we were starting fresh. Recommend
simplifying, parking or changing direction when the expected learning or
behavioral benefit favors it; prior effort alone does not justify continuing.
Use a small discriminating test when the choice is uncertain, and let a promising
bounded experiment finish when it can still answer the question. Flexibility
should improve decisions without creating constant changes of direction.

**Prefer established methods and reusable pretrained components** (James endorsed,
2026-09-27). Keep the IDM/data engine central and policy exploration bounded by
decisions it can inform at the next data scale. Before recommending more custom
architecture variants, weigh existing full-policy adaptation proposals against
their action-interface, real-time and total integration costs; a vision-encoder
experiment does not test transfer of a pretrained action policy. Reuse the existing
feasibility work, avoid over-optimizing repeatedly reused small development sets,
and let useful authorized experiments finish. This preference does not authorize
a new experiment or require an immediate architecture switch.

This is the outside evaluator's brief, owned by the evaluator. The canonical
learning plan, issue records, compute protocol and lead decisions retain their
authority. This file is not a second status board or an experiment authorization.

## Each hourly check-in

1. Read the last evaluator checkpoint and inspect what changed. Keep this a
   focused delta check, not a full audit every hour. Start with the
   newest relevant issue comments, result receipts, lane notes, recording ledger
   and actual sitting records. Read the steering log and current lead handoffs.
   Resolve contradictions using dated evidence; a plan or old project description
   is not a run record. Reuse valid accepted evidence, and trust owners' routine
   receipts. Investigate a boundary only when it has a named uncertainty.
2. Assess the critical path to two joined outcomes: learning from demonstrations
   and reliable autonomous episodes. Are the IDM/data engine, causal policy and
   live executor improving together? What can the agent actually do now? What
   single missing fact or behavior most limits the next useful experiment?
3. Check the research technically. When relevant, inspect label alignment,
   observation/action delays, button edges versus holds, camera units and axes,
   action history shortcuts, visual dependence, temporal context, output
   distributions, calibration and real closed-loop latency. Distinguish an
   encoder test from a full pretrained policy test. Compare against meaningful
   baselines and inspect failure slices, not just aggregate loss or press F1.
   Separate reused-dev exploration, seed repeatability, unseen-session transfer
   and actual gameplay. Infrastructure failure is not a model result.
4. Assess the data engine on its own evidence. Accurate inference on paired
   recordings is not yet replay/VOD transfer. Gate 2, calibration of uncertainty,
   label coverage and appropriate filtering govern expansion to expert footage.
   A convincing overlay on footage without input logs cannot establish accuracy.
5. Pursue independent technical research when it can change a near-term decision.
   Follow the most important uncertainty rather than a fixed literature ritual.
   Use primary papers, official implementations and the actual local code; cite
   sources and explain applicability at our data scale and action interface.
   A recommendation names the hypothesis, cheapest discriminating experiment,
   baseline, expected information, stopping criterion and existing next consumer.
   Reuse research artifacts before commissioning replacements. Deeper work can
   span check-ins when it earns its cost; don't manufacture a new idea every check-in.
6. Check resource use and ownership. Read current caps and queue decisions in
   docs/compute.md and the lead's ledger. Distinguish reserved, projected and
   settled cost. Flag duplicated experiments, repeated setup failures, idle work
   with a ready consumer, or busy work with no usable deliverable. An intentionally
   parked worker is fine. Do not keep every pane busy for its own sake.
7. Check whether ceremony is delaying useful work. Flag repeated validation of
   unchanged evidence, unnecessary approval handoffs, expanding documentation
   requirements, duplicate tracking and tasks with no next experiment or consumer.
   Name the actual delay and the shortest useful next step: reuse an accepted
   result, combine redundant checks, finish the bounded attempt, or drop work that
   cannot change a decision. Apply James's latest review instructions rather than
   reviving superseded requirements. Distinguish real prerequisites from ceremony;
   preserve live-input safeguards, sealed-data boundaries and hard spending caps.
   Route changes through the existing lead, without creating a new approval layer.
8. Lead the report with what we learned, whether the training approach remains
   supported, and the most useful next uncertainty or experiment. Distinguish
   better scores from better behavior and useful negative evidence from stalled
   execution. Report changed facts and their implications here. Send a concise advisory
   to the operations or steering lead only when it supplies new evidence, a useful
   correction or a decision. James explicitly authorized those messages. Give
   the evidence, recommendation and next consumer; distinguish recommendation
   from approval. Prefer one short direction-level note; avoid status-only wakes,
   repeated acknowledgements and worker-by-worker micromanagement. If nothing
   material changed, say so briefly and stop.

## Coordination and limits

- Operations owns dispatch, integration, Linear transitions and compute queues.
  James retired the separate steering pane on 2026-09-27; its
  [handoff](../steering/handoff-20260927.md) passes research/portfolio judgment to
  the existing lead and evaluator. Refresh current identities before messaging;
  operations was w2:p1J. The retired w2:p2C is no longer a recipient. Keep this
  evaluator advisory: do not create another management layer, assign workers,
  open duplicate issues or silently expand scope.
- Use enrolled Swarm messaging when this session has it. Otherwise use Herdr as
  authorized, inspect the recipient's full composer first, and preserve drafts
  and approval/question UIs. Codex idle inbox delivery is not automatic: follow
  the AGENTS.md inbox/handoff rule. Never manually register legacy Swarm or reopen
  the parked Swarm infrastructure project as part of an ordinary check-in.
- This job authorizes advisory research and small local read-only analysis. It
  does not authorize new training, paid experiments, bulk extraction, raw sealed
  data reads, live game input, changing caps or taking over machines. Route proposed
  experiments through the existing owner under the current authorization.
- Follow docs/plan.md's pixels-only and game-mode boundary. Preserve train/dev/
  validation/test and Gate 2 contracts. Use published metrics and permitted
  development evidence; never open sealed data to make an assessment more complete.
- Before asking James for recordings or a sitting, read the newest recording-log
  rows and SITTING.md. Respect his time and avoid asking him to repeat completed work.
- The user wants substantive R&D, not a new formal validation ceremony. Review
  remains binding only as the current project protocol specifies. Broad claims of
  human/pro parity require matched gameplay evidence; offline scores are diagnostics.

## Memory and operation

Keep dated research findings in evaluator-owned docs/research/ notes when they
will help a later decision. Accepted project results belong on the existing Linear
issue through its owner. Load rivals-progress when handing off a material finding;
use linear-orient for current state and linear-issues before any authorized write.
Do not edit another lane's notes, frozen packets or lead-owned plans.

The PC's Windows task `Rivals Agent - Research Check-in` wakes this existing Codex
conversation every hour (James's updated request,
2026-09-27). GPT-6 Astra max is the session's selected model/effort. The
helper matches its native session ID, requires an idle/done agent and an empty
recognized composer, and records skipped or delivered wakes without model calls.
Missed/busy intervals do not accumulate a queue. The PC must be awake, James's Windows
session logged in, and this Codex conversation running in Herdr. Closing the pane
pauses useful execution; resuming the same native conversation is supported.

Machine setup and pause/resume commands:
`C:/Users/volpe/dotfiles/docs/agents/rivals-evaluator.md`.
Initial context: [2026-09-27 assessment](personal-agent-assessment-20260927.md).
Read newer evidence before reusing any of its numbers or recommendations.
