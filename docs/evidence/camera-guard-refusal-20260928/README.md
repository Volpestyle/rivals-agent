# Sitting d: guard refusal diagnosis and evidence repair

The cause of yaw-01b's `range/idle/freshness stop` remains **unknown**. The driver
lost the failing capture and combined several checks into one error. No safety
threshold, capture timeout, prime, input type, token gate or recovery behavior is
relaxed by this repair. This packet is uncommitted and awaits independent live-review.

## Native evidence

Authorized source: `C:/Users/volpe/Videos/2026-09-28 21-00-33.mkv`, 3,720,823,490
bytes, HEVC 2560x1440, 120 Hz, 1/1000 time base. No full-file hash was performed.
The manifest wall/performance-clock pair estimates the prime at 21:05:16.194 CDT,
approximately PTS 283.194 s using the filename's second-resolution start time.
This is an approximate alignment, not a verified OBS/performance-clock anchor.

The bounded CPU replay streamed all 1,200 native frames in PTS [279,289). Every
frame passed the unchanged `record.in_range`; none triggered `idle_warning`.
Inspected native frames at 282.004, 283.504 and 284.504 s show the same rock/banner
view, keyboard prompts, and no Switching Devices banner. These observations do
not establish which clause failed on the separate DXCAM capture. In particular,
OBS cannot establish its capture age, foreground window or key state.

The original generic error came from the outer `proof()` check, not controller
commit. Its clauses were focus, keyboard, scope, range, idle and freshness.
The `guard:1` queue drop was a **passing** proof: journaling follows all checks.
Increasing the journal queue would not retain a frame that failed before enqueue.
The outgoing prime report lasted 87.6732 ms before neutral. A stale DXCAM proof is
consistent with these records but is not proven; no cause-specific relaxation is
justified. The absent visible turn is not proof that the pad report was accepted.

All decoded artifacts remain off C:, under
`D:/rivals-diagnostics/live-loop-guard-20260928/native-279-289-attempt2/`.
`result.json` pins 20 retained native PNGs; `frames.json` records all native PTS and
HUD checks. Decoder duration 54.922 s, parent peak RSS 140,996,608 bytes, CPU with
two HEVC slice threads, BelowNormal under the existing PCGuard. No GPU, desktop,
input, sealed source or recording modification was used. All own jobs exited.
The first attempt stopped on PCGuard's 3 s `tasklist` timeout before retaining
pixels; its `ABORT.json` is preserved in `native-279-289/`. The guard was unchanged.

## Repair boundary

- Ordered, short-circuit guard checks now name focus loss, keypress, scope expiry,
  range loss, idle warning and reader errors. Capture, freshness and report-timing
  failures get distinct clauses. Known controller commit/actuator failures are
  classified from their existing exact errors and saved callback audit.
- Failed-proof pixels are held in RAM independently of the droppable journal.
  `guard-refusal.png`, its hash/shape/capture timestamp and `guard-refusal.json`
  are encoded/written only after `Live.close()` neutralizes the pad. Failure JSON
  links them and names the clause. Disk-write failure is explicit and cannot
  resume input.
- A failure before a new capture (focus, key, monitor, capture error) labels the
  retained image **last_available**, not the failing observation. A checked
  capture is labelled **checked**. No frame is fabricated if none was available.
  Controller fallback includes the original error and preceding callback audit;
  an unrecognized controller error stays unknown rather than inferred.
- Passing frames incur no new full-frame copy. Existing prime, settle, leases,
  pad sends, motion/pose checks and token ordering are unchanged. The old v3
  receipt must fail on the changed driver/tests until live-review issues a new one.

## Verification and limits

125 owner tests passed, 12 corpus tests skipped (13.14 s); Ruff passed. Controls
cover each named failure, short-circuit order, reader exceptions, monitor stops,
controller commit/actuator errors, a dropped passing frame followed by a retained
failure, no available image, and disk-full encoding failure after neutralization.
Two actual images (sitting-d ready-attach and native PTS 283.504) pass fresh proof,
then correctly refuse an **injected** stale timestamp and retain identical pixels.
That injection tests the repair; it does not diagnose the sitting's cause.

Qualification outputs and scripts are pinned by `review-inputs.json` and remain
on D:. `delta.diff` is the exact driver/test delta from accepted v3 source
`6e3b7b0622478ab39c4af4263044821245b7c086`. No changes are staged or landed.
An independent delta review, receipt and committed-checkout verification are
required before the lead's next sitting. Lead owns desktop operation and Linear.

Proposed VUH-1384 current-result text: Sitting d produced no camera measurement.
Native replay around yaw-01b passes the existing range/idle checks on all 1,200
frames; the lost DXCAM frame leaves the original failure clause unresolved.
Guard diagnostics now retain refusal pixels after neutralization and identify
the failing clause (125 tests passed, saved-frame controls passed), pending
independent pre-run review. Focal and signed camera maps remain unaccepted.
