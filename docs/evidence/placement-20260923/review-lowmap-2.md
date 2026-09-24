# Re-check: lowmap-2 (L1-L3 in `lowmap_fit`, L4 the physical-input kill switch)

Reviewer `admission-review` (Claude Opus 5.5), 2026-09-23. The re-check is read-only: no pad was opened, the real
sentinel was not started, and nothing was committed.

**Bytes: all equal to the hand-back.**

- `scripts/place.py` `5685148d` (diffed against landed `19a8e3a`)
- `agent/physical_input.py` `3f4357b7`
- `tests/test_place_lowmap.py` `dc283323`
- `tests/test_physical_input.py` `48138ec2`
- `docs/next-pc-session.md` `1fa52c61`
- `docs/lanes/placement.md` `3caa557a`

**Tests:**

- `tests/test_physical_input.py` with `tests/test_place.py`: **116 passed** (24 + 92).
- `tests/test_place_lowmap.py` under a cv2 venv: **20 passed**. The file has 20 tests; the hand-back's "21" is a
  miscount.

**My own checks** (`pi_adv.py` and `lmfit2.py` in my scratchpad):

- the client against fake sentinels;
- `trips()` on the packet classes;
- constructed rows through `lowmap_fit`.

## Verdict: settled. Step 5 may run behind this kill switch. Three notes, none blocking

| Question | Answer |
|---|---|
| The sentinel cannot fail silently | **Holds** |
| A touch during a hold releases within one write | **Holds** |
| The touch test is positive and runs before the pad | **Holds** |
| Zero-effect and handle-0 packets don't trip | **Holds** |
| L1-L3 make a wrong measurement not ok, not Cal-shaped | **Holds**, within the stated tolerance |

**1. The sentinel cannot fail silently.**

| Failure | Where it is caught | My fake-sentinel result |
|---|---|---|
| **No registration** | `RegisterRawInputDevices` failing, a failed window class or window, or a failed `OpenProcess` → `sys.exit(2)` before READY; `start()` refuses | exit 2 → `Refused … no pad opened` |
| **Heartbeat loss** | `HB` comes from `WM_TIMER` on the same message loop that handles `WM_INPUT`, so a hung loop stops both. `check()` reports stale when the last HB is over 0.5 s old | READY, 3 HBs then silence, process alive: None → "heartbeat is stale" |
| **Sentinel death** | `proc.poll()` | "the physical-input sentinel is not running" |
| **A dead client reader thread** | Its bad line stops the HB updates, so it fails stale | — |

**2. A touch during a hold releases within one write.**

- `make_proof` calls `physical.check()` first, before every `_hold` write and every settled frame. `Live`'s commit
  guard also requires `physical.check() is None`.
- A trip sets the latch through the reader thread. The next proof returns `TRIPPED` → `Stopped`, and `_hold`'s
  `finally` releases.
- **The worst-case stick-on time after a touch** is one write period plus a proof: 50 ms plus `fresh()` and the HUD
  check. The test covers "stops `_hold` after one write, then releases".
- **The backstop:** an executor that doesn't ACK within `TRIP_KILL_S` = 1 s is `TerminateProcess`ed.
  - This covers the case the lease cannot: a process hung with the GIL held, where the lease watchdog can't run.
  - The ACK is sent only by `check()`, which also returns `TRIPPED`, so an ACKing executor is a stopping executor.

**3. The touch test is positive and runs before the pad.**

- **Order in both measurement and live branches:** the declaration, then `_physical_input` (start, then `pre_run`),
  then `_open_game`, then `_pad_side()`/`Live`. Each has `physical.close()` on its failure path and in the final
  `finally`.
- **`pre_run` refuses a trip latched before its prompt.** My pre-latched fake gave "before the touch test: …", so an
  old latch can't satisfy the test.
- It requires `TRIPPED` from a new packet within 30 s: "no touch" is refused.
- Then 3 s with no EV while `foreground_pid_guard(pid)` is True. Game never in front: refused.
- Then REARM, and it requires ARMED.

**4. Zero-effect and handle-0 packets don't trip.**

`trips()` is `handle != 0 and control_affecting(…)`, using the importer's rule. I checked:

- handle-0 key: False;
- real-handle zero-motion mouse: False;
- real move, button, absolute or key: True.

The raw structs match the 64-bit Windows layout (a 24-byte header; `RAWMOUSE` with its ULONG-aligned button union).

**5. L1-L3.**

| Construction | Result |
|---|---|
| **The reviewer's 1.6×/0.9×** | not ok ("holds disagree") |
| **One low deflection (0.06) at 1.6×/1.0×** | not ok. The case my first review said nothing caught |
| **15° off-axis on every hold** | not ok |
| **Abstention** | not ok |
| **Wrong sign** | not ok |

- **Output fields (L3 holds):** every not-ok result carries `cal_candidate` and no `cal`. `main` and
  `--lowmap-judge` print `cal` only when ok.
- **Re-judging:** `--lowmap-judge` refuses non-lowmap files and refuses to overwrite its source. It records
  `rejudged_from` and `judged_by`.
- **On-time:** `held_s` is now first send to release (the `stamps` in `_hold`).

## Notes (not blocking)

**N1: the tolerance is loose on purpose.** `_lowmap_agree` is `|a−b| ≤ max(25 % × max(a, b), 0.5°)`, so a ratio up
to 1.33 passes.

- **Constructed:** 1.3×/1.0× on every hold is `ok: true`, and a 1.3× second repeat is `ok: true`.
- **Constructed:** a deflection biased +20 % on all four holds is `ok: true`, because nothing can see a consistent
  bias.
- This is scatter tolerance, not a hole. If the low end needs better than about ±15 %, tighten it to 25 % of the
  *smaller* value.

**N2: what the switch does not hear.** Say this on the page:

- a **physical gamepad**: only keyboard (1/6) and mouse (1/2) are registered;
- **pen/touch digitizers**;
- **any input arriving as injected (handle 0)**: remote-desktop/Parsec/Steam Remote Play input, or another agent's
  SendInput desktop driver.

So the kill switch works for James at the PC's own keyboard and mouse, not remotely. The one-driver rule covers the
other agents.

**N3: the touch test runs with the terminal in front.**

- **What it proves:** raw-input delivery to the background sentinel. The sentinel's window is never foreground, so
  this is the INPUTSINK path.
- **What it doesn't prove:** delivery with *the game* in front. INPUTSINK is documented to work regardless of the
  foreground app, so this is low risk.
- **A cheap confirmation, once per session:** while the page's step 3 waits "3 s hands off, game in front", a key
  tap should visibly delay `Armed`. That shows the sentinel hears input with the game in front.

**Minor:**

- **The HB write isn't under the lock.** `on_timer`'s `say("HB …")` runs outside `lock`, while the stdin thread's
  `say("ARMED")` runs inside it, so the two threads could interleave a line.
  - A merged `HB …TRIP {}` line does hide the TRIP from the client: my fake gave `check()` None. But a real TRIP is
    written by the window thread, the same thread as HB, so that case can't happen live.
  - A merged ARMED would only make `rearm()` refuse.
  - Put every `say` under one lock anyway.
- **A trip between arming and the first proof latches.** In that window (cv2 import, Live construction) no proof
  runs yet, so the 1 s timer may terminate the executor before any report is written. That fails safe; it only
  loses the run's files.
- **The camera-acceleration note (hold lengths versus Cal's maps)** remains open, as the hand-back says. It matters
  for interpreting the numbers, not for safety.
