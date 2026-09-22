# First learned range integration

Lead: w2:p1. Technical plan: [learning-plan.md](../learning-plan.md).
Acceptance/results: VUH-1311, VUH-1346 and VUH-1319 in Linear.

## Accepted software delta, 2026-09-22

Independent `range-review` examined the policy, typed consumer, loop, controller
timestamp delta and regression tests outside the producing lane. Its first review
reproduced two P1 findings: a gate could renew an attack before missing-observation
or history checks, and one identity conflated source KBM settings with the pad
runtime. Both were fixed by the producer and independently retested. The final
frozen review found no new blocking findings. Lead reproduced the integrated
suite: **169 passed**, isolated CPU PyTorch/perception environment; the shared
stdlib environment was unchanged.

The reviewer additionally exercised the actual CLI, loader, Decider, Loop,
Controller, LiveIO, Live/watchdog and recording writer with synthetic observations
and an injected fake device. Startup navigation and image writing were stubs.
The valid synthetic fixture recorded 13 decisions, nine Engage decisions, zero
keep-alives and final neutral output. A separate uncertainty transition neutralized
all 21 later ticks after 26 earlier attack ticks. These are software checks, not
human training or gameplay evidence. Synthetic metadata used to test the human
loader branch is never a deployable human artifact.

## Caller contract

`python -m agent.loop --brain range` is the bounded candidate path. It requires
an explicit checkpoint, external SHA-256 and source-identity JSON. Live use also
requires separate runtime and deployment JSON files:

```text
--range-checkpoint CHECKPOINT
--range-sha256 SHA256
--range-identity SOURCE_IDENTITY_JSON
--range-runtime RUNTIME_IDENTITY_JSON
--range-deployment DEPLOYMENT_BINDING_JSON
--cooldowns normal --max-s 20 --decision-hz 10
```

Use `--dry RUN_DIR` for a named offline recording or `--live` only after the
actual admission, validation, runtime measurement and independent-review gates.
No genuine human checkpoint or deployment binding was produced by this software
review. Source identity is KBM provenance. Runtime identity separately pins the
observed virtual-pad settings, calibration, controller/selector code, perception
and semantic review. The external deployment binding pins those to exact model
bytes and the source identity. Hash equality cannot prove that current settings
were inspected; the lead must supply actual reviewed evidence.

Loading and compatibility checks precede pad attachment. Range policy runs use
the checkpoint cadence, at most 20 seconds, fresh consumer/history per invocation,
and no scripted warmup or idle keep-alive attacks. Existing range/focus, decision
age, input lease and neutral-on-exit guards remain. A valid retreat can still be
gate-owned; learned choice is only Idle/Engage delegation timing.

Every decision's trace is copied on its producing thread and saved with its
originating State. `meta.json` includes source/runtime/deployment receipts and
the limited capability claim. Wrong cadence, missing runtime binding, wrong
checkpoint bytes and incompatible profiles refuse before capture or pad setup.

## Scoreboard time contract

The existing board row `t` remains the pre-hold request time. New live rows add
`captured_t`, `capture_interval` and `capture_clock`. The interval is the selected
board frame's grab start/return in loop seconds, frozen before range reacquisition;
`captured_t` is its upper endpoint. It does not measure game rendering or the
player's observation. Missing timing stays missing. The episode adapter must
preserve the interval, reject boundary-straddling evidence and never reinterpret
legacy `t` as acquisition. No new automatic readiness or designated-KO reader is
claimed; initial episode evidence still needs native-video audit.

Re-run the changed boundary without game input:

```powershell
uv run --offline --no-project --with torch --with opencv-python-headless --with numpy --with pytest python -m pytest tests/test_range_policy.py tests/test_learned_range_loop.py tests/test_loop.py tests/test_live_pad.py -q
```
