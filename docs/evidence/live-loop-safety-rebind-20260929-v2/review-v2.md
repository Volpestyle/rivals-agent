# Independent delta re-review v2: live-loop safety and deferred camera rebind, VUH-1319, 2026-09-29

Reviewer: live-review (Claude Opus 5.5, `w2:p3E`, the v1 reviewer, outside the live-loop lane). Read-only; no desktop
input, game, pad, capture, GPU or sealed data. Scope: the delta since
[review v1](../live-loop-safety-rebind-20260929/review-v1.md) (receipt `b8711867…661a`) and the v1 findings.

Reviewed against `review-inputs.json` sha256 `520e48a80945e89ad3b9fc9f181cf8f8d9b1af9a8e7885978bccfe7caba796c8`, base
`5b55f96`.
- All 17 `files` and all `support_files` hashes match the working tree.
- Only `agent/loop.py` (now `96bd81b3…7462`) and `tests/test_loop_safety.py` differ from the v1 pins.
- The `pre-v2/` snapshots equal the v1 pins.
- I diffed `pre-v2/` against the working tree myself, after line-ending normalization. The whole runtime delta is the L1
  change: `LiveSafety.begin_scoreboard` and `end_scoreboard`, the window check in `proof()`, and the calls in
  `LiveIO.scoreboard` (`agent/loop.py:228-244`, `1220-1236` and `1300-1308`).
- `agent/controller.py`, `agent/startup.py` and the other calibration-pinned files are unchanged.

## Item 1, the `agent/loop.py` safety delta: **LAND**

### L1 (was blocking): fixed

- **The mechanism.** `LiveIO.scoreboard` opens a latch exemption before `Live.scoreboard()` and always closes it in
  `finally`. While the window is open, a negative range proof still returns `False`; it just doesn't latch
  `range_lost`.
  - The window lasts at most `hold_s + RETURN_S + 2·FRESH_S` and is capped at the scope deadline.
  - A non-finite or negative hold refuses before any window opens. `begin` refuses to nest.
- **No proof is promoted.** `Live` still needs a true range proof before pressing BACK, and it still raises after
  `RETURN_S`. `LiveIO` latches `range_lost` on that `RangeLost`, as in v1.
  - The monitor's checks (focus, takeover and deadline) ignore the window.
  - `proof()` checks idle and reader errors before the window test, so those latch immediately.
- **Reach.** The window affects only proofs made while the loop thread is inside `_scoreboard`. The loop's three
  `p.in_range` calls run on that same thread, and the decider thread never proves range. So no other sender can use the
  exemption, and a negative proof can never authorize input.
- **Independent reproduction.** My v1 script, with the real `Live`, `LiveSafety` and `LiveIO` and a fake pad and
  capture:
  - Fades of 0, 0.05, 0.2 and 1.4 s return the board, with no stop and `Live` still usable.
  - A fade of 2.0 s, past `RETURN_S`, raises `RangeLost`, latches `range_lost` and closes `Live`.
  - Focus loss or takeover **during** a fade latches `focus_lost` or `human_takeover` and closes `Live` 9–11 ms after
    the trip.
- **Owner tests.** New tests cover real-`Live` fades of 0, 0.05, 0.2 and 1.7 s; the five hard stops during a fade;
  window expiry and that the window never grants; invalid holds; and window cleanup on an exception.

### L2: disclosed, and the lead confirmed

Scripted, Jev and learned modes lose the 0.25 s one-false-frame HUD grace outside the scoreboard window. The README now
states this, following `AGENTS.md`.

### L3: recorded as a known gap, outside this delta

`scripts/range_cast_probe.py:324-347` still drives `LiveIO` and `Loop` live without takeover or an independent monitor.
The README records it, and the lead routes the fix. It must be fixed before that script is used live again.

### L4: fixed

`owner-tests.txt` now carries the command and the environment. I re-ran that same five-file set in the live venv
(`--no-project`, read-only): **345 passed**, matching the owner.

### Unchanged from v1 (evidence reused)

The following were verified in v1 and none of them changed:
- every live mode needs a PID and a finite duration;
- the 10 ms monitor is independent of capture;
- takeover uses the reviewed `human_input`;
- HUD and idle are checked on every proven frame;
- release is idempotent and retried, and cannot deadlock;
- every exit path cleans up;
- a bare `LiveIO()` refuses;
- the default guards are equivalent to `Live`'s own.

## Item 2, `integration.patch` `b9eb06ab…2d5b`, design only (no receipt)

The v1 findings are resolved in design:

- **P1: resolved.**
  - `Cal.from_profile(live=True)` refuses without an explicit `--camera-map`, and `--camera-map` has no default.
  - Live always goes through `load_reviewed_camera_map`, and pose-only resolves the map before any hardware.
  - `--camera-settings-match` must name the same profile. That is operator evidence, not pixel verification, and the
    README says so.
- **P2: resolved.**
  - `agent/camera_acceptance.py` keeps a code-reviewed registry, `REVIEWED_ACCEPTANCES`, which is **empty**. So live
    currently refuses every map, including the fully "accepted" legacy one.
  - An entry pins the SHA-256 of a record that must match the map's own bytes (`map_sha256`), its profile and
    settings, and a nonempty evidence map. Each evidence file is re-hashed, and its path must stay inside the repo.
  - A JSON file supplied by path can match an entry only if it is byte-identical to the reviewed map. Status strings
    cannot add trust. Candidate and missing points are still refused even for a trusted record.
- **P3: resolved.**
  - All five map-derived timed turns (startup ±0.45, search up and down, disengage) are validated at construction,
    before attach, and again whenever computed.
  - A turn needs a finite positive angle and rate, and must last at most 4× its legacy duration. Nothing is clamped
    silently, and the durations and the factor go into run metadata.

The legacy exactness argument from v1 still holds; I did not re-run the 1,500 comparisons. The two things this design
cannot settle belong to that later exact-byte review:
- whether the accepted whole map and its evidence are right, which is the acceptance owner's job;
- the registry entry that will first grant live use.

## Conditions

- This receipt covers the `agent/loop.py` safety delta and its pinned tests. It grants no live authority.
- Before its own exact-byte review and a new deployment freeze, `integration.patch` stays unapplied.
- The bridge (`agent/session.py`) and `scripts/range_cast_probe.py` each need the guarded scope before live use.
- Everything used fakes. The real fade-out length, game behavior and physical release latency are unmeasured.
