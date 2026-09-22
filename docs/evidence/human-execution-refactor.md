# Human execution pipeline evidence

This refactor retains the historical VOD experiments, dataset loader and guarded
virtual-pad runtime. New recordings and checkpoints use the explicit
`keyboard_mouse` control domain. No learned live control has been run.

## Recorder integration

Recorder source and schema: `C:\Users\volpe\obs-input-logger\SCHEMA.md`.
The recorder owner installed the OBS plugin. That work is separate from this repo.

The blank-scene integration session `20260922T031536-308Z-34988-1` has 714
pre-muxer callback rows and 711 decoded file frames. The lead independently ran
`check_session.py SESSION --verify-video`: all 711 frames match, with a 21 ms
muxer PTS shift and maximum rounding residual 1/3000 second. Three callback-tail
packets were never written. There are no recorded queue/raw/writer errors and all
composition timestamps are present. The pause/resume path is included. It contains
no gameplay or physical inputs and cannot be used as a training demonstration.

The recorder owner's first physical-input verification is at
`C:\Users\volpe\obs-input-logger\verification\20260922T032454-642Z-24328-1.md`.
That 1440p/120 FPS, approximately 30-second recording has 3,609 decoded video
frames, 3,610 callbacks, 2,501 relative mouse packets and 115 keyboard packets.
Its original video is `C:\Users\volpe\Videos\2026-09-21 22-24-54.mkv`.
The reported pixel inspection identifies Spider-Man in the practice range. The
lead independently reran `check_session.py SESSION --verify-video`: all 3,609
frames match, with one unwritten callback-tail packet, a 21 ms muxer offset and
maximum 0.333334 ms rounding residual; no recorded loss or writer error.
Settings, patch and capture/display/input-delivery latency remain unverified;
recorder verification alone is not training admission.

## Review findings

An independent read-only data review reproduced three defects in the initial
importer: an unconstrained muxer-offset fit hid leading frame loss, generic/sided
modifier aliases left stale unknown holds, and multiple input devices could
produce false released-state labels. These now require an independent PTS anchor,
normalize modifier aliases while preserving the unobserved side, and gate admission
to one participating keyboard/mouse. A zero-effect ancillary mouse packet does not
count as a second control source. All raw packets remain available for inspection.

Review caught one follow-up regression: distinct keys with zero scan codes collided.
The importer now retains their VK identity; the execution consumer rejects zero-scan
controls because their physical mapping is unsupported. The reviewer independently
replayed the failures and accepted the importer boundary: **66 passed, 1 skipped**.
Accepted/rejected/unresolved imitation suitability is required per segment, with
only accepted segments supplying training examples. This is software acceptance,
not acceptance of the first physical recording into a corpus.

The independent design review accepted the source, hardware and control-domain
decisions and a bounded, preregistered AI-only engage/execute/continue-or-escape
evaluation contract. That evaluation has not been run. Linear VUH-1307 is complete.
The historical VOD audit VUH-1326 was closed against its already accepted review and
format-5 migration evidence; its commits remain in this branch's ancestry.

## Executable verification

The locked Windows environment uses PyTorch **2.14.0+cpu** and torchvision
**0.29.0+cpu**. `uv run --group execution pytest -q` passed **528 tests**, with
**12 skipped**. No sealed corpus payloads or live input were used.
After `uv sync` restored the stdlib-only environment, `uv run pytest -q` passed
**521 tests**, with **13 skipped** (including the optional execution module).

The execution consumer's seven tests include actual generated FFV1 videos, raw
session import, causal sample creation, two training epochs, checkpoint loading,
exact nonconsecutive frame decoding and repeat validation. The producer also ran
the saved checkpoint through the real `python -m policy.execution evaluate` entry
point and reproduced its validation report exactly. Synthetic training loss fell
from 0.780476 to 0.776323 on eight train windows; validation used eight windows from
a separate synthetic session. Those numbers establish plumbing, not gameplay.

Independent read-only review accepted the execution consumer after rerunning its
seven tests and separately checking persistence/prior arithmetic and unknown-start
edge masking. No unresolved correctness findings remain in the reviewed delta.

MPS/CUDA runtime behavior and pretrained-encoder gameplay adequacy remain unmeasured.
The installed CPU wheel does not enable CUDA; GPU training requires the appropriate
platform build and a separate resource/latency check.

## Limits

The software target is a usable, reviewed offline training path. Demonstrating
expert execution, generalization to new sessions, motor-domain transfer, and
strong full-match play requires actual accepted demonstrations and evaluation.
The existing virtual-pad safeguards and rejected synthetic-mouse boundary remain
binding. Sealed VOD payloads are not part of this refactor's verification.
