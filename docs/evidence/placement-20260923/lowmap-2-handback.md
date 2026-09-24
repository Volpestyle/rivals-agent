# lowmap-2: review-lowmap L1-L4

Lane pilot-prep. No commits, no Linear writes, no game input. Re-check: admission-review.

## L1-L3 (`scripts/place.py` lowmap_fit)
- **L1:** each hold's magnitude is normalised to the nominal hold (|deg| / held_s × hold_s). A moving deflection
  whose forward and back magnitudes disagree, per repeat, becomes `mixed` and the result is not ok. So does one whose
  two repeats' means disagree. The tolerance is max(25 %, 0.5°).
  - The reviewer's construction (forward 1.6×, back 0.9×) is now not ok ("holds disagree").
  - A 1.5× repeat is not ok.
  - 1.1× / 0.95× stays ok.
- **L2:** any hold whose off-axis rotation exceeds max(the still threshold, 20 % of the on-axis) makes the result not
  ok. The reviewer's 15° construction is now not ok; 0.1° stays ok.
- **L3:** Cal's four fields are written as `cal` only when ok, and otherwise as `cal_candidate`. `main` prints `cal`
  only when present, so only when ok.
- **Re-judge:** `python scripts/place.py --lowmap-judge FILE [--out FILE]` runs offline with no pad.
  - It re-runs `lowmap_fit` on a saved file's raw `rows`.
  - It writes `<stem>.rejudged.json` with `rejudged_from` {path, sha256} and `judged_by` {place.py sha256}.
  - It refuses non-lowmap files and refuses to overwrite the source.
  - An old "ok" file whose rows fail the new rules comes back not ok.
  - Saved lowmap files now also carry `judged_by`.
- **Review note on answer 4:** `held_s` is now the stick's on-time, stamped by `_hold` at the first send and at the
  release, instead of around the call. `_hold` takes an optional `stamps` list; it is unchanged otherwise.

## L4: the physical-input kill switch (`agent/physical_input.py`, new)
- **The sentinel** is a separate process: `python -m agent.physical_input --sentinel --parent PID`.
  - It uses a message-only window with RegisterRawInputDevices for mouse (1/2) and keyboard (1/6), with
    `RIDEV_INPUTSINK`, so it hears input while the game has focus.
  - It says READY only after registration succeeds, then sends a heartbeat every 100 ms.
  - It trips on a control-affecting packet from a real device handle, using the importer's rule: any key; mouse
    motion, buttons, wheel or absolute. Handle 0 (injected) never trips. The trip latches.
  - Armed, a trip that the executor doesn't ACK within 1 s makes the sentinel TerminateProcess the executor. That
    unplugs the ViGEm pad, so a hung executor can't keep driving.
  - It exits when the executor exits.
- **Client (`PhysicalInput`):**
  - `start()` refuses without READY within 5 s.
  - `check()` returns a stop reason for:
    - a sentinel that isn't running;
    - a heartbeat older than 0.5 s;
    - a trip (the first armed trip sends the ACK).
  - `pre_run()` is the positive test: a physical touch must trip a dry loop of the same `check()` within 30 s. Then
    there must be 3 s with no input while the game is in front (within 90 s). Only then does it REARM, and it
    requires the sentinel's ARMED reply.
- **In `place.py`:**
  - The kill switch applies to every measurement mode (`--measure-pitch`, `--reset-check`, `--lowmap`) and to
    `--live`.
  - Order: declaration gate, then `_physical_input(pid)` (start and pre-run), then `_open_game`, then the pad side.
  - Proof checks `physical.check()` first, before every write and every settled frame.
  - `Live`'s commit guard also requires `physical.check() is None`.
  - `physical.close()` runs on every exit.
- **Test hook:** the sentinel accepts `TEST_TRIP` on stdin, which fakes a device trip. It can only stop more, never
  allow input.

## Tests
- `tests/test_physical_input.py`: 24 pass (stdlib). They cover:
  - the packet rule;
  - the client against a fake sentinel: touch, latch, dead or silent sentinel, no READY, pre-run pass/no-touch/game
    not in front;
  - the proof stopping `_hold` after one write, then releasing;
  - every input mode (4) refusing before Live when the touch test fails.

  The real Windows sentinel ran on this PC, always with a dummy parent process, never pytest. It:
  - registered with INPUTSINK and kept a heartbeat;
  - terminated the dummy after an un-ACKed armed TEST_TRIP;
  - left the dummy alone after an ACKed trip;
  - exited with its parent;
  - passed pre-run end to end.

  A real device's packet can't be produced in a test; the pre-run touch test proves it at the session, every
  command.
- `tests/test_place_lowmap.py`: 21 pass (perception group). There are 10 new tests for L1-L3, re-judge and on-time.
- With the perception group: test_place_lowmap, test_physical_input, test_place, test_controller and
  test_place_frames give **167 passed**.
- Full stdlib suite: 2954 passed, 5 failed. None of the failures involve these files:
  - `test_replay_states` ×3 and `test_scoreboard` ×1: `data/run1/*` is missing on this checkout;
  - `test_hud_accuracy`: a latency bound under load, which passes alone.
- ruff clean.

## Docs
- `docs/next-pc-session.md`:
  - kill switch now: physical key/mouse, Alt-Tab/click away, Ctrl-C;
  - the touch-test procedure (move the mouse, Alt-Tab to the game without clicking, 3 s hands off, "Armed");
  - step 3 also shows the FOV setting (review "also noted");
  - step 5's kill switch, the L1-L3 ok conditions, `--lowmap-judge`, and the review line.
- `docs/lanes/placement.md` §8: the kill switch block (sentinel, pre-run test) and row D (L1-L3, `cal_candidate`,
  `--lowmap-judge`, on-time, tests, review status).

**Not done:** the review's "camera acceleration" note (whether Cal's maps were measured at comparable hold lengths)
is not addressed in code. `--lowmap` reports rates over 1.0 s and 0.5 s holds; a comparison would need the l4 yawmap
hold lengths (0.10 and 0.25 s).

## Bytes (sha256)
| file | sha256 |
|---|---|
| scripts/place.py | 5685148deadd6b737a7cdd2f26d189d3e1548435782fa02160c5069e46ad39c6 |
| agent/physical_input.py | 3f4357b7973d64f0b9291f021a1119708aca8c883960097e99e43603f59fa4dd |
| tests/test_place_lowmap.py | dc2833237f6c6bacad12f51f56dd3dd44ad39e9956ef27e24b6103b982a04aaa |
| tests/test_physical_input.py | 48138ec274dccaf4162d9070bf9d8dce0137224ad59917bfddb5328e08863a12 |
| docs/next-pc-session.md | 1fa52c618495aee1679913422caf059179a27498d3665aba9eb4b977009c4e25 |
| docs/lanes/placement.md | 3caa557a6bd4625fd11cdea73a2069bfde1ad6c102eac32e59d98606131f58dc |
