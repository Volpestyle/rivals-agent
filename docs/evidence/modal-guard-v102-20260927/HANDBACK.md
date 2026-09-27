# Modal guard v1.0.2: suspend-inclusive accounting

Delta for fit-review, no acceptance installed and no paid use. Previous v1.0.1
review closed F1, original F2 and the bootstrap gap; its remaining suspend F3 is
addressed here. Both older frozen packets stay unchanged.

Release: `732dc08f9d0351b3a601a0a613dbc31f5c2476b6eaddc8cb49e1575d004b78ce`.
Mac bundle: `eea1077bcab0a581bc9de25b3eea2c602b02955bfff42693790ec06f538b259a`.
Source/test closure: validation.json. Packet closure: SHA256SUMS.txt, LF blobs.

## Change

Every paid host duration/freshness/deadline now defaults to elapsed_time():
macOS clock_gettime(CLOCK_MONOTONIC_RAW), Linux CLOCK_BOOTTIME. Apple Libc maps
Darwin RAW directly to mach_continuous_time; CLOCK_MONOTONIC instead subtracts
boot time from gettimeofday. The default Python time.monotonic is awake-only on
this Mac and is no longer the paid host clock. Clock identity includes a new
suspend-inclusive contract prefix plus the kernel boot UUID. Old awake-only rows
cannot silently reuse the new time base; they refuse continuation and retain
allowances when continuity is unavailable. No live journal was migrated.

Terminal seconds are MAX(0, wall-forward delta, continuous elapsed), never MIN.
The reviewer example now retains $1.00 for 100 elapsed seconds and refuses the
next $1.80 reservation at a $97.75 baseline ($100.55 commitment). The same bound
holds for sleep combined with a 90- or 110-second wall rollback. Missing/changed
boot and backward elapsed clocks retain conservative allowances as before.
The driver and watchdog each hold their own caffeinate -i -w PID child through
teardown; only those owned inhibitor children are terminated/reaped. Native Mac
inhibitor startup was exercised without a cloud call. Idle sleep inhibition does
not promise protection against forced sleep, host failure or a lost network.
Expired work after wake gets the existing emergency stop, never fresh funding.

## Validation

- Windows: 77 passed, 3 platform skips.
- Mac / Modal SDK 1.5.5: 80 passed, including the actual adapter seam, cross-process
  boot identity and RAW clock bracketed by native continuous ticks.
- Native read-only capture shows continuous time about 3292 seconds ahead of the
  awake-only Python clock, and the owned caffeinate process alive.
- Three new mutants killed: awake-only Darwin clock, MIN settlement, and omitted
  caffeinate -i. Prior F1/F2/bootstrap mutations and accepted delta evidence are
  unchanged; the full suite includes all their regressions.
- Ruff passes. No host sleep, wall-clock modification, paid launch, image build,
  volume mutation, sealed input or live workspace ledger operation occurred.

## Transport and consumer status

The disclosed v1.0.1 mutation JSON normalization is addressed by commit 7bc87aec
in docs/evidence/modal-guard-v101-transport-20260927/: exact original bytes plus
committed LF pins. No old freeze was rewritten. This new packet explicitly uses
LF; its Git blobs are checked against every packet pin before handoff.

Bootstrap/image/spec API is unchanged from v1.0.1. Consumers must pin this new
release in the host checkout AND immutable worker image/manifest. No compatible
image is built here. Explore still waits for fit-review LAND and a matching
lead-installed acceptance before the six-app shakedown. Short probes never become
full-fit p95. The approved $24 campaign allocation is not increased by this patch.

Mac tested source: /Users/james/dev/range-bc-data/handoff/modal/shared-library-v102/.

Sources: [Apple Libc clock mapping](https://github.com/apple-oss-distributions/Libc/blob/main/gen/clock_gettime.c),
[Apple continuous-clock declaration](https://github.com/apple-oss-distributions/xnu/blob/main/osfmk/mach/mach_time.h).
