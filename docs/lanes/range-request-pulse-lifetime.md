# Request-start freshness and owned pulse lifetime

**Root adopted `request-start-owned-pulse-v1`; Controller/Live implementation is ready for F's independent changed-boundary review.** Root owns concurrent Loop/LiveIO integration and joined tests. This is not software acceptance, a binding or live permission. Historical full-press-within-request results remain unchanged; no new human evidence gate was added.

`RequestExample.validate()` in `policy/range_skill_policy.py` labels a fresh received point in `(anchor, anchor+.1]`; cast confirmation is separate evidence. It does not label a complete 33 ms hold inside that interval. The accepted n141 point at +97.984 ms illustrates the distinction without establishing human physical timing. Current Controller requires `execution_t + press_s <= valid_until`, and Loop subtracts `press_s` again when deriving the first-send deadline. Thus the current 67 ms processing budget is an executor choice, not a property of this event label. The accepted third-run median was 71.261 ms, with 19 `insufficient_press_time` proposals; that does **not** prove those proposals would successfully send or cast under another contract.

The previous [semantic review](../evidence/range-request-efficiency-runtime-20260922/preflight/semantic-review.md) and [runtime review](../evidence/range-request-efficiency-runtime-20260922/preflight/runtime-semantic-review.json) explicitly bind action within the original 100 ms authority. They cannot be copied as approval for holding beyond it. Keep source/checkpoint/head/horizon/confidence unchanged; name the new execution interpretation, e.g. `request-start-owned-pulse-v1`, in the existing runtime semantic review and controller manifest, with new exact code/calibration pins and binding after independent review. No new receipt framework or policy semantic revision is needed.

## Fix the pulse origin once

Use **Controller acceptance time A**, not send-return time, as the nominal pulse origin. Existing `accepted` means controller authorization; it does not mean device delivery. Let D be the original request deadline, P=33 ms, and B the earlier of learned-phase and absolute session deadlines. Set nominal end `E=A+P`, effective end `H=min(E,B)`, once. Require `A<D`. Consequently `E<D+33ms`. A scope cutoff may truncate the nominal pulse; it never grants more time.

First actual send must pass the actuator's locked pre-write check at C with `C<D`, `C<H`, fresh proof and the original ammo snapshot still at most 100 ms old. Controller-only ammo validation is insufficient if send/proof/lock waiting ages it out. With the existing exclusive `not_after` API, include `resources.observed_t+.1` in the first-send limit; this conservatively refuses the exact ammo-age boundary too. Keep fresh measured target/aim and all existing refusal gates. Do not refresh resources from reflex HUD.

Delay consumes the allocated pulse: **do not move H to `send_returned_t+33ms` or restart it on a continuation**. A returned first write permits continuation only until the same H; it proves a returned call, not physical onset. If proof reaches D before the first write, neutralize and consume the request. If the write was authorized before D but returns after D, record both facts without inventing a physical timestamp. If it returns after H, release/cancel rather than claiming a completed pulse.

This is a nominal 33 ms executor budget, potentially shortened by computation, transport or hard cutoff. Guaranteeing 33 ms starting from device/game receipt would require a different actuator protocol and unavailable physical timing evidence; it is not recommended here. Existing watchdog resolution and a potentially blocking write still limit physical release precision.

## Minimum implementation boundary

- **Controller `_RangePulse`, `_range_step`, `_range_record`:** retain immutable owner/target, original `request_valid_until`, `accepted_t` and `press_until`; distinguish request expiry from pulse expiry. Remove only the full-press-inside-D condition. Expiry of the current well-formed proposal refuses new starts but does not itself cancel a still-valid owned pulse. Keep terminal ID consumption, shot spacing and hard refusal cancellation. The primitive's existing 30 ms neutral tail may remain as neutral/rearming bookkeeping; it grants no LT authority beyond H.
- **Loop `_send_skill`:** first-send `not_after=min(D,H,ammo_observed_t+.1)`; continuation `not_after=H`, always `release_at=H`. Never subtract P from D. Cap H by both phase and absolute session bounds. Existing single caller must attempt the first write before treating later writes as continuations; any failed/not-sent attempt cancels before another step. Retain release-and-persistence-before-recovery behavior.
- **Live/LiveIO:** reuse guarded writes and monotonic watchdog conversion, but make the hard scope deadline explicit at the locked actuator check (a small optional `scope_not_after` argument through `send_guarded/_commit/_apply` is sufficient). Closed/stale/hard-scope refusal precedes recoverable request expiry and remains `RangeLost`. A composed proof evaluated before lock wait alone cannot establish that the 24-second scope still holds at the write. Continued sends must never renew a lease beyond H or B. No deadline grace.
- **Trace:** preserve request D, controller A, nominal E, effective H and bound reason separately; retain actual send entry/return, first versus continuation, owner ID, cancellation/release/write failures. If recording locked check C, call it `actuator_checked_perf`, not physical onset. Existing `accepted`/`completed` must remain explicitly controller lifecycle terms, never delivery claims. No policy/label/feature change or generic action registry.

## Lifecycle and synthetic acceptance controls

| Case | Required outcome |
|---|---|
| A=99 ms, D=100, proof/locked check C=99.5 | First send legal; nominal E=132; 32.5 ms of budget remains at C. Old contract rejects A. |
| Same A, final proof/lock reaches C=100 | Reject exclusively, release, consume ID. Owning a proposed pulse does not authorize a late first send. |
| A=70, C=90 | E=103 stays fixed; only 13 ms remains. No shift to 123. |
| A=10, C=45 | E=43 already passed: reject even though request D is still fresh. |
| Ammo observation=-5, A=94, C=96 | Ammo aged from 99 to 101 ms: reject at actuator, despite fresh request. |
| A=99, hard scope B=120 | Effective H=120, not 132; hard scope loss cancels, never recoverable request expiry. |
| Identical duplicate / healthy no-new / well-formed expired proposal | No new start; preserve only the same still-owned target pulse to H. Unknown/stale ammo on no-new does not revoke prior valid ammunition authority; malformed/future resource clocks remain hard refusal. |
| New same-target start while busy | Burn/reject the new ID, retain only old owner/end. Never queue it for after release. Shot-spacing and other soft start refusals do not create a pulse. |
| Changed target, conflicting reused ID, malformed state, missing detector, coast/loss, explicit Idle/fault/Disengage, force release or exit | Cancel ownership and release immediately; no substituted attack or resurrection. Target change cannot transfer the old pulse. |
| No new publication | Existing valid same-target decision plus fresh reflex observations may finish its owned pulse; no owner means no attack. Actual stale/missing-observation or fault refusal still cancels; do not manufacture a no-new decision to bypass it. |

The first six rows were initially checked with stdlib Decimal algebra only. The scoped implementation below now covers Controller and Live; root owns the joined fake-device Controller/Loop/Live cases, slow/failed write, cancellation persistence, first-send ammo limits and phase/24-second cutoff translation. Original old-code results and actual trial archives remain immutable. Changed source-test expectations explicitly describe the new active interpretation; there is no dual-mode branch to preserve obsolete behavior.

**Consequence:** fresh starts between 67 and 100 ms become eligible; bounded continuation may cross D, but never its immutable H or hard scope. This removes an avoidable start-timing restriction without promising a usable pulse, cast or better policy. Root retains acceptance and runtime authority; performance work remains independent.

## Controller/Live implementation handoff

Only `agent/controller.py`, `tests/test_range_skill_controller.py`, new
`tests/test_range_pulse_lifetime.py`, and this note were changed. `tests/test_live_pad.py`
was exercised unchanged. No changing Loop/caller source, data, native media or model
was read for this implementation; no runtime/input or environment install occurred.

- `Controller.step` is unchanged. Frozen `_RangePulse` fields retain A, E and the
  original owner D; its mutable steps list only advances the existing primitive.
  `pulse_valid_until` still means D; new `pulse_accepted_t` means A;
  `pulse_press_until` remains E; range traces include
  `execution_interpretation="request-start-owned-pulse-v1"`, including cancellation.
  Calibration accepts only finite numeric `0 < press_s <= RANGE_SKILL_VALID_S`.
- Expired well-formed requests cannot start but do not erase the owned schedule.
  The existing neutral tail may retain busy bookkeeping; it emits no LT after E.
  Malformed/future resource clocks, loss/coast/target switch, mode exit and forced
  cancellation still clear ownership. Rejected/busy IDs remain consumed.
- `Live.send_guarded(pad, *, not_after, release_at, scope_not_after=None)` returns
  None on success. Invalid typed/nonfinite scope raises `Forbidden` after release.
  `_commit/_apply` carry scope to the lock; closed, stale and hard scope precede
  `InputExpired`. The monotonic lease uses the earlier release/scope endpoint.
  Neutral release remains available; failed neutral writes propagate. Legacy
  omitted-scope behavior and public exception classes remain unchanged.

Red evidence before production edits: the initial new selection had **25 failures /
six passing controls**, including late-start rejection and missing scope keyword.
A separate already-accepted-pulse/current-expired-request regression failed while
nine unchanged loss/target/Live controls passed. After implementation, final scoped
verification was **146 passed**:

```text
uv run --offline --no-project --with pytest python -B -m pytest tests/test_range_pulse_lifetime.py tests/test_range_skill_controller.py tests/test_live_pad.py -q -p no:cacheprovider --tb=short
```

Checks cover 99 ms acceptance, immutable A/D/E, expiry without replay, no-new and
busy ownership, hard cancellation, finite calibration bounds, exclusive request
and scope checks, proof/lock delays, closed/stale precedence, malformed scope,
movement scope refusal, failed release, no-scope compatibility and the actual
watchdog loop with a fake clock. `git diff --check` passed. These are scoped
synthetic correctness results, not the independent review or live approval.
