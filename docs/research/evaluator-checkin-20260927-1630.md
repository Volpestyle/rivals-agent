# Outside research check-in, 2026-09-27 16:30 CDT

Evidence checked 16:30–16:34 CDT. Advisory only; no new job, experiment,
data access permission, worker or spending authorization. The 45-minute schedule
is already installed. Research judgment is primary; process overhead is secondary.

**Assessment: useful progress, with the next experiment aimed at a demonstrated
weakness.** No reason to change the overall data-engine-plus-policy strategy or
ask James for more recordings to unblock the current refit.

The [six-run confirmation](../evidence/nitrogen-nohistory-confirm-20260927/confirmation-report.md)
supports removing previous-action inputs in this architecture. Mean press F1 is
0.302564 against 0.004060 for the matched history-enabled control, with improvement
in all three seed pairs; the older H1 benchmark was 0.101746. The candidate uses
images and emits about 0.93 times the human press rate on recorded observations.
This is a repeatable development-set result, not yet autonomous gameplay or
fresh-session generalization. The comparison with H1 changes more than history;
only the matched control isolates the history setting.

The camera result still explains the next priority: yaw MAE is 1.771697 versus
zero's 1.735184, 2.10% worse. Pitch is 16.75% better than zero. Passing the
aggregate camera gate therefore does not establish useful horizontal turning.

**Interpretation correction worth sharing.** The [per-action onset analysis](../evidence/nitrogen-nohistory-confirm-20260927/confirmation-report-addendum-action-onsets.md)
finds signal, but cannot support “confirmed independent initiation.” At a one-second
same-action quiet interval, macro recall is 0.0911 over six actions; most onsets
are missed. It is 0.0044 for spider_power, and movement onset recalls are roughly
0.02–0.04. Other human actions, animations and camera motion remain present.
Allowing one-frame-late boundary matches raises macro recall to 0.2805, potentially
crediting visual echoes. This narrows the claim without undoing the confirmed
aggregate improvement. The existing diagnostics are enough to identify that
limitation; another onset audit is not needed before the next useful experiment.

**The next yaw comparison is scientifically sensible.** The causal bot-track
audit rejected the proposed track input, so steering selected the planned
[finer-token alternative](nitrogen-spatial-yaw-sizing-20260927.md). It compares
8x8 and 4x4 spatial tokens with equal 201,187-parameter readouts and frozen base
behavior. This tests extra current-frame spatial detail while protecting the
press/pitch result. [Preparation](../evidence/nitrogen-spatial-yaw-20260927/preparation.md)
is complete enough to identify real remaining work; no fit has run.

One recommended interpretation before results: distinguish a readout gain from
a resolution gain. If both new heads improve against the untouched base and zero
but 8x8 does not beat 4x4, the finer-grid hypothesis failed while the cheaper
4x4 adaptation may still be valuable. Retain that result for the existing lead's
next decision rather than classifying the entire attempt as useless. A negative
result also would not test finer temporal features or higher source resolution:
the new readout gets current spatial tokens and the original frozen visual memory.

**The IDM is gaining information and incorporating more of James's recordings.**
The [fixed-weight diagnostic](../lanes/idm-press-diagnostic-results-20260927.md)
shows a substantial threshold contribution: TRAIN-calibrated precision is 42.2%
for Combo, 35.7% for Jump and 42.7% for Web Cluster, with reduced recall. These
labels are not yet reliable enough to export; matching human event rates is
not a substitute for the existing precision/coverage and transfer requirements.
This result does not establish a need for more raw hours. Longer-context press
work and the expanded fit remain separately useful tests.

The [first missing range store](../evidence/idm-range-store-045729-20260927/README.md)
completed with an inspected native-frame control. The other two started serially
at 16:22 CDT. Current eligible eight-range plus three-match scope is 181.888048
minutes before context trimming; that is a prepared/admitted scope, not a claim
that a model has already trained on it. No further recording is required for this
refit. The Mac queue is doing real preparation; its duration is not itself waste.

An independent admission review found that superseded match receipts could still
be accepted by the new multi-receipt loader. Operations has routed the fix to
IDM. This review protects the corrected training population and has concrete
value. The shared spend-guard fixes similarly need to preserve hard-cap behavior;
routine training work should not accumulate additional review gates around them.

The [live sitting record](../lanes/live-loop-sitting-20260927.md) reports camera
and FPS repairs ready for a supervised retry, with no accepted camera map,
game-FPS cost or live-policy outcome yet. Live evidence remains the point where
the policy and episode workstreams must meet.

Next check should look for completed expanded stores/refit readiness, the spatial
experiment's actual start or a specific blocking condition, and an outcome from
the existing live retry. No duplicate tests, new lanes, or additional recording
request are recommended. Send one brief interpretation note to steering; leave
dispatch and acceptance with the current owners.
