# Bounded pixel compatibility mode ? VUH-1319

Owner: live-loop. Independent exact-byte review: live-review w2:p3E, routed by
the lead. **Produced offline, uncommitted, review pending; no live authority.**
Issue: https://linear.app/vuhlp/issue/VUH-1319. Lead decision: 2026-09-29 16:21.
This is a brief compatibility check, not whole-map acceptance or a campaign.

## Scope and implementation

`agent.loop --compat --live` dispatches to a separate parser and runner. Only
explicit camera profile/settings match, PID, output directory and <=60-second
deadline are accepted. Brain, combat, movement, startup, scoreboard, episode
collection and ordinary loop options refuse before hardware. The runner uses
existing LiveSafety, guarded LiveIO/native Live, outline perception and Tracker
with cam=None. No camera integration, focal, angular prediction, interpolation,
re-levelling, timed degree turn, attack or keep-alive is called.

Each command is a single axis at +/-0.1 for at most a 50 ms reserved actuator
window. Yaw commands must be exact signed measured knots. Pitch uses only the
observed sign (positive RY looks up) at +/-0.1, with no degree-rate claim. Native
Live receives freshness, release and scope deadlines through send_guarded;
its existing lease disarms the command during blocked capture. Every pulse
ends with explicit release. No new pulse occurs until an observation acquired
at least 100 ms after release shows >=2 pixels of target motion toward the
crosshair along the commanded axis (pixels scaled to 1280 width).

Freshness is required before and after detection/retention and at the actuator:
frames <=100 ms old, increasing timestamps, unchanged valid frame size and
valid native-pixel boxes. Target identity is locked through the existing pixel
tracker; missing or ambiguous matches stop. A >=2 pixel opposite response
stops. A per-pulse 750 ms response watchdog closes LiveSafety independently
of capture/perception, and a late returned frame cannot authorize another
pulse. The watchdog is canceled only after a timely observed response; normal
cleanup also cancels it. Response timestamps are observed delays, not a
calibrated or guaranteed latency. Animation, bot movement and pixel tracking
can contribute to the observed displacement; retained frames must be inspected.

Fixed pre-input budgets: at most 40 pulses and 2 seconds of reserved input,
with enough remaining response time before both the phase and scope deadlines.
Acquisition is bounded to 10 seconds per side and convergence to 15 seconds
per side. Frame-dependent phase checks occur on observations; the independent
scope/response guards close the pad even if a read blocks. No further input is
allowed after a phase bound. A blocked native pad write can still delay close;
software tests do not establish physical device latency, and lease/timer
resolution depends on host scheduling. No limit is exposed as a CLI override.

All existing safety checks apply: focus, any key or mouse button, deadline,
fresh range HUD, idle warning, and release. Scope monitoring begins before
attachment. Guard failures are latched. Close/release runs on attach, runner,
frame-retention, result, perception and actuator failures. No scoreboard
transition exemption is used by this mode.

## Scoped measurement admission

`agent/camera_acceptance.py` reuses the deferred patch's pinned-record design.
`YAW_COMPAT_ACCEPTANCES` pins the new
`agent/camera_maps/alt-247-124-yaw-compat.json` record. This is the lead-authorized
scope submitted for exact-byte runtime review: all 14 signed yaw knots
**within their measured scope only**, and pitch sign separately. Runtime
strength is further restricted to +/-0.1. The record pins actual CRLF map
bytes: `0e062286bd942aad776d719cd5841321b83773ae5b9e4b74ae8443b8795709d9`,
matching the evaluator's delivery-receipt.json. The Git LF blob has a different
hash by design and cannot substitute for these runtime bytes.

The record also pins the evaluator README, yaw results, pitch results and
delivery receipt. Focal, all pitch degrees, latency and interpolation remain
missing. The map file and its candidate statuses are untouched. The ordinary
whole-controller acceptance registry stays empty and complete-map loading
still refuses the alt map. The metadata preserves the underlying data-level
live=False alongside the separate compatibility scope, record hash and operator
settings declaration; scoped admission does not promote raw candidate data.

Only the independent admission module was reused from integration.patch.
Controller/startup and the rest of that patch stay unchanged/unapplied. The
ordinary loop behavior remains as landed and gains no authority for an alt
whole-controller run. Its parser rejects --camera-map. Any future full patch
application must rebase its loop preimage and reconcile the now-existing
admission module, then undergo its own exact-byte review.

## Brief live check plan (lead operated, only after review)

1. Lead confirms the approved runtime/profile and sets up the practice range
   with an idle bot left and another right of the crosshair, both visible.
   Inspect the view and start retained native video if needed for the sitting.
   No lobby navigation belongs to this tool. James remains hands-off; any key
   or mouse button immediately stops the check.
2. Run one <=60-second invocation with a new output directory. Example after
   review, with the actual foreground PID and a never-used destination:
   `uv run --group perception python -m agent.loop --compat --live --camera-map alt-247-124 --camera-settings-match alt-247-124 --game-pid PID --max-s 60 --out OUTPUT`.
   The settings argument is an operator declaration, not pixel verification.
3. Acquire the left target at least 24 pixels left (1280-scaled) on two
   successive observations; converge using yaw then pitch. After three fresh
   observations within +/-12 pixels on both axes, acquire a visible right
   target at least 24 pixels right and repeat. No blind search turns occur.
4. **Pass:** both sides converge under the phase, cumulative and total limits;
   every pulse has a timely response and all guards remain valid. This proves
   only compatibility of the bounded pixel controller in the inspected scene.
   **Stop:** no target, lost/ambiguous target, stale/invalid frame, no or opposite
   response, any exhausted budget, any guard failure, or IO failure. Neutral
   and retain the reason. No retry, navigation or fallback is automatic.
5. Inspect result.json and native acquire/pre-pulse/response/convergence PNGs.
   The JSON holds every observed box/timestamp, pulse/release/response event,
   budgets, scoped map provenance and safety status. Report actual elapsed
   time, final errors and observed response delays without converting them
   into camera degrees or guaranteed latency. Setup plus this one check fits
   within a few minutes; a refused setup is returned to the lead.

## Tests and limitations

Affected suites only, following the brief's no-broad-reverification constraint:
- **Stdlib: 477 passed, 9 skipped** (`stdlib-tests.txt`).
- **Perception: 478 passed, 8 skipped** (`perception-tests.txt`).
- **1,500 exact legacy pad reports and camera states unchanged** against
  c34e6c8 (`verify_legacy.py`, `legacy-trace.txt`).
- Scoped Ruff passed (`ruff.txt`). Exact commands and environments are retained.

The suites cover all compatibility budgets, knot admission/tampering, complete
map refusal, target loss, stale/nonmonotonic/invalid frames, slow readers and
retention, opposite/absent/late response, independent response expiry, native
Live integration, preflight failures and post-attach cleanup. The existing
loop safety suite covers every focus, idle, keyboard/mouse, deadline and release
stop path including blocked capture and actuator failure. All desktop/pad/frames
are fake. No game, desktop, real pad, paid compute or GPU operation occurred.
No full repository suite or corpus opt-in was run; prior unrelated failures are
not reclassified by these targeted results.

## Pins made historical by this delta

Exact previous runtime SHA values and both line-ending-form search results are
in before-source.json, pin-search-patterns.txt and prior-pin-records.txt.
- `agent/loop.py`: prior `96bd81b3...77462`. Supersedes that file in safety-v2
  review-inputs.json and review-v2-receipt.json. The old integration patch's
  base-sha256.json loop preimage no longer applies. Existing evidence is intact.
- `tests/test_camera_map.py`: prior `8e0d8437...7955b`. The test pin in
  live-loop-rebind-20260929/receipt.json becomes historical. Evaluator
  camera-map-20260929b/delivery-receipt.json and validation.json recorded the
  old preserved placeholder test and are historical on that field. The update
  now checks all fourteen independent candidates and every remaining hole.
- **No calibration runtime pin is invalidated:** all nine still match the
  camera-pitch review inputs (`calibration-pins.json`). Controller, startup,
  camera map loader and both existing maps are untouched. The already-obsolete
  checkpoint 698d8831 deployment freeze is not renewed by this delivery.

No existing evidence packet was edited. The new packet initially lived under
lanes during preparation and was moved here before freeze on the lead's
clarification. The old frozen lane note is preserved; the new
`docs/lanes/live-loop-compat.md` links this packet.

Lead owns VUH-1319 reconciliation and live-review dispatch: compatibility
preparation produced; scoped exact-byte review and the brief live check remain.
No whole-map acceptance is claimed. Do not land until LAND.
