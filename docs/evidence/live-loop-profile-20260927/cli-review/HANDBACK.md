# Separate pre-run review: explicit inference backend in live CLI

Author live-loop. Requested by herdr-lead after inference-only commit 7ca7e16.
Reviewer binds-review. **Not landed; no live use.** Read-only independent review
requested for the two-file CLI/test delta plus its new inference dependency.

`delta.patch`, two source snapshots and `source-hashes.json` name the exact
working bytes. Inference implementation/tests already landed in 7ca7e16;
`agent/live_range_bc.py` and `agent/controller.py` are unchanged.

Changes:

- CPU + original subprocess preprocessing remain defaults. CUDA requires
  `--device cuda`; unavailable CUDA raises, without fallback.
- `--preprocessor inprocess|compact-bgr` explicitly selects the tested
  PyAV/libavfilter graph. Install PyAV 18.1.0 in the selected private environment;
  its FFmpeg build and chosen graph are recorded. No image size is reduced.
- Nondefault inference uses `DevicePredictor`, including batched DINO views.
  The existing supported legacy/CM3 checkpoint loader and distribution checks
  are unchanged. Exploratory H1/SigLIP/NitroGen files are **not** newly admitted
  for live use. Their timing loader remains an offline tool.
- Manifest records device, preprocessor and CUDA runtime/device/capability.
- Review receipt changes to `range-bc-live-review-v2`: it must pin exactly the
  existing three files plus `policy/range_bc/live_inference.py` and
  `tests/test_live_inference.py`. Import-time and current bytes are checked both
  before preparation and immediately before Live creation. Old v1 receipts refuse.

No inference warmup moves a pad; prepare mode remains preparation-only. No
cap, action mask, lease, range/focus/key guard, settle interval, scheduling
requirement or scorecard changed. No pad/capture loop was created or exercised
against the desktop. No accepted camera map or re-freeze is claimed.

Verification: **74 tests passed** in the private environment:
`uv run --no-project --python C:/Users/volpe/AppData/Local/Temp/live-loop-cuda-env/Scripts/python.exe python -m pytest tests/test_live_range_bc.py tests/test_live_pad.py tests/test_live_inference.py tests/test_profile_range_bc_live.py -q`.
All live objects in execution tests are fake/injected. Preparation was tested
with Live replaced by a fail-on-call sentinel for default CPU, both PyAV CPU
choices and explicit CUDA. Existing safety tests passed. Added tests cover CPU
defaults, old-receipt refusal, dependency coverage and no silent CUDA fallback.
Ruff passed on the changed CLI and tests.

Timing evidence/limitations: `../RESULT.md`. Only H1 approached a 33 ms decision;
full replay age is still slower. GPU game-FPS cost is unmeasured. The lead owns
camera maps, re-freeze and the supervised sitting. Camera/scorecard proposal is
in `docs/lanes/live-loop-20260927.md`; its input steps have not run.

Please return LAND or actionable blockers against these bytes, and, if accepted,
the five-file v2 receipt. A receipt establishes code review only; the lead still
owns acceptance and scheduling. No reviewer approval is authored by this packet.
