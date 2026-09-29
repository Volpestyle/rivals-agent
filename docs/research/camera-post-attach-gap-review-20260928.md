# Review: post-attach camera gap proposal, 2026-09-28 (amended)

Reviewer: live-review (Claude Opus 5.5), for the evaluator (VUH-1384). This reviews the design in
`docs/research/camera-post-attach-gap-20260928.md` only. It is **not a runtime receipt and not live authorization**.
It is read-only: no source or runtime changes, and no capture, pad, provider or paid work. The unchanged v6 behaviour is
not re-reviewed.

**Amendment 1 (same day, after the evaluator's reply).** The evaluator adopts the prime-first recovery. Three
corrections from the evaluator are accepted:
1. **Priming is always unknown in recovery.** A short report that returned is not proof that the pad primed or that the
   drift stopped; yaw-03 has no response evidence. So every failed initialization must actually detach, whatever the
   report count.
2. **The cause of the stall stays open.** The OBS timing does not separate the attach from the first `update()`. The
   first draft's attribution is withdrawn.
3. **Removal is documented, and the owner won't rely on it.** The installed `vigem_client.py` documents
   `vigem_target_remove` as an unplug, and says a target never removed is taken off the bus when the owning process
   terminates. The owner will implement explicit, idempotent removal of the owned target instead of relying on process
   exit or garbage collection.

The sections below reflect all three.

## Verdict: FIX the original design; implement the prime-first recovery, with a detach on every failed initialization

**What is sound.** The original readiness gate is safe for commanded input:
- no non-neutral report goes out before a guarded, continuing fresh stream;
- the deadline is fixed;
- semantic stops stay immediate;
- the prime and measurement freshness stops are unchanged.

**What is not.** Its neutral wait of at least 200 ms and up to 2 s before the prime adds uncommanded left drift of a
fresh pad on every attempt, and neutral reports do not stop that drift.

**The design to implement instead.** Keep the immediate prime as the fast path. Enter a bounded readiness wait only when
freshness cuts initialization short, and treat priming as unknown throughout that recovery. Any failed initialization
ends with an explicit, idempotent detach of the owned target, and only then any evidence I/O.

## The evidence

**Stall timing: the cause remains open.**
- `initialization_start` is at 721432.7539.
- The last OBS composition that still changes is at .7564, and the first unchanged one is at .7647. The image then stays
  unchanged for 483 ms.
- The first report, the prime at rx 14745, returned at .7837. The time `update()` was called was not recorded.
- The source-to-composition latency is unknown, and the last composition that changed is not a known start time for any
  renderer freeze.
- So these times do not isolate the attach from the first report, or from something else, as the trigger. This is one
  sample, and the exact attach time was not recorded either.

**The two observers are not independent.**
- The OBS log (`2026-09-28 21-55-08.txt`) shows the active Scene 2 source was `Display Capture`
  (`duplicator-monitor-capture`, method DXGI). DXCAM also reads DXGI Desktop Duplication.
- So "both observers froze" cannot separate a stall in the game's renderer from a stall in the compositor or the
  duplication path.

**The drift is established.** `docs/lanes/l4-controller.md` M1 records it:
- It starts 23–42 ms after attach and runs left at 21–49 deg/s, roughly 25 deg/s.
- One full reviewed right-stick pulse (rx 0.45 for 0.3 s) ends it. The residual drift after the pulse is 0.
- `VX360Gamepad.__init__` already sends a zero report (`virtual_gamepad.py:114-117`), so a neutral report is not a
  primed state.
- Whether a partial pulse ends the drift has not been established. yaw-03's 111 ms report is not evidence either way.

## Does a readiness wait address the 483 ms stall?

**Only if the stall is a one-time event around startup that ends within the bound.** About 0.48 s of stall plus the
200 ms streak is about 0.7 s, which is inside 2 s. If the stall recurs at a later report instead, the response prime
fails on freshness as yaw-03 did. That failure is safe, but the pad is left priming-unknown.

**What the original design's wait costs:**

| Case | Unprimed or unknown time | Drift at M1's 21–49 deg/s |
|---|---|---|
| Observed stall (about 0.7 s) | about 0.7 s | about 15–34 degrees |
| 2 s bound | 2 s | about 42–98 degrees |
| Fast start, no stall | at least 200 ms | about 4–10 degrees, on every attempt |
| Today (prime within about 30 ms) | about 30 ms | about 0–1 degree |

**Why that drift is a concern.**
- It is camera-only in the practice range, so it is not a game-safety breach.
- It is motion no proof covers. Neither neutral nor `close()` ends unprimed drift.

## Cleanup: explicit, idempotent removal of the owned target

**Confirmed on the installed vgamepad 0.1.0 and in the repo:**
- `VGamepad.__del__` (`:62-64`) is the only removal: `vigem_target_remove`, then `vigem_target_free`. There is no public
  close method.
- `vigem_client.py` documents these calls:
  - `vigem_target_remove` unplugs the target;
  - a target never removed is taken off the bus when the owning process terminates;
  - `vigem_target_free` alone orphans the device until then.
- That process-exit behaviour is documented, not tested here. The owner will not rely on it.
- `watch_pad` (`agent/startup.py:51-96`) assigns closures onto `pad` that close over `pad`. That is a reference cycle.
- `Live` is also kept alive by its watchdog thread until `_closed` is set.
- Dropping references therefore does not remove the pad at a known time.
- `update()` goes through `check_err` (`virtual_gamepad.py:219-223`), so it raises after a removal.
- `Live._write` always writes neutral, including from `close()` and the lease watchdog (`agent/controller.py:232-239`,
  `:266-286`).

**Minimum design.** It needs exact-byte review, because it changes `agent/controller.py`:
1. **An owned detach under `Live._lock`, idempotent:**
   - set `_dead`;
   - write neutral once;
   - call `vigem_target_remove` on the owned target at most once, and record the result;
   - swap in an inert pad, so later `_write`, `release()`, `close()` and watchdog ticks never touch the removed target;
   - set `_closed` so the watchdog exits.

   A second detach must do nothing.
2. **Free exactly once.**
   - Either `vigem_target_free` stays with `__del__`, with `__del__`'s second remove neutralised for a detached
     instance, or the detach frees and `__del__` is disarmed.
   - Neither path may remove or free twice. The installed ViGEmClient's behaviour on a double remove is not
     established.
3. **Order on any failed initialization:**
   - this means any exception from attach through the end of the settle and pose check, whatever the report count;
   - detach first, then any synchronous evidence encoding;
   - if the detach itself fails, record that and leave the process promptly. Process termination is then only the
     documented fallback, not the mechanism.
4. **Offline tests with a fake ViGEm client:**
   - remove and free called exactly once, including through `__del__` when the `watch_pad` cycle is collected;
   - a lease expiry racing the detach;
   - `send_guarded`, `release()` and `close()` after detach are refused or no-ops;
   - detach while `collect_segment`'s `finally` releases;
   - a detach failure recorded without masking the original stop.

## Prime first, with bounded recovery in which priming is unknown

**Steps.**
1. **Attach, then the existing guarded prime at once.** The code is unchanged: every renewal is proven, 100 ms
   freshness, leases of 100 ms or less. With no stall this path is today's behaviour.
2. **A freshness or capture-unavailable stop during initialization.** This covers a stop before the response pair
   exists, whether before or during the prime. The actuator is already neutral. The pad's priming is **unknown**, and a
   report that returned proves nothing. Wait neutral:
   - the deadline is fixed at 2 s from attach and is never restarted;
   - it needs at least 200 ms of consecutive fresh, fully guarded frames;
   - focus, key, range, idle, scope and capture errors stop at once, followed by the detach.
   - During this wait the view may drift, by up to about 49–98 degrees at the 2 s bound.
3. **Then the existing prime exactly once more, as the response prime.** It has the same shape and guards. Its response
   analysis, then the 5 s settle and the fixed-reference pose check, are what first establish that the camera now
   responds and is stationary. The lead's ready-0 inspection follows.
   - There are at most two prime executions per block, and the second is allowed only after the first was cut short by
     freshness.
   - A second gap, a missing response, or drift or a changed pose in settle ends the block, with the detach.
4. **The recovery's cost is bounded, not zero.** Only the recovery path carries priming-unknown drift. It lasts for the
   stall plus the streak, 2 s at most, and every failure out of it detaches. The second prime is new commanded input,
   a bounded right turn of about 58 degrees, and needs its own exact-byte pre-run review.

**Offline checks.**
- a fake clock replaying yaw-03: first report, then a gap of about 483 ms, then a fresh stream, with exactly one response
  prime, no report before the streak, and the recovery marked priming-unknown;
- a stall before the first report, with no unproven report and a detach on failure;
- valid fast-start controls with one prime and no added wait;
- persistent staleness to the fixed deadline, then the detach;
- every semantic stop during the wait, then the detach;
- a gap during the response prime, then the detach;
- a drifting view in settle that never reaches measurement, then the detach.

## Not accepted here

This review does not accept a cause for the stall, a drift rate for the current account, whether a report cut short
primes the pad, ViGEm unplug on process exit, a yaw rate, a focal length or a camera map. The implementation needs an
exact-byte pre-run review of the driver and `agent/controller.py` before the lead grants live use.
