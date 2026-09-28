# Approved EXPLORATORY 4x4 hidden-dropout candidate

Lead approved one change after the bounded intent audit: residual hidden dropout
p=0.5, same 201,187 parameters, frozen NitroGen no-history base seeds 1/2/3,
existing 4x4 CUDA caches, fixed epoch 26 / 15,288 updates. No early checkpoint
selection, new encoder/grid, data label or partial resume.

All-in new allowance **$6.25**, including three concurrent cheap shakedowns and
three fresh fits/evaluations. Planned holds: probes $1.093761, fits $4.931142,
total $6.024903; $0.225097 unallocated. These six slots are finite, not retry
allowances. Exact accepted rounding must be checked before launch. Current
yaw campaign settled $18.666509, zero active holds; new maximum $24.916509.
Workspace $200 hard/$150 tell-James policy is the lead's separate gate, not
extra lane money.

Launch waits for v1.0.5 reviewer LAND and lead-installed acceptance. IDM's local
disk timing probe creates first; coordinate actual releases and >=15s globally.
New outputs only; input cache volume read-only. No build or extraction required.

Comparator: completed grid4-s1/s2/s3 `-02` residuals, plus their frozen base and
zero-motion baseline. Report yaw MAE overall, left/right separately, false turns
while still, exact action/pitch retention, per-seed/mean differences and all
train/dev curves. `train_chunk_loss` is cumulative through the epoch, not an
isolated epoch average. No claims of intent-conditioning benefit are made by
this regularization experiment.

The rationale and sizing were fixed in
`../intent-target-audit-20260928/next-paid-sizing.md` (9d6468d). Production changes
add only the training dropout operation and authenticated config propagation;
default no-dropout behavior and historical frozen packets remain unchanged.
