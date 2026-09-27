# a2: verify pulse-block pad initialization

Owner live-loop; VUH-1384. Input-only delta from accepted a1 (8580cea).
No desktop, game input, capture or GPU used. Owner tests: 29 passed; Ruff passes.
Exact 11 source pins: source-hashes-a2.json. Old packets remain unchanged.

The live-game skill records that a fresh pad may swallow its first input and
may yaw while neutral after attach. A short measurement must not silently be
that first command. Pulse mode now has one fixed initialization per block:
positive 0.45 rx for 120 ms, no new CLI setting. Full-turn mode is unchanged.

After the existing 3-second attach settle, ready-prime.png/json is produced
while neutral. The lead inspects the pose and atomically writes its token to
continue-prime.json remotely; no PC keypresses. This is the first non-neutral
input. A neutral native still is taken before and after initialization, with
350 ms neutral settling on each side. The existing guarded collect_segment
path sends the fixed command, renews at most every 40 ms after fresh full
proof, caps leases at 100 ms and the initialization end, and releases in
finally. The independent keyboard/focus/deadline monitor remains active.

The accepted l4.checked_shift must observe the commanded negative horizontal
scene shift in YAW_BOX. No motion, wrong direction or unreliable registration
writes a refusal and stops the entire block. There is no retry. This proves
observed directional motion, not USB acknowledgement or device delivery time.

Initialization moves the pose approximately 19 degrees at the historical
half-stick rate; that estimate is not calibration. The next iteration saves a
NEW ready-0 frame and requires its own token. Reinspect the bot-free pose after
initialization; never approve measurement from ready-prime. Pitch signs still
alternate near clamps; no return pulse is sent.

Manifest pulse_initialization, initialization.json and successful/failed result
references label initialization_excluded. Its NPZ and before/after native
frames are retained separately; on/off monotonic times identify the excluded
full-report/video interval. Initialization never enters measurement segments.
All candidate camera values remain unverified until native evidence is audited.

New tests cover the exact token/init/reinspection/pulse order, swallowed first
input refusing without a pulse or retry, and rejected initialization token
sending no input. Existing 26 tests retain the guarded leases, blocked-capture
stop behavior, full-rate retention and signed l4 pulse checks.
