# Live-loop safety and pending rebind: v2 delta

Owner: live-loop. Issue: [VUH-1319](https://linear.app/vuhlp/issue/VUH-1319).
Reviewer: live-review w2:p3E, routed by the lead. Offline preparation only;
independent delta review pending. No map acceptance or live demonstration.

This supersedes the v1 safety and integration bytes for review. The v1 packet,
review and receipt remain immutable. The prior FIX receipt is
`../live-loop-safety-rebind-20260929/review-v1-receipt.json` (b8711867...).
`delta.diff` contains only the active changes since that review; `safety.diff`
contains the cumulative safety changes against HEAD. `integration-delta.diff`
shows changes to the deferred patch, which remains unapplied.

## Review findings addressed

- **L1:** LiveIO.scoreboard opens a bounded latch exemption on LiveSafety and
  closes it in finally. A negative range proof remains false, but does not
  permanently stop the device during the native scoreboard return wait.
  The window lasts at most hold_s + RETURN_S + 2*FRESH_S (hold + 1.7 seconds),
  capped by the scope deadline. Native Live still refuses a false initial
  range proof before BACK and still enforces its 1.5 s return timeout. Failed
  native transitions latch range_lost. Focus, takeover, deadline, idle and
  reader errors remain immediate stops throughout; no proof is promoted to true.
- **L2, confirmed by the lead:** scripted, Jev and learned live modes lose the
  former 0.25 s one-false-frame HUD grace. One negative HUD proof stops them
  permanently outside the bounded scoreboard transition. This implements
  AGENTS.md's stop-when-HUD-disappears rule. Offline replay behavior is unchanged.
- **L4:** owner-tests.txt now records the exact command, environment and result,
  including tests/test_episode_collection.py.
- **P1, pending patch:** --camera-map has no live default. Even pose-only needs
  an explicit map; --camera-settings-match PROFILE records the operator's
  assertion that current game settings match that reviewed profile. It is not
  automatic pixel verification. Legacy 265/75 is never implied for alt 247/124.
- **P2, pending patch:** agent/camera_acceptance.py introduces a code-reviewed
  profile -> (acceptance record path, SHA-256) trust registry. It is EMPTY.
  Neither profile has live acceptance. A future independently reviewed entry
  must point to a rivals-camera-acceptance-v1 record with scope
  controller_complete, profile, map_sha256, settings, and a nonempty evidence
  path -> SHA-256 mapping. Every byte pin and settings match is verified before
  hardware. A JSON map's own accepted strings cannot add a trusted entry.
  Candidate/missing point checks remain enforced even for a trusted record.
  The run receipt retains map hash/settings plus acceptance record/hash,
  evidence pins and operator declaration. Review of the whole completed map,
  including its measurement provenance, remains the acceptance owner's task.
- **P3, pending patch:** all five map-derived timed turns are validated before
  attach and bounded locally to at most four times legacy duration. Startup
  positive/negative each <=1.2 s; search up/down each <=7.2 s; disengage
  <=720/415 s (~1.735 s). Every turn is checked again when computed. Derived
  durations and the factor are in run metadata. Scope and startup deadlines
  remain independent limits. No duration is silently clamped.

## Ownership and remaining callers

Only agent/loop.py and tests/test_loop_safety.py changed in the active runtime
and tests since v1. Prior owned safety test changes are carried unchanged.
The lane note was updated after an LF/CRLF hash search found no pin. No other
lane source or test was edited. calibration-pins.json checks all nine files
against the current camera-pitch receipt: all match. The legacy/alt map data
and loader remain commit 3355601. RX +0.45 stays candidate; no acceptance is
inferred from this patch or its synthetic review fixtures.

**Bridge owner (VUH-1316): agent/session.py must pass an explicitly guarded Live before the bridge is enabled.**

**L3 known gap, outside this delta:** scripts/range_cast_probe.py:324-347 uses
LiveIO/Loop with focus, HUD and deadline checks but lacks human takeover and an
independent monitor. Its owner must route it through the guarded scope before
its next live use. The lead routes that separate fix. It was not edited here.

Placement/menu callers stay out of scope. agent/placement.py:33,92 and
docs/lanes/reentry.md:263 retain 172 deg/s at .45 and focal 465 (930 at 2560).
Placement is deployment-pinned and needs re-measurement/re-freeze after map
acceptance; scripts/place.py and scripts/reenter.py also duplicate constants.

## Verification and limits

- Active safety suite: **345 passed** in the shared torch/numpy/cv2 environment;
  **336 passed, 9 skipped** in isolated stdlib. Exact commands are in
  owner-tests.txt and stdlib-tests.txt. All inputs are synthetic.
- New real-Live tests cover scoreboard fade 0/.05/.2 seconds, a fade exceeding
  RETURN_S, focus/takeover/deadline/idle/reader-error stops during the fade,
  local window expiry, invalid window durations, and finally cleanup.
- Deferred integration: **229 passed** in each environment, plus **1,500 exact
  legacy pad reports and camera states** against the pinned controller.
  verify_patch.py validates pre/postimage hashes and applies only to disposable
  files. Coverage includes acceptance tampering/missing artifacts, explicit
  selection/settings, slow maps, signed startup, metadata and imported CLI
  cleanup/stop-path tests with explicit synthetic admission fixtures.
  This is a targeted integration suite, not the prior 521-test combined run:
  unchanged old CLI fixtures omit the newly required map arguments. Active
  safety tests still run in full, including episode collection.
- Scoped Ruff passed for active delta and disposable patched sources/tests.
- No broad-suite rerun for this localized follow-up. Reuse v1's full stdlib
  baseline and the separate baseline-triage-20260929 packet (commit ea52fc1):
  45 pre-existing IDs, 3 stale tests, 8 environment/order, 34 denylist re-pin
  integration failures. Zero test/source fixes were permitted after pin checks.
  Three stale denylist consumers fail CLOSED; the replay-HUD corpus glob is a
  marker-rule violation, not a sealed breach under the lead's directory audit.

Tests demonstrate software behavior with fake capture and pad, not actual game
fade timing or physical release latency. No live game input or desktop operation
was performed. The monitor still depends on host scheduling and a native pad
write that blocks while holding its lock can delay close.

## Next consumer

Lead routes this frozen packet to the same reviewer for delta-only review.
Pending controller/startup changes require whole-map acceptance, application,
exact-byte review and a new deployment freeze before live use; checkpoint
698d8831's old deployment binding is not carried forward. The trust registry
must be populated only with the independently reviewed whole-map record.
The active safety delta remains uncommitted pending review. VUH-1319 remains
safety preparation produced; calibration acceptance and the brief live
compatibility check remain outstanding. The lead owns Linear reconciliation.
