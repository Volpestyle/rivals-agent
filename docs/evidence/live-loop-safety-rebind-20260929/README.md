# Live-loop safety and deferred camera rebind, 2026-09-29

Produced offline for [VUH-1319](https://linear.app/vuhlp/issue/VUH-1319).
Owner: live-loop. Independent reviewer: live-review `w2:p3E`, routed by the
lead. This packet is preparation, not calibration acceptance, independent
approval or a demonstrated live run. VUH-1384 supplies the accepted camera map.

## Changed boundary

`agent/loop.py` now scopes every live CLI mode, including scripted, Jev,
learned, range-skill, episode collection and pose-only. An explicit foreground
game PID and a finite positive duration are required before capture or attach.
It reuses `foreground_pid_guard` and the calibration tool's `human_input` helper
without changing either source implementation. Keyboard taps and holds and all
five mouse buttons count as takeover; synthetic gamepad VKs are excluded.

`LiveSafety` latches the first stop permanently. Focus, human takeover and the
startup-plus-run deadline are checked by a 10 ms monitor independently of
capture or policy work, and again around pixel proofs. HUD loss, idle warning
or reader failure closes the device. Scoreboard opening keeps the existing
recognized board/session alternatives; a failed transition latches a stop.
Native Live retains its fresh-frame proof, serialized actuator and lease.
Cleanup covers attach return, startup, metadata, brain/log/loop construction,
execution, pose-only and normal exits. Release errors are retained and retried;
an unconfirmed close raises rather than claiming success.

Bare `LiveIO()` fails before opening hardware. Explicit injected instances remain
supported for guarded callers and offline tests.

**Bridge owner (VUH-1316): `agent/session.py` must pass an explicitly guarded Live before the bridge is enabled.**

The active source change is confined to `agent/loop.py`. Test changes are
`tests/test_loop_safety.py`, `tests/test_loop.py`, `tests/test_startup.py` and
`tests/test_range_skill_loop.py`. The lane note and this evidence directory are
also owned by this lane. No bridge, placement, menu or calibration-pinned
runtime file was edited.

## Deferred integration and pins

`integration.patch` changes controller/startup and adds camera selection and
metadata to the final safety loop. It is **unapplied**. `base-sha256.json` pins
its exact preimages; `patched-sha256.json` records disposable postimage bytes. The controller/startup hunks preserve the initial delivery;
the loop hunks are rebased onto this safety delta. The old packet at
`../live-loop-rebind-20260929/` remains immutable and its old loop preimage is
superseded for integration by this packet.

`calibration-pins.json` verifies all nine current runtime hashes against
`../camera-pitch-20260929/review-inputs.json`. Relative to the older schedule-v2
receipt, the evaluator independently changed only `agent/camera_calibration.py`
and `scripts/calibrate_camera_schedule.py`; those changes are in his pitch
packet. This lane changed none of the nine. The seven remaining pins, including
controller/startup, retain their earlier bytes.

The legacy and alt maps and loader remain as delivered in commit `3355601`.
Alt RX +0.45 = 154 deg/s is still candidate, with native-count provenance,
151.397–156.473 bounds and unknown symmetric uncertainty. The native count ruled
out the old 77 deg/s alias. Acceptance waits for the whole completed map.
`agent/placement.py:33,92` and `docs/lanes/reentry.md:263` retain their duplicated
172 deg/s and focal constants; placement is pinned by the range-benchmark
freeze and needs re-measurement and re-freeze after map acceptance.
`scripts/place.py` and `scripts/reenter.py` are known duplicated-constant callers
outside scope.

## Verification

- `owner-tests.txt`: **331 passed**, synthetic safety/startup/loop/range-skill/
  episode-collection checks. Includes every stop category, all-key/mouse
  detection, blocked capture, late attach, release failure, permanent stop,
  the actual native actuator with a fake device, and post-attach CLI failures.
- `owner-ruff.txt`: scoped Ruff checks passed.
- `patch-tests.txt`: **521 passed**, plus **1,500 exact pad reports and camera
  states** matching the pinned legacy controller. `verify_patch.py` applies the
  deferred patch only to disposable named copies; no checkout patch is applied.
- `stdlib-patch-tests.txt`: **512 passed, 9 skipped** in an isolated stdlib
  environment, plus the same 1,500 exact legacy comparisons.
- Full isolated stdlib suite after `657020d`: **2690 passed, 138 skipped,
  28 failed, 12 errors**. Every failure/error reproduces on the 8331c45
  baseline. Perception reuse and all 45 distinct pre-existing failing/error
  IDs, including order-dependent cases, are in `baseline-failures.md`.
  No failure caused by this lane remains outstanding.

Reproduce the combined synthetic check with:

```powershell
uv run python docs/evidence/live-loop-safety-rebind-20260929/verify_patch.py --root .
```

Tests establish software stop/release behavior with fake desktop/capture/pad IO.
They do not measure physical release latency or game behavior. The monitor is
subject to host scheduling and the native pad API; existing Live lease coverage
remains in force during blocked capture. No real pad input, desktop operation,
GPU computation or paid compute was used. Corpus tests were not opted into.

## Next consumer and current record

Lead routes the exact-byte safety delta and combined deferred patch to
live-review. Apply controller/startup/map-selection changes only after map
acceptance and review; reconcile the older checkpoint `698d8831` deployment
binding and issue a new freeze before any live run. Keep the narrowed brief
compatibility check in `docs/lanes/live-loop.md`; this is not a KO campaign.

Pending lead-owned VUH-1319 reconciliation/readback: record safety preparation
and this combined packet, replace the previous missing-wrapper implementation
action with independent exact-byte review, and retain full-map acceptance,
deferred integration, deployment freeze and the brief live compatibility check
as remaining work. Direct workspace Linear tools were unavailable here; no
account connector was substituted. The lead relays the bridge requirement.

The safety delta is frozen in the working tree for independent review, not
committed or authorized for live use. The earlier data delivery remains commit
`3355601`. `review-inputs.json` pins this packet and every owned code/test input;
the mutable lane note is deliberately outside that freeze.
