# Bounded intent/target audit — EXPLORATORY, $0

Question: when James starts a horizontal turn, what is he turning toward, and
is that destination identifiable from the visual past? This follows section 3
of `docs/research/recent-ai-research-20260927.md`. It creates diagnostic
annotations, not admitted training labels, a new model or a live controller.

Use only the three previously admitted TRAIN sessions explicitly listed in
`docs/research/nitrogen-yaw-audit/audit.py` (200129, 203745, 035932), through
their existing admission, split and current denylist checks. Read their frozen
step metadata first. Never enumerate or open other recordings, sealed payloads
or frozen-dev images. Reuse admission media hashes; do not rehash whole videos.

Select 12 events before decoding: four per session, two left and two right.
An event starts a 0.5-second window with absolute net requested yaw at least
10 degrees and at least 80% directional consistency (absolute net / sum of
absolute yaw), preceded by 0.5 seconds with at most 2 degrees total absolute
yaw. Require accepted, normal, gap-free, relative-known rows in a continuous
run spanning -1 through +2 seconds. Use the actual header step period.
Pick the first and last qualifying event in each direction, enforcing at
least 10 seconds between events. If a cell lacks two events, report the shortfall;
do not relax thresholds or replace it based on its pixels. This is a balanced
diagnostic sample, not a population prevalence estimate.

Pin selected row indices, exact PTS, source metadata hashes and yaw summaries
before opening pixels. Decode only six selected frames per event at
-1, -0.5, 0, +0.5, +1 and +2 seconds. Native frames are retained; contact sheets
are for navigation. Verify exact PTS, dimensions, timebase and frame composition
at or before each row anchor. CPU only, BelowNormal/niced, two decoder threads,
under 3 GB; no game input, inference, refit, cloud launch or paid compute.

First inspect only t<=0 panels and freeze `causal-annotations.json`: visible
bot candidates, whether a unique plausible destination can be identified,
visibility/occlusion and uncertainty. No human future yaw labels or future
panels are supplied during this pass. These are visual observations, not a
tested causal planner or deployable target labels.

Then inspect t>0 panels and record separate `oracle-annotations.json`: apparent
acquisition, engagement/tracking, traversal, disengagement or unknown (overlap
allowed); target category and whether its identity can be linked back to the
causal panels. Never infer intention solely from the nearest bot, and never
force an offscreen destination or an ambiguous kill/combo into a definite label.
Future frames/outcomes and human commands are oracle evidence only.

Report per-event evidence, class counts, causal ambiguity versus hindsight
resolvability, and concrete failure examples. Do not claim intent causes the
yaw error without a later controlled test. Any causal input proposal must be
observable at decision time and must address visual feedback from the model's
own actions. No model or annotation is promoted to training in this audit.
