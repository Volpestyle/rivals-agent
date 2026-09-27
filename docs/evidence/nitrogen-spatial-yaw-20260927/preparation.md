# Approved spatial-yaw experiment: preparation, not execution

Lead approved the [sizing](../../research/nitrogen-spatial-yaw-sizing-20260927.md):
8x8 versus 4x4, identical 201,187-parameter position-aware yaw residual, frozen
candidate seeds 1/2/3, six 26-epoch fits. **EXPLORATORY, $24 total hard cap, warn at $20.**
The next compute dependency is the shared modal_guard spend-fix LAND plus reviewed
bootstrap envelope, then the six-app concurrent cheap shakedown. No legacy bypass.
The lead reports approximately $48 metered Modal usage and says the new cap fits $100;
that is not substituted for the library's fresh provider query or outstanding-hold admission.

Mac cache preparation is authorized at $0, but the heavy slot is held by IDM's three
serial range stores under `/Users/james/dev/idm-data/range-stores-a730f75` (PID 73044).
IDM says hours, provisionally, and will explicitly release to explore-policy.
**Nothing auto-launches on PID disappearance. No extraction or paid job has started.**

Prepared code:

- `policy/range_bc/spatial_yaw.py`: independent 4x4/8x8 pooling, readout and frozen-base wrapper.
- `policy/range_bc/spatial_yaw_cache.py`: same admitted roster loader and pinned cohort as
  confirmation; streaming verification of actual global/crop bytes, compact original-frame
  IDs, both grids from each tower forward, per-session artifact hashes and final completion
  receipt. Complete sessions may be verified/reused; partial stages are refused, not overwritten.
- `mac-cache-spec.json` and `launch_mac_cache.py`: explicit pinned Mac paths, nice >=10,
  two CPU threads, log/PID/exit/terminal receipts. No Modal imports/calls or video decoding.

The code and tests ran on **PC CPU**, BelowNormal, two threads, with CUDA hidden. Eight
synthetic tests passed. They check spatial geometry and original 4x4 equivalence, equal
parameter counts, zero residual initialization, no base gradients/tensor changes, exact
action/pitch output retention after yaw updates, causal prefix behavior, exact compact-ID
lookup including gaps/repeats, hash corruption, completed-stage replay without inference,
partial-stage refusal and STOP behavior. Ruff passed. The first test run exposed an extra
H1 horizon dimension in the wrapper; it was fixed before the successful run. No dataset was
opened for these tests. Mac MPS extraction and CUDA training remain untested for this code.

Before the queued extraction: export committed code with canonical LF bytes, verify its
archive and per-file source manifest on the Mac, use the existing pinned Mac venv/vision
assets and archived cohort registry/tally, run these synthetic tests on CPU, and check disk
again. A read-only probe found 313 GiB free; the compact cache needs about 99.18 GiB plus
margin. That observation is not a future reservation. Preserve all old outputs and assets.

The model-training driver, requested yaw/false-turn report and shared-guard run packet still
need integration and measured shakedown evidence. Prepared code is not a completed experiment.
The confirmed press result and A3 judge remain unchanged.
