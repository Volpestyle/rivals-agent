# Independent exact-byte pre-run review v1: bounded pixel compatibility mode, VUH-1319, 2026-09-29

Reviewer: live-review (Claude Opus 5.5, `w2:p3E`, outside the live-loop lane). Read-only; no desktop input, game, pad,
capture, GPU or sealed data.

Reviewed against `review-inputs.json` sha256 `8f7fa0091996f89a9af5b6ba1ec9ebf4723ce152fe590990922803c7738ac129`, base
`17743ad` (HEAD).
- All 33 `files` and all 13 `support_files` match the working tree.
- I diffed HEAD against the working tree myself. `agent/loop.py` gains only a 4-line `--compat` dispatch
  (`loop.py:1347-1350`).
- The new runtime code is `agent/camera_compat.py` and `agent/camera_acceptance.py`, plus the pinned record
  `agent/camera_maps/alt-247-124-yaw-compat.json`.
- `controller.py`, `startup.py`, `camera_map.py`, `tracker.py`, `state.py`, `perception/outline.py`, `perception/hud.py`
  and `alt-247-124.json` equal HEAD after line-ending normalization.

## Verdict: **FIX**

Every harm-order check passes. One finding blocks, and it fails closed: at this PC's native resolution the check can
never send a pulse, so a live sitting spent on it is guaranteed to fail. The fix is local to `camera_compat.py`.

### C1 (blocking; fails closed): synchronous PNG retention sits inside the pulse timing window

- **Cause.** `pulse()` fixes `release_at = now + 0.05` (`camera_compat.py:116`). Only after that does it call
  `self.retain(...)`, which runs `cv2.imwrite` of the full native frame (`:129`, `:262-264`). It then refuses if
  `io.now() >= release_at` or if the frame is older than 100 ms (`:132-133`). So the PNG write time comes out of the
  50 ms pulse, and out of the frame-age budget.
- **Measured.** A `cv2.imwrite` PNG on this PC (live venv, no game load):
  - 2560×1440: **73–89 ms**;
  - 1920×1080: **41–49 ms**.

  The desktop here is 2560×1440 (`scripts/capture.py`).
- **Reproduced.** I used the owner's own fakes (`tests/test_camera_compat.py::setup`) with a `save` that advances fake
  time by the measured cost:

  | save cost | result | pulses sent |
  |---|---|---|
  | 0 / 10 / 30 ms | passed | 10 / 14 / 23 |
  | 45 ms | `no_observed_response` | 1 (truncated to about 5 ms) |
  | 75 / 86 ms | `stale_before_input` | **0** |

- **Consequences.**
  - At 1440p, no pulse is ever sent.
  - At 1080p, the first pulse is shortened to about 5 ms and draws no response.
  - Even at small costs, each pulse's real length is `50 ms − retention`. So pulse length depends on disk I/O,
    the budget is consumed faster (23 pulses at 30 ms instead of 10), and the observed response gets confounded.
  - The response-frame retain (`:168`) likewise ages the frame the next pulse starts from.
- **Coverage gap.** The owner's happy-path tests use `save=None`, and `test_slow_detector_and_retention_refuse_before_input`
  asserts refusal only at 200 ms. The realistic cost is never modeled.
- **Fix.**
  - Move retention off the timing path. Either queue frame copies to a background writer (the lossy, bounded
    `live_range_bc.Journal` pattern), or retain first and then take a fresh `observe()` and re-match the target before
    computing `release_at` and the age checks.
  - Compute `release_at` from the time the send is issued.
  - Add a test with a realistic `save` cost of at least 90 ms that must still converge.

### Harm-order checks (all pass)

1. **The input set cannot exceed the declared pulses, axes, caps or scope.**
   - Each command is one axis:
     - yaw must be an exact measured signed knot (`YawCompatibility.yaw_command`), and the knot set is pinned;
     - pitch must be exactly ±0.1;
     - then `abs(value) == 0.1` is enforced as well (`:122-127`).
   - Sent state is `{**NEUTRAL, rx|ry: value}` through `send_guarded`, and `Live` enforces its whitelist, a lease capped
     at `release_at`, `not_after` and `scope_not_after = deadline`. The explicit `release()` is in `finally`.
   - At most 40 pulses and at most 2.0 s reserved (`:114`). Acquisition is ≤10 s per side, convergence ≤15 s per
     side, and the scope is ≤60 s, validated in the parser, with no CLI overrides.
   - Physical hold is bounded by `Live`'s lease, which ends at `release_at` (watchdog resolution 20 ms).
   - **No degree or interpolation path exists.** The module imports only `camera_acceptance`, `NEUTRAL`/`RangeLost`,
     `ENEMY` and `Tracker`, and calls `Tracker.update(..., cam=None)`. It never touches `Cal`, `rate`, `stick_for`,
     focal length or turns.
   - The separate parser admits only `--compat`, `--live`, `--camera-map`, `--camera-settings-match`, `--game-pid`,
     `--max-s` and `--out` (`allow_abbrev=False`).
2. **Every `agent.loop` safety guard applies.**
   - It uses the landed `LiveSafety` and `_open_live_io`: a 10 ms monitor for focus, all-key/mouse takeover and the
     deadline, started before attach.
   - `guard = safety.proof(in_range, idle, range_required=True)` runs on every `observe()`, both before and after
     detection. The same latching proof is `Live`'s commit guard.
   - The board and session guards are constant `False` and no scoreboard is called, so the transition exemption is
     never used.
   - `ResponseWatch` arms a `threading.Timer` that calls `safety.stop("no_observed_response")` before each send.
     Blocked capture therefore still closes `Live`; the owner's test covers this.
   - `finally` cancels the timer, closes the source and then safety, and writes `result.json` after release.
   - Preflight refusals (map, focus, takeover, output directory) all happen before attach.
3. **The acceptance record is pinned and cannot be self-declared.** I checked this on the real files, read-only.
   - `YAW_COMPAT_ACCEPTANCES` is a code constant pinning the record's sha256 (`a5597978…`).
   - The record pins the actual on-disk map bytes: `map_sha256 = 0e062286…` equals the CRLF file hash. It also pins
     the settings, the exact 14-knot list and the four named holes, with every hole re-checked as `missing`. It requires
     `settings_match`, and it pins 4 evidence files under `docs/evidence/camera-map-20260929b/`.
   - Knots come from values whose status is candidate or accepted, but they must equal the pinned list, and the map
     bytes are pinned too. So status strings cannot add anything.
   - What the real files return:
     - the scoped load gives knots ±{0.1, 0.2, 0.3, 0.45, 0.6, 0.8, 1.0}, with the receipt's `live` still `False`;
     - `load_reviewed_camera_map` refuses, and so does `load_camera_map(live=True).require_controller()`
       ("focal: missing … live");
     - a wrong `settings_match` refuses;
     - the legacy profile refuses on the compat path.
4. **The legacy trace is unchanged.** Running `verify_legacy.py` gives "1500 exact legacy pad reports and camera states
   match c34e6c8". `controller.py` is byte-identical to its pin.
5. **Tests cover each limit and stop.** Covered: budgets, off-knot commands, admission tampering, complete-map refusal,
   target loss, stale, non-monotonic and invalid frames, opposite, absent and late responses, response-watch expiry
   during blocked capture, a real-`Live` actuator, preflight failures, and post-attach cleanup. The eight suites in the
   live venv (`--no-project`, read-only) gave **486 passed**, which is the owner's 478 plus the 8 torch skips. The gap
   is C1.

### Notes (not blocking)

- **C2 (operational): the record pins on-disk CRLF bytes by design.** If a checkout, stash or pre-commit restore
  rewrites `alt-247-124.json` or the record into another line-ending form, admission refuses. That fails closed, but
  verify both hashes on the PC right before the sitting.
- **C3:** after C1's fix, keep the "late frame cannot authorize a pulse" property. Take a fresh observation for the
  age check, never the retained one.

## Limits

Everything used fakes. No game, pad or real capture was used, and the physical pixel response and device latency are
unmeasured. The `imwrite` costs are synthetic 3-channel frames measured on this PC without the game running, so real
costs during play are likely higher.
