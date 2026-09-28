# CPU synthetic verification before source freeze

Windows, torch 2.14.0+cpu, BelowNormal, two torch threads. No corpus, sealed data,
GPU, model checkpoint, cloud call or fit of real data.

- 30 passed: new dropout tests plus existing spatial yaw, trainer and metric tests.
- After adding the actual shakedown exercise, all 10 dropout tests passed in 2.65s.
- Ruff passed on changed production/test files.

Checks cover unchanged 201,187 parameters and state-dict keys, identical seeded
initialization and zero residual; train-only stochastic dropout and deterministic
evaluation equal to the original operations; frozen base weights/gradients and
exact action/pitch outputs through optimizer steps and serialization; refusal of
unapproved grid/dropout combinations; and the real shakedown optimizer on small
synthetic CPU batches. Existing tests cover tiny fit/evaluation/reload, completed
stage replay and partial-stage refusal, stride64 schedule, sample alignment,
metrics/retention and source-bridge corruption refusal.
