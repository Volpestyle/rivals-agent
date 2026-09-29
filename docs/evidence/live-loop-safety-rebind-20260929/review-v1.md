# Independent pre-run review v1: live-loop safety delta and deferred camera rebind, VUH-1319, 2026-09-29

Reviewer: live-review (Claude Opus 5.5, `w2:p3E`, outside the live-loop lane). Read-only; no desktop input, game, pad,
capture, GPU, paid compute or sealed data.

Reviewed against `review-inputs.json` sha256 `17c7ece41b75f51580d7994ba86f6447c38a665530b58afdb7bf6b7fe85aa10e`, base
`7e2b2e3`.
- All 17 `files` and all 28 `support_files` hashes match the working tree. Active `agent/loop.py` is `00047fd5…a412`,
  and `integration.patch` is `7687e548…9766`.
- I diffed `agent/loop.py` against HEAD myself, after line-ending normalization. The diff has four hunks: `LiveIO`,
  the new `human_takeover_guard`, `LiveSafety` and `_open_live_io`, the `--game-pid` help text, and `main()`.
- `agent/controller.py`, `agent/startup.py` and the other calibration-pinned files are byte-identical to their pins.

## Item 1, the `agent/loop.py` safety delta: **FIX**

One finding blocks. It is not an input hazard, because it fails closed. But it turns the normal scoreboard transition
into a permanent stop. As a result, episode collection can never start and every end-of-run scoreboard is lost. The
README says the opposite ("Scoreboard opening keeps the existing recognized board/session alternatives").

### L1 (blocking; fails closed): the latching range guard fires during the scoreboard's documented return wait

- **Cause.** `_open_live_io` passes `safety.proof(percept.in_range, …, range_required=True)` as `Live`'s range guard
  (`agent/loop.py:1298`).
  - `Live.scoreboard()`, which is pinned and unchanged, releases BACK and then waits up to `RETURN_S` = 1.5 s for the
    range to be recognized again: `while not self._in_range(self.fresh())` (`agent/controller.py:225-228`).
  - Under the delta, the first post-release frame that is not yet the range makes the proof call
    `safety.stop("range_lost")` (`agent/loop.py:1281-1282`). That closes `Live` for good.
  - Every later proof returns `False`, so `scoreboard()` times out and raises `RangeLost` before `return shot`, and the
    board frame is discarded.
- **Consequences.**
  - `Loop._scoreboard` records `skipped: range_lost`.
  - `_prepare_episode` then returns `collection_baseline_refused`, so every `--collect-episode` run refuses at its
    baseline (`agent/loop.py:625-635`).
  - Every default end scoreboard is lost too.
- **Reproduction.** The real `controller.Live`, `LiveSafety` and `LiveIO`, with a fake pad and a fake capture. The
  capture shows the board while BACK is held and a fade (session banner, no HUD) for `fade_s` after release.

  | Guards | fade 0.00 s | fade 0.05 s | fade 0.20 s |
  |---|---|---|---|
  | Delta (`safety.proof`) | board returned | `RangeLost`, `stop_reason=range_lost`, `Live` dead | same |
  | Pre-delta control (plain `in_range`) | board returned | board returned | board returned |

- **Scope of the evidence.** I have not measured the real fade-out. `RETURN_S` exists for it, and the fade-in is
  documented as 0.3–0.5 s (`controller.py:49-50`), so any fade of one frame or more triggers this. The owner's tests
  miss it: `tests/test_episode_collection.py` uses a fake `scoreboard()`, and `tests/test_loop_safety.py:119-133` checks
  the proof and `LiveIO` separately, never the real `Live.scoreboard()` with fade frames.
- **Fix (in `loop.py` only; the controller stays pinned).**
  - Let `LiveIO.scoreboard` open a transition window on `LiveSafety`. During the window, a negative range proof returns
    `False` without latching, while focus, takeover, the deadline and idle still latch.
  - Close the window when `scoreboard()` returns or raises. The existing `except RangeLost` path already latches a stop
    for a real failure, so the documented `RETURN_S` bound still applies.
  - Add a test with the real `Live` and fade frames, covering both return inside `RETURN_S` and failure after it.

### L2 (medium; decision and disclosure, not blocking): one false HUD-gone frame now ends scripted, Jev and learned runs

The loop now uses the latching guard as `percept.in_range` in every live mode (`agent/loop.py:1450`). Before the delta,
only collection did, and without latching. Scripted, Jev and learned runs used to tolerate `LOST_GRACE_S` = 0.25 s
(`agent/loop.py:54`: "one false 'HUD gone' frame (camera straight up) must not end a run") and resume. Now one such frame
permanently stops the run. This matches `AGENTS.md` ("stops when it disappears"), and it adds no input. But the README
doesn't disclose it, and the scripted brain's pitch re-level can produce exactly that frame. Please have the lead
confirm it and note it in the README.

### L3 (medium, outside this delta's files): `scripts/range_cast_probe.py` drives the loop live without the new scope

`live_probe` builds its own `Live(guard=range_focus)` and `LiveIO(native)` and runs `agent.loop.Loop`
(`scripts/range_cast_probe.py:324-347`). It has focus, deadline and HUD checks on proofs, but no human takeover and no
independent 10 ms monitor. The delta keeps an explicit `LiveIO(live)` legal, so that path is unaffected and still lacks
two of the five guards `AGENTS.md` now requires. Route it through `LiveSafety` before its next live use.
`agent/session.py:130` calls a bare `LiveIO()`, which now refuses before touching hardware, as intended; the README
already names the bridge requirement.

### L4 (low, evidence)

`owner-tests.txt` records no command. The 331 passes reproduce only when `tests/test_episode_collection.py` is added to
the four named files, run in the torch-enabled live venv (details below).

### Verified (no finding)

- **Every live mode is scoped.**
  - `a.live` now requires `--game-pid` and a finite positive `--max-s` in every mode: scripted, Jev, learned, range,
    range-skill, collection and pose-only.
  - Focus and takeover are checked before preload and again after it, before capture or attach
    (`agent/loop.py:1416-1437`).
  - `_open_live_io` starts the monitor before `Live()` is constructed. `Live`'s constructor runs the latching proof on
    its first frame before creating the pad, so a scope failure there opens no pad (`controller.py:85-86`).
  - `bind()` re-checks, so a stop during construction still closes the new device.
- **Guards.**
  - A 10 ms monitor thread checks the deadline, focus and all-key/mouse takeover. It never touches capture, so a
    blocked `fresh()` cannot delay it.
  - `human_input` is reused unchanged from the reviewed calibration tool, and reads are serialized under
    `LiveSafety._lock`, so tap bits cannot be lost between threads.
  - Idle and HUD are checked on every proven frame, meaning every `_commit`, every `start_pose` frame and every loop
    tick. Idle latches on board and session proofs too.
  - With no frames, no send can be proven, and `Live`'s 0.1 s freshness and 0.25 s lease release the pad.
  - Startup already refused on the first missing HUD (`agent/startup.py:183`), so latching changes nothing there.
- **Release.**
  - `_close_live` calls `Live.close()`: neutral under the actuator lock, then `_dead`. The call is idempotent, and its
    errors are retained and retried at `safety.close()`, which raises if release is not confirmed.
  - Guards run outside `Live`'s pad lock (`controller.py:59-62`, 123-135), so closing from inside a proof cannot
    deadlock.
  - Every exit reaches `source.close()` and then `safety.close()` through the outer `finally`: attach, startup, pose-only,
    metadata, brain, log, loop construction, run, and `ap.error` (which fires before anything opens).
  - The pad device stays attached, neutral, until the process exits. That is existing `Live` behavior.
  - The known limit is unchanged: a native write that blocks while holding `Live`'s lock delays `close()`.
- **Bare `LiveIO()`** raises `ValueError` before any import or hardware (`agent/loop.py:199-201`).
- **Input behavior.**
  - Default guards are equivalent to `Live`'s own defaults: `record.in_range`, `is_scoreboard(f) is True` and
    `banner_score >= BANNER_MIN`.
  - The whitelist, freshness, lease, `send_guarded` and the controller are untouched.
  - Apart from the added stops, the only behavior changes are L1 and L2.
- **Tests.**
  - The four named files in my private environment gave 264 passed and 8 skipped; the skips are torch-only.
  - The same files in the live venv (`--no-project`, read-only) gave 272 passed.
  - Adding `tests/test_episode_collection.py` gives **331 passed**, matching the owner.
  - The stop-path coverage is good: every stop category, a blocked capture, a late attach, release failure, the real
    actuator, and every post-attach failure. The scoreboard gap is L1.
- **Baseline-failure claim, sampled.**
  - `test_sealed_denylist_v2::test_every_consumer_pins_v2`, `test_spatial_yaw_fallback::test_partial_fit_never_recomputed`
    and `test_replay_hud::test_identify_order_on_james_is_his` fail on the current tree. None of those files imports
    `agent.loop`.
  - `test_measure_inference_fps.py`, which does import `agent.loop`, fails the same three IDs on a stdlib export of
    pre-delta HEAD, and HEAD's `loop.py` equals the 8331c45 version.
  - So the claim holds on this sample: 6 of the 45 IDs.

## Item 2, `integration.patch`, design only (no receipt)

Legacy exactness looks right by construction:
- The 1.8 s re-level becomes `178.2/99` and `77.4/43`.
- Disengage becomes `180/415`.
- The startup pulses become `51.6/172` at ±0.45, since `SEARCH_TURN_RX` is −0.45.
- `cal=None` keeps `START_TURN_S` for other callers.

I did not re-run the 1,500 comparisons. Live refuses `candidate` and `missing` points for every value it reads, including
interpolation brackets. It requires full-stick coverage in both directions and a nonzero rate at the four timed sticks.
It also resolves the map before perception, capture and the pad. The following would make the applied version unsafe or
wrong, so please fix them before its exact-byte review:

- **P1 (high): the live default is a stale map.**
  - `--camera-map` defaults to `legacy-265-75`, whose every point is `accepted`, so `live=True` loads it.
  - Its settings are H/V 265/75, but James plays the alt Spider-Man at 247/124. The patch deletes the `Cal` docstring
    that said so ("HISTORICAL, STALE … Recalibrate … before any alt agent run").
  - As a result, `agent.loop --live` without `--camera-map` would run with a known-wrong camera model.
  - Live should require an explicit `--camera-map` (no default), and should record an operator-declared settings match.
- **P2 (high): provenance is self-declared, not pinned.**
  - "Accepted" is a string inside the JSON, and `--camera-map` accepts any path. Nothing checks the file's sha256
    against a reviewed pin, that each accepted point's `receipt` exists and verifies, or that `settings` match the
    sitting.
  - `receipt()` records the sha256 but nothing enforces it.
  - Live use should admit only a built-in profile whose sha256 is pinned by a reviewed acceptance record, or a path
    whose sha256 matches one.
- **P3 (low): map-derived durations have no local bound.**
  - The startup pulse (`51.6/rate`), the re-level holds and Disengage now scale with the map's rates. A slow but
    "accepted" map lengthens pulses. The start deadline and the loop scope still cap them, and a zero rate is refused.
  - Add a validation that derived durations stay within a stated factor of the legacy values, or record them in the
    run receipt for review.

## Limits

Everything used fakes. No real fade-out duration, game behavior or physical release latency was measured.

## Evidence scripts (scratch, not in the repo)

- `scoreboard_fade.py` (delta) and `scoreboard_fade_control.py` (pre-delta guards): the real `Live`, `LiveSafety` and
  `LiveIO` with a fake pad and capture, as tabled under L1.
- A stdlib export of HEAD, `git archive HEAD`, used for the baseline sample.
