# Matched yaw fit recovery, authorized before launch

The six original fits all refused `matched window schedule differs` before
loading a base model or constructing an optimizer. The generic batch loader
defaults to stride 48; the original encoder recipe explicitly uses stride 64.
The production correction passes `stride=64` to both TRAIN and frozen-dev
`SpatialBatches`. The 15,288-update refusal remains unchanged.

The regression exercises the actual fit entrypoint through its pre-checkpoint
boundary and compares both loaders with the original encoder's windows. The
12 relevant CPU tests pass, including the tiny real fit/evaluation and completed
stage replay checks. The metadata-only real-cohort proof authenticates the ten
admitted step tables against the completed cache dataset: 4,697 TRAIN windows,
383 frozen-dev windows, length 96, stride 64, batch 8, 26 epochs, exactly 15,288
updates. It opens no pixels, feature arrays, checkpoints or sealed data.

`failed-original/` preserves all six failures, accepted teardown proofs and
settled ledger rows. Each proof was independently revalidated using unchanged
v1.0.4 `lifecycle.validate_proof`; all six apps are stopped with zero owned
containers and no remaining holds. All failures contain the same schedule
refusal. No scientific metric or training checkpoint was produced.

The lead pre-approved this one recovery after these checks and a campaign-wide
cost comparison. Conservative settled amounts: shakedowns $1.302986, both
extractions $1.780898, six failed fits $1.583800, total $4.667684. The unchanged
six-run envelope reserves $14.971080. Their sum is **$19.638764**, below the $20
warning threshold and unchanged $24 hard cap. These are lane reports and guard
bounds, not a provider balance. Prior slots and partial directories are retained;
fresh attempt IDs and output volumes are required. No automatic retry follows.

The matched six-arm science, CUDA image/stack, frozen bases, completed dual-grid
caches and pre-stated metrics remain unchanged. This corrects launch plumbing;
it is not a new exploratory arm or a change to the confirmation judge.
