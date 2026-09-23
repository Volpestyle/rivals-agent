# Review: placement driver `scripts/place.py` (input-path review under AGENTS.md)

Reviewer `admission-review` (Claude Opus 5.5), 2026-09-23. The review is read-only: no pad was opened, no game
input sent, nothing committed.

**Bytes reviewed:**

- `scripts/place.py` `2fa435f0`
- `tests/test_place.py` `8b565c55`
- `tests/test_place_frames.py` `b896aec5`
- `agent/placement.py` `822e7738`

**Context read:**

- `agent/controller.py` `55730a7a`: `Live`, plus an uncommitted Cal deadzone diff that `place.py` does not use
- `agent/startup.py`
- `agent/loop.foreground_pid_guard`
- `record.idle_warning`
- the hand-back `placement-driver.md`

## Verdict: APPROVE WITH REQUIRED FIXES

The actuator path is sound: every write goes through `Live`, sticks only, re-proved per write, with a
0.25 s lease. The live gate cannot pass as committed. **Two required fixes (D1, D2) before the measurement
session**, and D3 before any live run.

## Answers

### 1. Can any path open a pad or send a stick value before the live gate passes?

**Yes, by design: `--measure-pitch`,** and `--reset-check` once the pitch durations are set.

- **What they require:** `--pid` naming the running `Marvel-Win64-Shipping`, the game in the foreground
  (`_open_game`, `:532-540`), and the range HUD on the first frame. `Live.__init__` raises `RangeLost` before
  creating the pad (`controller.py:83-84`).
- **What they don't require:** the declaration.
- **Today:** `--reset-check` is refused, because `PITCH_DOWN_S` is None (`:598`, `:498`). So **`--measure-pitch`
  is currently the only path to the pad**.
- `--dry` and `--replay` never import `Live`.

**`--live`:** `check_declaration` runs before `Live` exists (`:631-648`), and it refuses first on any unmeasured
constant (`:243-246`). `run_live` repeats that check before any write (`:358-361`). **As committed, no
declaration can pass.** I verified this in code, and `tests/test_place.py` (54 passed) covers it.

### 2. Is `prime()` camera-only?

**Yes.**

- It holds `rx +0.45` for 0.3 s through `_hold(..., allowed={"rx"})` (`:339-340`). Then 5 s of proven frames
  with no write, then, with `undo`, `rx −0.45` 0.3 s under the same allow-set (`:347-349`).
- `_hold` refuses any key outside its allow-set before writing (`:307-308`). The only `live.send` in the file
  is inside `_hold` (`:314`).
- No translation or button is possible from the prime. The old `ly=0.05` draft is gone.
- Its timing matches `agent.startup`: the pulse at the earliest guarded send, with `Live(settle_s=0)`.

### 3. Do the measurement modes obey the kill switch and the range proof? Can they ever walk?

**The kill switch and the proof: yes.** Every write is preceded by `proof(live.fresh())`:

- the foreground is still the game (the Alt-Tab kill switch);
- `in_range`;
- no idle banner.

Separately, `Live.send` re-proves `in_range and focused()` at commit, with a frame-age check (`:612`,
`controller.py:137-144`). The `look()` frames are proven too (`:434-437`), and Ctrl-C closes `Live`
(`:621-624`).

**Walking: no.** Every hold in these modes is `allowed={"ry"}` (measure, reset) or `{"rx"}` (prime).

**Not proven: that the pad stays harmless when neutral.** `Live` attaches a real virtual pad, and the game
turns the camera on attach until the first non-neutral report. That's camera only, and the prime ends it.

### 4. Is the replay mode's simulator check honest?

**It is weaker than its exit code says (D2).**

- **Default flags pass vacuously.** Without `--pitch-ref`, every recorded frame is UNLEVELLED and every
  decision plans PITCH_RESET. Replaying the 84-frame fixture: 28 decisions, **0 compared, `ok: true`, exit 0**.
- **With `--pitch-ref`, the comparison is trivial.** 9 of 28 decisions are compared, and all are **TURN**. Each
  decision is planned from a fresh state, whose first action is always "face the pair", so moves are never
  compared.
- **The check is circular by construction.** The simulator is rendered at the pose localised *from the same
  boxes*. It tests that the planner behaves the same on real and idealised boxes at an assumed pose, not that
  the pose is right.
  - It does flag some biased inputs: on simulated boxes with a ±8 % differential bias it returned
    `ok: false` for 3 of 3.
  - It cannot detect a pose that is wrong but self-consistent.

## Required fixes

**D1. A gate for the measurement modes (before the measurement session).**

- **The gap:** they drive a pad with no declaration, so any agent could run `--measure-pitch --pid <PID>`
  while the game is in front. AGENTS.md says one agent drives the desktop, and input needs lead authorization.
- **Required:** a small `measurement-declaration` naming:
  - the game PID and the range entry;
  - that James is present and recording;
  - the lead's authorization;
  - an expiry, so a stale file cannot be reused.
- The same gate goes before `Live` in `--measure-pitch`/`--reset-check`, with a test that main refuses without
  it.
- Camera-only input is low-risk. The rule is about authorization, not only motion.

**D2. Make replay's exit code mean what it checked.**

- **Required:**
  - `ok` requires `compared > 0`, else exit 2 with "nothing compared";
  - the report states that the comparison is first-action-from-fresh-state and pose-circular;
  - optionally, compare the first *move* (continue planning from the view until a WALK/STRAFE, or say none).
- Until then, don't cite a replay `ok` as evidence of placement correctness.

**D3. Bind the live declaration to one range entry and to time (before any live run).**

- **The gap:** `check_declaration` has an unused `now` parameter (`:238`), and it doesn't bind the range entry.
  A declaration stays valid across re-entries while the PID lives, whereas the pilot bindings were per range
  entry.
- **Required:** an issued-at/expiry field, and the range-entry id or binding hash, checked against the current
  entry.
- **Also:** the look's `done` and `findings` are self-attested JSON. Require the look's independent review file
  (hash) among the evidence, so the gate rests on a reviewed record, not an unsigned claim.

## Smaller

- **`Live.fresh()` can return a stale frame.** After a 0.1 s timeout it returns the last frame
  (`controller.py:116-119`), and the script's own `proof(live.fresh())` may run on that stale frame. `Live`'s
  commit re-checks freshness, so input is still safe. The script proof can still pass on a stale frame and then
  `Live` raises `RangeLost`, so the stop reason may read as "range" instead of "stale".
- **The log file handle can leak.** If `Live(...)` raises in `--live` (`:648`), the steps log stays open; no
  input is affected.
- **The low-end map (checklist step D) has no tool.** Agree it needs a named owner and path; `place.py` should
  not grow it.

## Checks run

- `uv run pytest tests/test_place.py`: **54 passed**.
- `tests/test_place_frames.py` with the perception group: **5 passed**.
- My own calls:
  - the replay vacuity above;
  - a biased-sim replay;
  - a grep for every `live.send`/`hold`/`send_guarded` in `place.py`: only `_hold`, `:314`.
- I didn't re-run the full suites; I ran only the driver's own tests.

## What is sound

- **One door to the pad.** Every input goes through `Live`, sticks only, per-write proofs, the lease and close
  on every exit.
- **Gate order.** The live gate refuses on unmeasured constants before reading the declaration, and again in
  `run_live`. far is refused; near needs `EDGE_X_M`.
- **Moves.** A move without a pose is refused again at the actuator (`execute`, `:324-326`).
- **Measure-pitch's method:** a sweep, a clamp check from looking up, and 3 repeats with a spread limit. `ok`
  is false with a named reason otherwise, and nothing is written into code automatically.
