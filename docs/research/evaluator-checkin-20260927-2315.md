# Outside research check-in, 2026-09-27 23:15 CDT

Read through 23:17 CDT. This updates the [22:30 check](evaluator-checkin-20260927-2230.md)
and the intervening exploration/reuse discussion and IDM launch recommendation.
No new compute, dispatch, raw corpus access or schedule was authorized here.

The main decision is now concrete: operations parked further custom yaw-head
variants and launched the expanded IDM refit. This is a sensible allocation
after the completed regularization test, while preserving the pretrained-policy
alternative for a later model decision.

The [dropout result](../evidence/nitrogen-yaw-dropout-20260928/results-01/INTERPRETATION.md)
completed all three seeds at the fixed 26-epoch endpoint. Mean yaw MAE is
1.885650 degrees, against 1.908168 for the matched residual control, 1.772851
for the frozen base and 1.735184 for zero motion. Dropout improves the control
by 1.18% but remains worse than the base in every seed, on left/right turns
and still-frame false turns too. Buttons, movement and pitch are exactly
retained. The declining cumulative TRAIN loss and rising dev camera CE remain
consistent with overfitting; they do not identify insufficient data as the
unique cause. The partial 8x8 run still has no completed endpoint MAE.
The campaign cost bound is $2.550702, below $6.25; yaw campaign bounds total
$21.217211 with no active holds. These are not provider invoices.

The [IDM full02 launch](../evidence/idm-expanded-full02-launch-20260928/report.md)
records one app created at 23:12:22 CDT, with the unchanged three-epoch recipe
on eight TRAIN ranges and three admitted matches, 181.89 counted minutes.
Two existing range-dev sessions remain the evaluation sources. Additional
admitted night matches are not silently added to this frozen run. Timing02
measured 6.777766 updates/s; the total work projection is 27,930.559 seconds
before the 30% margin, including about 6,692 seconds of post-fit inference.
The resulting full-run reservation is $26.288839, under the $26.29 cap and
newly authorized $40 lane allocation. The forecast is an overnight envelope,
not a measured completion time or accuracy result.

The [short bottleneck analysis](../lanes/idm-timing02-bottleneck-20260928.md)
found synchronous sample construction and transfers but no recorded CPU/GPU
time split establishing a specific fix. Stores are already decoded uint8.
Operations followed the evaluator recommendation: finish that analysis, skip
the speculative extra probe, and run the properly funded baseline. This
avoided turning a potentially useful optimization into a new prerequisite.
The owner's completion and allocation-alert watcher is armed. The result will
compare camera error and press precision/recall/coverage with pinned older
reports, disclosing the old MPS/new CUDA boundary and checking denominators.

The [full-policy adaptation assessment](nitrogen/policy-adaptation-vs-heads-20260928.md)
landed at 57a5253 and is on VUH-1346. It distinguishes our encoder experiments
from adapting NitroGen's pretrained action policy. It also corrects the old
memo's model-card assumption: retained checkpoint metadata records action_dim
25 and horizon 18, with 16 inference iterations. Exact tokenizer layout and
cadence still need resolution. Full-policy latency, current pad calibration
and total training/integration cost remain unmeasured. No training or live
launch follows from this paper assessment.

Current Linear comments agree with the owner receipts: VUH-1346 records the
negative dropout result and parked yaw line, plus the adaptation paper;
VUH-1353 records full02 running and explicitly retains the Gate 2 boundary.
No new live-controller result was reported in the inspected delta. No fresh
recording or calibration request was made to James.

One advisory went to steering after checking identity and the empty composer.
Broader supervision is a reasonable next bet, but the approximately 50-hour
archive is a candidate pool before source/support cuts, and refitting alone
does not establish usable labels there. The existing
[Gate 2 plan](../lanes/idm-gate2-plan-20260926.md) explicitly permits camera-first
qualification without waiting for the seconds-context button head. If camera
transfer qualifies while presses remain weak, camera-only supervision could
advance yaw learning, with uncertain action targets masked rather than
converted to neutral. Keep qualification per output so one weak channel does
not unnecessarily block every use of improved labels. This is guidance for
the next result interpretation, not authorization to open sealed data or label
the archive now.

The next useful uncertainty is the expanded IDM's measured label quality and
coverage, followed by transfer under the existing protocol. No new literature
sweep or experiment was needed to make this check's decisions.
