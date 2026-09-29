# Compatibility mode v2: retention outside the pulse window

Owner: live-loop. VUH-1319. Same independent reviewer: live-review w2:p3E,
routed by lead w2:p1J. **Offline preparation, uncommitted, delta review pending.**
No game/desktop/pad/GPU use, no whole-map acceptance or live authority.

This supersedes the runtime/test bytes in the v1 compatibility packet for
review. All existing v1 evidence, its FIX receipt and its lane link remain
unchanged. Only agent/camera_compat.py and tests/test_camera_compat.py change
from v1. delta.diff and before/ retain the exact review delta and preimages.

## C1 fix

Synchronous retention now finishes while neutral, before the pulse timing
window. The runner then acquires a new observation, re-matches the locked
identity, and recomputes both axis and command sign from its current pixel
error. The retained frame and earlier error cannot authorize input. If the
fresh observation is already within the deadband, it returns without a pulse.

Only after that work does the runner sample send time and compute the 50 ms
release deadline and 750 ms response deadline. It rechecks remaining phase/
scope response budget and freshness before reserving input. There is no image
write between that timing sample and send_guarded. Native Live still checks
commit-time proof freshness and enforces the release/scope deadlines. The
independent response watchdog and every guard/limit are unchanged.

Pulse records now distinguish proof_t (new observation) from retained_before_t
(the older retained PNG). The retained image is contextual evidence, not the
frame authorizing the command. Observe events retain the fresh proof's boxes
and acquisition timestamp. Response-image and acquisition-image retention can
also age their returned observations; the next pulse always re-observes.
A storage stall can still exhaust a phase/scope budget or lose target identity;
that stops with no additional input, rather than shortening a pulse to fit IO.

## C2 sitting-plan addition: hash preflight

Keep the [v1 bounded check plan](../live-loop-compat-20260929/README.md), with
this step **on the PC immediately before the sitting and before any live
invocation**, after the exact-byte review has passed:

```powershell
uv run --no-sync python docs/evidence/live-loop-compat-20260929-v2/preflight_hashes.py
```

It verifies the actual map/record bytes through the scoped acceptance loader,
including the four pinned evidence files, without capture or hardware:
- Map: 0e062286bd942aad776d719cd5841321b83773ae5b9e4b74ae8443b8795709d9
- Acceptance record: a55979781567808b2b490032759d76e64e6b34fccb4594594c4e50c81a5df7df

Any mismatch is a STOP: report it to the lead. Do not rewrite line endings or
repin a changed file merely to pass. The hashes intentionally identify the
reviewed CRLF runtime bytes. Re-run the preflight if checkout or tooling touches
those files after verification. This hash check grants neither live authority
nor an operator settings attestation; the reviewed run still requires the
explicit profile/settings declaration and all ordinary preflight guards.
`hash-preflight.txt` records a successful offline check of the current bytes.

## Verification and reused evidence

- Updated compatibility tests: **63 passed in stdlib; 63 passed with perception**.
  Exact commands/environments are in stdlib-tests.txt and perception-tests.txt.
- Save costs of 90, 100 and 120 ms all converge left and right; every simulated
  send retains its full 50 ms window and uses a newly acquired proof. New tests
  also cover a direction change during retention and refusal of scope loss,
  stale capture, target loss or expired deadline after saving.
- Slow detection still refuses. The existing budget, late-response, real-Live,
  watchdog, admission and cleanup tests run in that same 63-test file.
- Scoped Ruff passes. No broad-suite rerun: reuse v1's 477/478 affected-suite
  results and 1,500 exact legacy trace for unchanged code. Controller, startup,
  loader, map, acceptance record and all nine calibration runtime pins remain
  unchanged. No data point or acceptance scope changed.

Physical pad latency and actual game convergence remain unmeasured. The v1
review's 73-89 ms native PNG measurement motivated this deterministic slow-save
regression; this packet claims software correctness with fake IO, not a live
result. Lead routes delta-only review; do not land until LAND.
