# Near Galacta slot 01: recorded policy diagnosis

The immediate reason for zero firing is **zero model start proposals**, not a
start suppressed by confidence, ammo, timing, or the executor. This identifies
the observed mechanism; it does not identify which feature caused the GRU output.
No inference, checkpoint load, training, media inspection or runtime imports were
needed. Native target identity, readiness, damage and KO findings remain F's audit.

Inputs are the finalized `galacta-pilot-20260922-01-learned` JSON, exact loader/setup
receipts, admitted request `examples.json`, and original Windows fit report. All
input hashes before/after are in `receipts.json`. `report.json` retains numerical
source features, actual runtime decision locators and matching box candidates.
Original files are unchanged; this report issues no labels or approval.

## Where firing stopped

| Accounting unit | Actual result |
|---|---|
| Episode | `max_time`, meta 19.999 s, 1,104 normal ticks |
| Unique persisted decisions | 199: 194 model events, four warmups, one initially unobserved target |
| Model proposals | 194 `no_new_start`, **zero `start`** |
| Start probability | min 0.022576, median 0.117267, max 0.192764 |
| Confidence refusals / invalid history | 0 / 0 |
| First executor consumption of model decisions | 182 `no_new_start`; 12 `target_missing_or_ambiguous` |
| Accepted pulse owners / returned LT / returned RT | 0 / 0 / 0 |
| Normal guarded sends | 1,104 returned; no failed send |

The maximum start probability was decision 6 (State.t 8.035115300), the first
model event. The minimum was decision 68 (14.226116800), in an ambiguous-track
interval. The winning no-new confidence was always at least 0.807236, above the
unchanged 0.7 gate. Lowering that confidence gate would not change these recorded
argmax choices. There is no basis here for changing it.

Later reflex ticks include 512 `decision_expired` and 315 `duplicate_no_new_start`
results. Those are repeated consumption of existing decisions, not 827 missing
start proposals. The 12 ambiguous first consumptions are decisions 64–69 and
166–171. Each State contains four or five boxes sharing selected track 1; their
actual State clocks and boxes are retained in the report. These are a secondary
selection/execution issue, not the cause of zero upstream starts. All 194 model
decisions name track 1; this does not prove continuous physical identity.

Every model State and immutable request resource observation has five webs, full
250/250 HP and the original matching State.t. No start-specific ammo/aim/deadline
acceptance was exercised. Thus the report does **not** claim that a hypothetical
start would have passed those guards.

## Measured feature support

The admitted source is **five TRAIN labels: four no-new controls and one received
request**, with 103 unknown coverage rows excluded from this comparison. The
25 history-snapshot occurrences overlap; they are not 25 independent examples.
The original fit report predicts all five training labels, including start
probability 0.995263 for grid 141. That is training fit, not validation.

| Actual feature | Runtime | Admitted histories / sole positive |
|---|---|---|
| Web ammo | 5 at all 194 model anchors | 0–3 across histories; positive always 3 |
| Target height / frame height | 0.316–0.381, median 0.351 at 182 uniquely recoverable anchors | 0.058–0.286 overall; positive 0.201–0.286 |
| Target center x / width | 0.487–0.515, median 0.499 | Positive 0.465–0.513; 181/182 runtime anchors within its marginal range |
| Target center y / height | 0.527–0.647, median 0.557 | Positive 0.607–0.687; 180/182 outside its marginal range |
| Target tagged | False for every matching runtime candidate | Positive selected snapshots: true, true, unknown, true |
| HP mask | Full HP known at all 194 anchors | Positive includes one unknown-HP snapshot |
| Pull / uppercut / swing ready | All true at all 194 anchors | All true in positive history |
| On-target / target distance | Unknown | Also unknown in admitted examples |

Geometry is excluded for the 12 ambiguous anchors: a logged track ID cannot
identify the exact selected box there. No selector reconstruction was attempted.
There are 170 consecutive five-anchor windows with unique recorded boxes and
actual clocks satisfying the 25 ms geometry, without reconstructing warmup
selection. Their selected targets stay present, HP known, ammo five and tagged
false. The positive's first snapshot has no selected target (the source's recorded
window-local selection), then four selected targets; its masks and trajectory
must not be silently replaced by a continuously tracked runtime history.

These comparisons use the 26 value/mask feature arithmetic in the hashed
`policy/range_policy.py`. Source and runtime preserve their different perception
identities and the same selector/feature revisions. Bot name, raw pixel size,
swing charges and ult readiness are not direct features. Box geometry, readiness,
resource values and masks are. The measured larger boxes and full ammo are outside
the admitted numerical support; neither establishes a learned prohibition.
Source grid 137 also has three webs and tagged targets yet is a no-new control,
so even those shared values do not define a firing rule.

## Smallest next comparison

Use root's already planned fixed mid pair: compare its **recorded** normalized
box geometry, target/HP/tag masks, ammo/readiness and unchanged head probabilities
against this near slot. This tests whether outputs change when geometry moves
toward source support while full ammo and untagged state remain comparable.
If starts occur with those latter values, they are not an absolute learned veto;
if not, geometry alone remains unproven. Different scenes still prevent causal
feature attribution. Do not change the model, labels or threshold based on this
one run, or report a generalization failure rate.

Reproduce from repository root with:

```powershell
uv run --offline --no-project python -B data/diagnostics/galacta-slot01-policy-20260922/analyze.py
```

The script reads only the explicit allowlist, projects JSON features with stdlib
arithmetic, and writes only this directory. It does not follow evidence links or
open a checkpoint. No counterfactual firing, damage or kill is inferred.
