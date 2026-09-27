**Recent AI research for Rivals Agent — outside evaluator, 2026-09-27**

James asked for a deep review of recent Google/big-lab research that could change
our approach. This covers selected primary papers and official releases from
2025 through September 2026, checked September 27. It is an advisory research
memo, not a change to the learning plan, an experiment registration, or spending
authorization. Operations and steering retain their existing roles.

**My assessment:** the direction is credible. The most useful near-term ideas are
better spatial and temporal conditioning, explicit intent, and learning from
corrected failures. Training a large simulator or substituting a reasoning model
for the fast controller is a weaker use of our next unit of effort. None of these
papers establishes that our data or budget is sufficient for professional-level
Rivals play. They provide testable mechanisms, not a guaranteed breakthrough.

**What this review is grounded in**

The local snapshot was refreshed at approximately 15:05 CDT / 20:05 UTC. The
six-run NitroGen confirmation has completed fits and is recovering evaluations
on the Mac after the cloud interruption; there is no confirmation verdict in
the record read for this memo. Keep its judge and decision rules unchanged.

The exploratory seed-0 no-action-history result is promising for buttons:
TRAIN-calibrated press F1 was 0.308382 versus H1's 0.1017458. Camera MAE of
1.185917 degrees beats zero's 1.224645 only in aggregate. Yaw is **worse** than
zero, 1.782815 versus 1.735184; pitch supplies the gain. This is not evidence of
autonomous target acquisition. See the [explore lane](../lanes/explore-policy.md)
and its [existing yaw proposal](nitrogen-yaw-proposal-20260927.md).

The current experiment uses NitroGen's frozen **vision tower**, followed by our
own head. It is not a test of the complete pretrained action policy. Also, the
encoder does not discard all spatial structure: [explore_encoder.py](../../policy/range_bc/explore_encoder.py)
pools its 16-by-16 patch grid into a **4-by-4 regional grid**, separately for
global and crop views. Any finer-feature experiment must compare against that
actual baseline, not an invented global-average baseline.

The [camera analysis](camera-targets/analysis.md) finds an unconditional yaw median
of zero despite only about 19% exactly zero labels. A weakly conditioned median
decoder can therefore score reasonably by hardly turning. This supports a
missing-information hypothesis; it does not establish which information is
missing. The recorded camera labels are requested input degrees, not observed
screen rotation; pitch currently inherits an equal-sensitivity assumption.

The admitted cohort is about 180.57 minutes including 13.64 frozen-dev minutes,
so fit data is about 166.93 minutes. IDM camera inference is useful on paired
range evidence, but press/movement and replay transfer remain unresolved. The
[SSL smoke](../lanes/idm-ssl-smoke-result-20260927.md) used 80 clips/1,280 frames,
not hours of training footage: its predictor losses were worse than copy-last
and it established no downstream policy gain. These distinctions matter when
comparing our experiments to the papers below.

**1. Google DeepMind: SIMA 2 makes the overall strategy more credible**

[SIMA 2](https://arxiv.org/html/2512.04797v1), announced November 2025 with a
December report, fine-tunes a Gemini-based agent on human screen/control data,
then adds reinforcement learning and model-assisted task/reward generation.
Its actor uses images and ordinary keyboard/mouse actions. The paper still
identifies precise motor control, complex 3D perception, memory and long tasks
as limitations. Some evaluation environments provide ground-truth verifiers;
pixels-only acting does not imply pixels-only supervision everywhere.

Our takeaway is a sequence: learn usable behavior, establish independently
checkable outcomes, then improve from attempts. We should borrow bounded task
specifications and curricula before copying model-generated rewards. For us,
“acquire the designated visible target, complete an encounter, reset” is a more
useful unit than “be good at Spider-Man.” A success judge must distinguish
completion, timeout, interruption and uncertainty using our own evidence.

Later, a slower intent planner could set goals while a local learned controller
executes them. That is our architectural inference, not a claim that SIMA 2 is
simply a two-model fast/slow system. No deployable SIMA 2 weights were verified
in this review. DeepMind's [August 2026 games update](https://deepmind.google/blog/from-atari-to-eve-online-building-on-15-years-of-ai-research-in-games/)
extends the research direction to memory, continual learning and developer
partnerships; it does not supply a new ready-to-run Rivals controller.

**2. Meta: V-JEPA 2.1 suggests a concrete camera experiment**

[V-JEPA 2.1](https://arxiv.org/html/2603.14482v1), March 2026, improves dense video
features through prediction on visible and masked tokens and supervision across
layers. The [official repository](https://github.com/facebookresearch/vjepa2/blob/main/README.md)
provides an 80M-parameter, 384-pixel model as well as larger checkpoints. Its
robotics planner is not a twitch controller: Table 6 reports three-second and
fourteen-second planning configurations on an A100. The encoder and the planner
are different things to evaluate.

My inference for Rivals: fine geometry and causal motion may matter more now
than another increase in generic recognition capability. Small bots can become
only a few pixels in the 256-pixel global view; subsequent pooling can further
weaken location cues. Our global/crop pair may help, so this needs measurement.

The existing explore-policy proposal already supplies the first sensible test:
learn yaw from **all** reliable causal bot tracks, retaining visual context.
Do not choose the nearest bot by rule. Its weak bearing correlation with James's
turns already warns that visible proximity is not intended target identity.

If tracks cannot supply reliable information, a separate alternative is finer
NitroGen patch features with a small position-aware readout, comparing 4-by-4
against a preselected finer grid. Keep the backbone, cohort and other action
heads fixed. Finer tokens cannot be reconstructed from the current pooled cache;
this needs a bounded extraction and memory/latency estimate. More tokens also
cannot recover details already lost at image resize.

Only after that diagnostic would I compare the smaller V-JEPA 2.1 encoder.
Video windows must end at the current observation: bidirectional processing of
past frames is acceptable; silently including future frames is not. Its MPS
compatibility and actual game-time cost have not been measured here.

**3. Physical Intelligence: intent and quality conditioning may unlock more of our existing data**

[Pi 0.7](https://arxiv.org/html/2604.15483v2), April 2026, conditions robot policies
on tasks/subtasks, visual subgoals and episode metadata, including quality,
speed and mistakes. Its experiments show that this context can make mixed-quality
data beneficial where undifferentiated mixing hurts. Desired quality can be
specified at runtime. This is a large robotics system, not evidence that a
small Rivals head will reproduce the result.

The transferable idea is unusually relevant: a nearly identical image can
precede “close the gap,” “switch target,” or “escape.” Averaging incompatible
demonstrations can produce a weak action even when each demonstration is useful.
Our missing signal may be intent as well as geometry.

A small categorical intent input is enough to test this hypothesis; we do not
need to introduce a language model. Start with a bounded, human-audited TRAIN
sample of acquisition, engagement, traversal and disengagement contexts,
allowing overlap/unknown rather than forcing all play into one exclusive class.
Preserve source, correction and quality metadata as older or inferred footage
enters the data engine. Do not equate high kill count with high demonstration
quality, or discard purposeful waiting and defensive actions.

Separate two claims. A hindsight intent label may be used for an explicitly
oracle diagnostic: does knowing intent explain the ambiguous yaw? Deployable
conditioning must come from a user command, a preselected encounter goal, or a
causal learned planner. Never score a future target image or eventual outcome
as if the live agent could observe it. Metadata identifies desired behavior;
it does not turn the future into an input.

This refines the current all-data-pretrain/best-data-finetune strategy without
requiring a new roadmap. Unknown IDM labels remain masked; a quality tag cannot
make an incorrectly inferred button label true.

**4. NVIDIA NitroGen: a valuable foundation, with two underappreciated distinctions**

[NitroGen](https://arxiv.org/html/2601.02427v1), released December 2025 with a
January 2026 paper, uses roughly 40,000 hours across more than 1,000 games.
Its action labels come from visible controller overlays. Its complete policy
generates action chunks with a flow model; our current experiment retains only
the visual encoder. Its reported best adaptation gain is not a Rivals result.
The evaluation interface freezes the game during inference.

First, a failed local head would not reject the full policy's pretrained action
prior. Conversely, successful encoder transfer would not validate its motor
policy. The [existing feasibility memo](nitrogen/feasibility.md) already makes
this distinction and records why its official execution harness is outside
our allowed interface. Reuse model components only through our own executor.

Second, input-overlay recordings are a possible additional label source. A
small availability audit could establish whether useful Spider-Man sources
actually show sufficiently complete inputs. A keyboard icon overlay may supply
button edges but no numeric mouse deltas; native pad recordings still need
action-domain mapping. Timing, missing controls and overlays leaking labels
into policy images require checks. This is an option to investigate, not an
assumption that expert paired data is available or permission to bulk scrape.

Full-policy adaptation belongs after action mapping and real-time feasibility
are demonstrated. It is a larger bet than the existing yaw test.

**5. Real-time chunking explains why execution has to be part of model design**

Physical Intelligence's [Real-Time Chunking](https://arxiv.org/html/2506.07339v1),
June 2025, generates the next action sequence asynchronously while the current
sequence executes, constraining the already committed prefix. A
[December follow-up](https://arxiv.org/abs/2512.05964) incorporates execution
delay into training. These methods address flow-policy inference delay and
discontinuities between chunks.

This is not a drop-in replacement for our categorical one-step head. The useful
principle now is to measure observation-to-executed-action age, including capture,
encoding, prediction, scheduling and pad submission. Mean model latency alone
does not establish controllability; stalls and missed deadlines matter.

If a full flow policy becomes the selected bet, adapt its execution schedule
using measured delay. An action prefix already committed by our controller is
available at deployment. It is different from teacher-forcing the previous
human action, which produced a shortcut in our earlier policy. Likewise,
removing human-action history does not mean removing causal visual memory.

The negative H4/H8 categorical chunk trials do not reject flow policies plus
real-time chunking, but they do argue against repeating the same chunk change
without a new explanation. No chunking scheme overrides fresh-frame/range
guards or authorizes holding stale input indefinitely.

**6. RECAP provides a plausible route beyond demonstration imitation**

[Pi-star 0.6 / RECAP](https://arxiv.org/html/2511.14759v1), November 2025, combines
demonstrations, autonomous experience and expert interventions, iteratively
learning values and improved policies. It illustrates how failures and
corrections can become training evidence rather than simply discarded episodes.

For us, the crucial distribution is where our own policy takes the game. A
model that loses a target creates views that may scarcely occur in James's
normal play. More normal-play footage alone may leave that hole unchanged.
Once the bounded controller is usable, short correction sessions from those
actual states could be more informative per minute than more undirected play.

Record the pre-intervention observations, executed controls, takeover boundary,
James's recovery and outcome. Recovery demonstrations must retain the failing
context; extracting only the successful final combo loses the lesson. Start
with supervised correction learning before adding a value learner. Preserve
old competent behavior and evaluate the failures the correction was meant to fix.

Exceeding demonstration quality will eventually require selecting behavior by
consequences, not just matching a single recorded action. Keep objective-specific
scorecards: target completion and time in the range; survival, contributions and
objectives only where those outcomes are actually observable in an authorized
environment. A practice-range policy cannot establish professional match skill,
and the current range contract cannot provide combat-death rewards.

**7. Google Dreamer 4 and Genie: attractive long-term, poor immediate budget bets**

[Dreamer 4](https://arxiv.org/html/2509.24527v1), September 2025, learns an
action-conditioned world model and trains policies in imagination. Its Minecraft
work uses 2,541 hours of paired gameplay; the reported training setup uses
256–1,024 TPU-v5p devices. Single-GPU model inference does not mean inexpensive
model training. A useful detail is separating uniform experience for dynamics
from successful/task-relevant samples for imitation, to avoid an optimistic
simulator.

We can borrow that data distinction now: mistakes and failures teach what
actions do, while imitation needs a way to distinguish desirable choices.
For a future latent dynamics experiment, demand improvement over copy-last and
action-agnostic predictors, then a downstream control benefit. Video realism
or lower prediction loss alone does not demonstrate that alternate actions
have correct consequences. Our tiny SSL smoke does not settle this question.

[Project Genie](https://blog.google/innovation-and-ai/models-and-research/google-deepmind/project-genie/),
January 2026, makes generative interactive worlds accessible. It does not establish
a simulator faithful to Marvel Rivals. Learning a fictitious cooldown, swing
response or damage rule would waste interaction budget even if the video looked
convincing. I would park full generative simulation until actual action-conditioned
predictive validity is the named bottleneck. No new world-model training is
recommended at this stage.

**Other papers that change how we interpret results**

| Work | Useful evidence | Consequence for us |
| --- | --- | --- |
| [D2E](https://arxiv.org/html/2510.05684v1), October 2025 | Generalist inverse dynamics on a large multi-game paired corpus; timestamp-aware next-event prediction and mouse-calibration adaptation | Test event alignment/context and transfer by action family. Delayed visual effects are not immediate button edges. Invisible failed presses can remain unidentifiable. Keep Gate 2 before expert labeling. |
| [Microsoft: world-model adaptation for 3D trajectory following](https://arxiv.org/html/2504.12299v1), April 2025 | Bleeding Edge experiments compare representations and heads under different data budgets; world-model features are not uniformly best in low data | Compare against simple frozen features. Use time to first meaningful divergence and recovery in addition to mean action error. Future reference trajectories supplied in that task are not free online inputs for us. |
| [ByteDance Lumine](https://arxiv.org/html/2511.08892v1), November 2025 | Long-horizon 3D gameplay using visual history, action generation and selective reasoning; thousands of hours of data and substantial multi-GPU training | Support for combining memory with motor control, not a recipe to train a 7B gaming model on our few hours. Reason about goals only as often as needed. |
| [CombatVLA](https://arxiv.org/html/2503.09527v1), March 2025 | Combat reasoning and action prediction, but the game pauses during approximately 1.85-second inference; the paper says pauses were edited out of one demonstration | Its speedup and human comparisons do not establish normal-speed Rivals control. Inspect execution conditions before using a demo as a performance target. |
| [FIERCE](https://arxiv.org/html/2609.18651v1), NTU and collaborators, September 16, 2026 | Very recent specialist-RL preprint using learned progress/failure feedback alongside independently verified terminal outcomes; fixed feedback snapshots during policy updates | Watchlist for later reward learning. A predicted failure score is not automatically a calibrated probability or a valid ranking of untried actions. It is too early to make this the main bet. |

One correction to keep in future summaries: the Minecraft data-size curve in
[VPT](https://arxiv.org/abs/2206.11795) is **neither an upper nor a lower bound** on
Rivals' paired-data requirement. The local IDM feasibility memo's “upper bound”
wording is too strong. Do not turn another game's 10/100-hour observations into
a recording quota for James. Measure coverage, action observability and transfer.

**Recommended sequence, using existing owners**

| Priority | Bounded question and consumer | Evidence that changes the next decision |
| --- | --- | --- |
| Finish current work | Explore-policy's six-run confirmation and operations/live team's current execution work | Existing decision rules; yaw/pitch separately; a replay visualization is labeled offline predicted controls, not agent gameplay. No changing the judge after seeing results. |
| First new camera bet | Operations/steering decide; explore-policy consumes. Use its existing all-bot-token yaw proposal | A small inspected causal TRAIN tracking sample first. Then one matched yaw-head test if the prerequisite passes and a cap is approved. Freeze press/movement/pitch and retain the registered yaw objective initially. |
| Diagnose remaining ambiguity | Steering/research and policy owner: does intent explain errors after geometry? | One bounded annotated TRAIN sample. An oracle-context probe is labeled as such; a causal version is required before any deployment claim. No bulk relabeling before this answers a real uncertainty. |
| Expand useful labels | IDM owner and admission owner | Calibrated accuracy/coverage and replay transfer by action family, with uncertain commands excluded. Longer event context is a hypothesis for delayed effects, not a blanket replacement for the current model. |
| Improve actual behavior | Operations/live and policy owners, once bounded episodes work | A fixed failure set, short human corrections when needed, and repeatable authorized range outcomes. Add RL only under the existing reward contract. |
| Conditional later options | Steering chooses only after the preceding diagnosis | Finer patch readout, V-JEPA 2.1, full NitroGen adaptation, or latent dynamics: each needs a specific failure it can explain. These are alternatives, not four new parallel lanes. |

For the camera test, retain all-frame yaw MAE against zero and the matched
control, but also inspect turn sign/onset, left/right errors, false turns,
target-visible and target-missing cases, and press retention. Compare real bot
tokens with session-preserving shuffled tokens as a diagnostic. If shuffled
geometry does just as well, there is no evidence that meaningful geometry caused
the gain. The existing proposal already specifies most of this; extend it only
where new evidence warrants it.

Offline imitation error also has a ceiling as a decision tool: two different
targets or retreats can both be reasonable. A stochastic/flow head might select
a coherent valid mode while matching James's recorded action less closely.
That possibility requires independently measured outcomes, not a convenient
excuse for bad predictions. Likewise, removing action-history inputs makes two
recorded-image evaluation modes equal by construction; it does not eliminate
the visual distribution shift caused by the policy's own actions.

Repeated exploration on frozen dev estimates development performance, not fresh
generalization. Three seeds on the same footage improve repeatability evidence
but do not create three independent sessions. Keep the existing sealed-data
contract and report those limits without creating new process gates.

**Resource judgment**

The immediate comparison should reuse the chosen encoder, existing demonstrations
and current owners. Spend effort on a small failure sample before paying for
another full cache or fit. No paper supports increasing the cloud cap merely
because its model is more recent. Mac queue/PC ownership and all current caps
remain governed by [compute.md](../compute.md).

The most consequential experiment is the one that establishes that a learned
policy can repeatedly see, turn, approach and fight under its own observations.
That would join the data and episode workstreams and make correction learning,
reward optimization and genuinely different playstyles testable. The literature
helps us choose that experiment; it cannot substitute for its result.

This review created no models, paid jobs, new workers or game inputs. Local
working notes and primary-source claims were checked; the proposed experiments
have not been run. Route accepted follow-up and this memo through the existing
VUH-1346/VUH-1353/VUH-1384 owners and issues, rather than creating a second queue.
