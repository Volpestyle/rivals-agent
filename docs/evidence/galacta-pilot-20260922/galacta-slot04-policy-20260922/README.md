# Slot 4 MID: recorded policy comparison

**The unchanged head again proposed no starts.** Early MID geometry overlaps
source height support, but that alone did not produce a start. This is a measured
failure to initiate in these two slots, not a population generalization estimate
or a causal diagnosis of individual features.

| Unique-decision accounting | Slot 1 near | Slot 4 mid → near |
|---|---:|---:|
| Persisted decisions | 199 | 199 |
| Model outputs / no-new / start | 194 / 194 / 0 | 194 / 194 / 0 |
| Warmup / initially unobserved target | 4 / 1 | 4 / 1 |
| Start probability min / median / max | .022576 / .117267 / .192764 | .013501 / .135473 / .154089 |
| First executor result: no-new / ambiguous target | 182 / 12 | 182 / 12 |
| Accepted pulse owners / returned LT / returned RT | 0 / 0 / 0 | 0 / 0 / 0 |

Slot 4 has zero confidence refusals or invalid-history decisions. Winning no-new
confidence is at least .845911, above .7; start probability is always below .5.
The argmax choice, not confidence filtering or suppressed start requests,
explains no firing. Every model anchor has five webs and 250/250 HP. Resource
clocks preserve State.t. This does not establish that a hypothetical start would
pass aim, freshness or other executor guards.

## Actual trajectory and source support

The five admitted TRAIN labels remain four no-new controls and one received-RMB
request (grid 141); 103 unknown rows are not negatives. The sole positive is
not evidence of a full-ammo, untagged first-web initiation: its history has three
webs, selected tags true/true/unknown/true, and one unknown-HP snapshot.

| Slot 4 anchors (actual State clocks) | Height / frame height | Recorded start probability |
|---|---|---|
| d6–18, 8.973411–10.162236 s | .122–.259, all within overall source .058–.286 | .013501–.040378 |
| d16–18, 9.958248–10.162236 s | .211–.259, within positive .201–.286 | .030509–.040378 |
| d19 onward, uniquely identified boxes | .303–.409, above all source history heights | .035192–.154089 |

The first model event is phase age .617 s. The first uniquely identified box
above source height support occurs at d19, age 1.911 s. Thus slot 4 supplies 13
model anchors within overall source height support, then 169 with larger boxes;
slot 1 had all 182 unambiguous anchors above it. Slot 4's maximum start probability
is d30 (State.t 11.367461 s), already near. Differences are observational, not a
controlled causal effect of distance or scale.

No unambiguous slot 4 anchor matches even the positive's joint x/y/height marginal
ranges: runtime target y is .409–.602, while the positive selected y is
.607–.687. Marginal overlap in height does not reproduce its trajectory. All
runtime candidate tags are false and ammo five; all admitted histories have ammo
zero–three. In exact anchors, pull and swing readiness are true; uppercut is true
except one unknown at d26 (State.t 10.964907100). That mask stays unknown and
is not interpreted as an unavailable ability. The positive has all three ready.
On-target and distance remain unknown in both domains, not zero-valued facts.

Of 170 five-anchor windows whose exact selected boxes can be recovered from
consecutive recorded model decisions and original clocks, nine (ending d10–18)
keep all heights within overall source bounds; none keeps all five within the
positive height range. Runtime target-presence/full-HP/tag masks also differ
from the positive, which begins with no selected target. No warmup target was
reconstructed. Decisions 53–58 and 155–160 have multiple boxes sharing track 1;
their geometry is excluded rather than guessed. Those 12 first consumptions
refuse ambiguity, but their model outputs already requested no new start.

## Terminal accounting

Meta classifies the stop `range_lost`, with 19.995 s and 1,097 normal returned
sends. The separate terminal record identifies a scope-deadline check, not a
native finding of range loss: phase begins 8.356855600 s; deadline 28.356855600 s;
final observation is 28.352229400 s (phase age 19.9953738); send check
28.364422000 s is 7.5664 ms beyond scope and records `not_sent`.
Neutral release returns at 28.366786000 s. There is no pulse owner or proposed
LT/RT on that failed final attempt. It is not an additional normal returned tick.
F owns native/outcome and code-join interpretation.

## Minimum next learning step

Stop repeating the same-model diagnostic or tuning its confidence gate from
these outputs. Ask the existing admission owner for a **small natural human
correction packet of a target-agreed Galacta approach and first web request from
full ammo while untagged**, covering the encountered mid-to-near geometry, plus
resource-legal no-fresh-request controls before commitment. Moving/aiming is
allowed; no stationary wait or artificial Idle class is needed. Preserve actual
received-RMB evidence, cast association, five causal snapshots, target agreement,
unknown masks and full continuity. These are requested evidence conditions, not
new labels assigned to either runtime run.

After that review, fit a separate candidate using the original admitted examples
and the correction packet; keep the original checkpoint immutable. Report whether
the new human starts and nearby no-new controls are learned as a TRAIN-only result,
not proof of generalization. Independent human-session evidence remains necessary
for quality claims. One correction sequence can make this targeted learning
experiment concrete; it does not establish how much data will suffice generally.

`report.json` preserves decision/JSONL locators and numerical features;
`receipts.json` pins inputs before/after and output hashes. Source and checkpoint
match slot 1 exactly; runtime receipts are distinct and are not treated as an
unchanged-environment causal control. No checkpoint, media, raw ledger or runtime
module was opened. Reproduce with:

```powershell
uv run --offline --no-project python -B data/diagnostics/galacta-slot04-policy-20260922/analyze.py
```
