# Evaluation-method novelty audit and empirical prerequisite

**Current result:** the [command-coarsening pilot](command-coarsening-pilot.md)
supplies two hash-verified archived prediction streams and reproduces both
models' historical metrics. Under controlled two-step label coarsening, paired
bounds resolve 7 of 27 action/session comparisons, versus 6 for separate bounds.
All 108 comparisons across four widths contain the known-label difference.
This resolves the export prerequisite for logged commands only. Naturally
uncertain cast effects, useful annotation-cost savings and current-policy
improvement remain untested. The earlier [timing pilot](historical-timing-pilot.md)
is a separate overlapping-forecast experiment, not the same event task.

2026-09-26. This follows the [paired temporal bounds](paired-event-evaluation.md)
and checks full method sections, not only abstracts. The original goal remains
a doctoral-quality improvement direction for the Spider-Man agent. The current
results establish exact reference checks and bounded archived-data pilots,
not that standard.

## Closest methods and precise differences

**Polo et al., NeurIPS 2024.** Their [paper](https://arxiv.org/pdf/2312.04601),
equation 1.1 and theorem 2.1, bounds an expected bounded function over joint
distributions with prescribed marginals. A fitted weak-label model supplies one
marginal; a sample supplies another. They derive convex dual formulations,
smoothed estimators and statistical uncertainty results. Appendix E also tests
model selection and ranking. This rules out novelty claims for performance
bounds, F1 bounds or weak-label model selection. A difference of scores is also
a legitimate bounded function; paired comparison is not outside their general
mathematical scope. Our finite-path uncertainty set, exact temporal matching
and product-state computation are different computational ingredients. We have
no counterpart to their sampling-uncertainty guarantees.

**Schroeter et al., AAAI 2021.** Their [paper](https://ojs.aaai.org/index.php/AAAI/article/view/17145/16952),
sections 5.1 and 5.2, smooths both predicted and labeled event sequences for a
localization loss, then uses a Poisson-binomial count loss to encourage sparse
point predictions. It directly addresses neighboring events merging under
label smearing and problems with causal models. It is a training objective,
not our evaluation optimization. Nevertheless, it rules out novelty claims for
combining relaxed temporal supervision with distinct event counts. Its exact
count assumption must not be imported into positive-only replay evidence.

**Bilen et al., ICASSP 2020.** Their [paper](https://arxiv.org/pdf/1910.08440),
definitions 2 and 3, uses proportions of intersections between detected and
annotated event durations to define relevant detections and covered truths.
PSDS aggregates performance across operating points and accounts for class
effects. It changes the detection criterion to tolerate annotation subjectivity;
our method keeps a declared point-event matching criterion and optimizes its
difference over possible truths. Neither is inherently a superior metric. Their
duration events do not become uncertainty intervals for point-event timestamps
by renaming fields. A numerical comparison must respect the different estimands.

## What survives this audit

**Additional temporal prior art: Zhang, Diao and Immerman, VLDB 2010.**
[Recognizing Patterns in Streams with Imprecise Timestamps](https://people.cs.umass.edu/~yanlei/publications/sase-vldb10.pdf),
sections 3–5, assigns uncertainty intervals to point events and defines matches
over possible timestamp worlds. It gives point-based and event-based evaluation,
memoization, and interval pruning to avoid exhaustive world enumeration. Its
confidence calculation uses timestamp probability masses (uniform by default)
and products across events. The target is pattern-query results, rather than
extremal differences between two detectors' one-to-one F1 scores. Thus neither
interval-time semantics nor avoiding possible-world enumeration is a new
ingredient here. A specific paired-score algorithm could still differ, but a
new application name does not establish that difference as a research advance.
No same-task performance comparison against an adaptation of this framework
has been run.

The Lamiroy/Pierrot imprecise-ground-truth chapter was also located through
the authors' [institutional publication record](https://inria.hal.science/hal-01401034v1),
but its full text was blocked by the provider. It is an unresolved audit item,
not a paper whose method has been ruled out. An OpenReview search lead likewise
returned a browser challenge and supports no full-method claim.

The narrow candidate is an exact finite-horizon algorithm for sharp paired
event-F1 differences, with distinct interval requirements, asymmetric timing
tolerances, bounded missing events and known negatives. It couples both models
to the same possible truth and avoids counting alternative event assignments as
different physical sequences. The synthetic examples demonstrate why subtracting
individual score ranges can be strictly weaker.

This is a computational specialization, not a new principle of partial
identification. In particular, place a probability variable on every admissible
truth sequence, constrain those variables to a simplex, and minimize/maximize
the expected paired score: an optimum occurs at a sequence with extremal score.
That generic finite linear program reproduces our endpoints. The potential
benefit of the DP is avoiding explicit enumeration of every sequence, exploiting
temporal structure. Worst-case exponential dependence on interval count remains.
No runtime advantage over a modern generic solver has yet been measured.

The three reviewed papers do not supply this specific DP in the method sections
examined. That is a bounded literature finding, not proof of universal novelty.
Publication value would require a useful computational or statistical advance
and empirical evidence, not merely different application terminology.

## Project evidence inspected

**Development HUD source now located.** A subsequent read-only inventory found
the existing `hud-scan-samples.jsonl` in admitted development session 171533,
whose commands already have two frozen prediction streams. Both the scan and
step table match their session manifest hashes. The [feasibility receipt](hud-scan-feasibility.json)
records 850 samples, 770 readable ammo values, and 35 adjacent-sample decreases
inside the accepted normal-regime run. All decreases are one count. These are
reader outputs awaiting visual checks, not independently validated cast labels.
The 32 existing review images contain no pair covering both endpoints of any
candidate decrease. The original 2,303,224,685-byte recording exists locally;
its full media hash was not recomputed in that initial inventory. A subsequent
[native-file identity check](hud-native-media-identity.json) read all bytes at
below-normal priority with a 40 ms pause per 4 MiB block. SHA-256 matched the
archived identity `3f8e4087…2126`; file size and modification time were unchanged
across the read. The check took 24.16 s and decoded no frames. The existing
FFmpeg process remained alive afterwards, so endpoint extraction is still
waiting on that resource condition.

This changes the next action: missing same-source observations can potentially
be inspected locally, rather than requiring a new recording or remote training.
At 2026-09-27 01:04 UTC an existing FFmpeg process (PID 5020) was alive, so no
research decoder was launched. After that work is clear, a bounded endpoint
inspection can test the reader outputs, starting with decreases and stable-count
controls. It must preserve native-frame identity and hash-pinned source
provenance. Even correct decreases supply consumption lower bounds when a
regeneration can hide another consumption. Neither complete cast counts nor
command-to-effect equivalence follows. Independent review is required before
any newly generated labels are relied on for training/evaluation admission.

The historical `press-lags.json` also reports a Web-Cluster first-seen range
of 0.0963–1.1019 s over 35 observations; its median is 0.1044 s. Selecting only
the roughly 0.1 s examples would not justify a universal narrow latency bound.
These are observed first-seen delays, not established causal cast latencies.
No paired effect score has been produced from this source.

**Natural-label follow-up after the command pilot.** The four existing
`docs/evidence/replay-hud-20260923/validation-*.json` reports contain 18, 18, 22
and 16 event records across sessions 051828 and 200129. Both
sessions are fitting sources in the interim94 report, whereas the newly
exported predictions are for development sessions 171533 and 205528. The
reports also match HUD observations to logged presses and preserve unmatched
presses; they are not independent complete cast transcripts. Joining these
reports to the new exports would compare different timelines. Reusing their
press matches as complete visible-effect truth would also change the event
contract. Only report metadata was inspected; no additional native media was
opened. These packets do not remove the natural-effect evaluation prerequisite.

The historical [self-fed diagnosis](../../evidence/range-bc-selffed-diag-20260925/fit-selffed-diag.md)
identifies two development runs and several prediction-feed modes. Its two
published `selffed/diag-*.json` files contain arm/checkpoint identifiers, run
metadata and aggregate mode diagnostics. The inspected `diag.py` accumulates
predictions in memory, summarizes them and writes the summary. It does not export
the paired timestamped prediction sequences required here.

The [replay HUD note](../../lanes/replay-hud.md) identifies an `events.json` output
with intervals, lower-bound counts and coverage. This does not provide two model
prediction streams or independently established absence of other events. It also
distinguishes HUD time, inferred cast time and press-time coverage. The event
definitions must be reconciled before comparison. No raw replay or sealed data
was opened during this audit.

The direct workspace Linear tool is unavailable in this session; tracker status
and ownership were not independently verified. An asynchronous request asks
James to identify an existing admitted development export or its owner. This is
a missing-data request, not permission to bypass a restriction or a request for
new recording sessions.

### Broader export search

A follow-up search of published lane/evidence notes located older B0 prediction
exports in [the policy lane](../../lanes/policy.md). The corrected H2 experiment
reports class predictions and timing intervals on overlapping two-second
forecast windows, with baselines and `predictions.npz` artifacts. These are not
automatically a unique event timeline: multiple forecast rows can refer to the
same future event. Counting every positive row as a distinct predicted cast
would change the task and inflate event counts. A conversion needs declared
anchor times, event semantics and a duplicate-resolution rule, assessed against
the original experiment's protocol. The lane already reports no improvement
under its joint gate; this research does not revise that accepted conclusion.

The named `data/experiments/b0-format5` and `b0-multilabel-v1` directories are
absent on this PC. Using the mac-remote skill, a read-only SSH check returned
identity `james` and directory metadata confirming both exist on the Mac. A
bounded `find` yielded no prediction paths; other directory/identity probes
failed to terminate promptly. Their same tool handles were polled, then only
the three local SSH processes created for these read-only probes were stopped
and their terminal exits verified. No training job was launched or interrupted.
Artifact availability and contents were not established, and no media, arrays
or predictions were opened. Directory existence is not empirical evidence.

The same search found inverse-dynamics prediction exports, which concern camera
motion and are not interchangeable with the point-event predictions required
here. The Round 3 idle sidecar is an input/weighting artifact, not a pair of
model outputs. These findings narrow the data request rather than satisfying it.

## Exact empirical prerequisite

### Current export-readiness check, after the frontier implementation

The [frontier result](frontier-event-evaluation.md) resolves practical runtime on
the tested sparse geometry, not the empirical-input prerequisite. A fresh
metadata-only inspection found additional timestamped predictions under local
`data/diagnostics/`, documented in the [hashed readiness receipt](export-readiness-audit.json):

- `range-human-shadow-d-20260922/report.json` has 52 decision records and 48
  inferences, but explicitly describes scripted calibration, one off-policy model,
  and no truth labels or scoring authority. It is not independent human validation.
- The cohort-fit, rehearsal-5 and earlier event-fit Mac reports contain per-row
  probabilities, but explicitly identify training-only numerical fits/reproductions
  with null validation. Their known rows cannot be repurposed as held-out evidence.
- The current Round 3 evidence packet still supplies design/sidecar material in
  the inspected local paths; an idle-weight sidecar is not a prediction stream.
  This observation does not assert that a remote fit has or has not finished.

Only named report metadata and archive member names were inspected. No additional
model, native media, validation/sealed source, or archive member payload was opened.
The previously copied B0 exports remain usable for the historical timing results,
but the overlapping-forecast representation does not meet the point-event contract.

There is no compatible paired development event export among these inspected
artifacts. This is a bounded inventory result, not a claim that none exists
anywhere. The next empirical action depends on a suitable export or its producer;
more synthetic solver extensions cannot demonstrate policy-selection benefit.

### History-only export feasibility

**Resolved for logged-command coarsening:** the [completed pilot](command-coarsening-pilot.md)
uses an isolated cached CPU environment and verified exports from two archived
seeds. Both reproduce their original metrics. Paired bounds resolve 7 versus 6
of 27 action/session comparisons at two-step coarsening, with all known-label
differences contained. This supplies real frozen outputs, but not naturally
uncertain effect labels or a current-policy evaluation. The paragraph below
records the earlier dependency check, not the present execution status.

An archived history-only checkpoint offers a possible CPU-only producer without
image inference. A read-only Mac stat found a 10,232,386-byte seed-0 checkpoint
and development tables of 3,247,674 and 13,522,361 bytes. No files were transferred
in this check. The shared PC environment lacks PyTorch; an offline isolated
resolution failed because the selected `filelock==4.0.4` was not cached. No model
ran and no shared environment was synchronized. The existing loader also opens
frame caches even for history-only models, so a research-only frame-free adapter
would need to preserve cohort, gap, denylist and patch validation. Logged press
edges would support command imitation, not visible cast-effect truth. This path
is not yet a completed export.

The required export contract remains:

- Two timestamped prediction streams for the same declared event type, timeline,
  binning and threshold/tolerance protocol, with model/executor identities.
- Reviewed distinct event intervals and their count semantics. Missing events
  remain allowed unless a count cap is justified; absence needs its own evidence.
- Run/session boundaries and clock transforms, so matches cannot cross cuts or
  compare a command timestamp directly against first-visible evidence.
- Source and code hashes, plus enough provenance to verify development use and
  preserve sealed test/Gate 2 exclusions.

An existing export suffices if it supplies these facts. Aggregate F1 values
cannot reconstruct them. A single successful synthetic ranking cannot replace
the missing empirical comparison.

With that input, the decisive experiment is: does the paired temporal method
resolve more comparisons than separate bounds under the same uncertain evidence,
while containing the fully reviewed difference when that truth is available?
Report unresolved comparisons, annotation cost, runtime and sensitivity to
missing events. Preserve the current evaluator as the declared baseline; do not
change production gates to make a research result pass.

Until this comparison and the remaining novelty review succeed, the honest
status is a tested research candidate, not a doctoral contribution or a verified
policy optimization. Further arbitrary synthetic extensions would not resolve
that gap.
