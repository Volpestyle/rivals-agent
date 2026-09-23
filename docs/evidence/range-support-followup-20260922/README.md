# Existing-footage support and fragment contract followup

The bounded search added **zero training examples**. The completed Galacta
pilot and its model remain unchanged. Natural courtyard training is requested
in [VUH-1351](https://linear.app/vuhlp/issue/VUH-1351); independent validation
remains VUH-1347. No standing-idle footage is needed.

## Existing source checked before asking for more

Human-admission inspected the remaining received RMB rises in the earlier
normal-resource recording, using saved frames and the existing raw-input ledger.
There are seven additional timing/history-eligible coordinates. The earliest,
n122, has five complete gameplay observations and ammo 5 throughout. Its
causal detector/selector has no target. It also lacks the raw-release event
required by the current positive schema; focus establishes an up-state, which
must not be falsely recorded as a release event. Missing history is not its
problem. This does not invalidate the received input or original recording.

The two remaining candidates with nonempty detections were checked through the
actual reset-window perception/selector. At n154, Luna is visible but the final
selected target is absent. At n211, the selected box covers a bar/nameplate
region without an identifiable bot body. Root inspected both original anchor
images. Neither supplies target-agreed supervision; no extra video decoding or
cast-association pass follows. Earlier admitted rows, profiles and masks remain
unchanged. This is a bounded result for these locators, not a proof that every
possible example in the original recording is unusable.

The corpus owner's two reports and exact measurements are copied verbatim in
[remaining-request-support](remaining-request-support/README.md), with the
[two-window result](remaining-request-support/reset-target-check/README.md).
These are diagnostic findings, not additional admissions.

## Tracker and controller disagree about body fragments

The tracking issue is separate from the model's no-start predictions. In slot 4,
12 first-consumed decisions (53–58 and 155–160) meet the controller's
`target_missing_or_ambiguous` refusal. Every one already proposes `no_new_start`.
The recorded decision boxes and later reflex boxes are kept separately.

`Tracker.update` intentionally returns the original fragments with a shared ID;
its existing tests require this. The range-skill controller requires exactly one
current detection with that ID. A real pure Tracker → State → Controller pair
reproduces the mismatch: a whole centered bot allows a start, while its two
tracker-associated body fragments reject it and clear arming. The no-new control
also changes from guarded movement to neutral. Native logged geometry reproduces
the shared five-fragment ID under explicitly synthetic preconditioning.

Root inspected saved slot-4 frames 000048, 000049 and 000054: the nearby named
Galacta remains visible across the fragment interval. These are nearby reflex
images, **not exact decision images**; their clock differences are retained in
[the diagnostic report](fragment-contract/report.json). No model was loaded or
inference rerun. No input device was instantiated.

Disposition: keep the demonstrated contract gap on
[VUH-1314](https://linear.app/vuhlp/issue/VUH-1314). A repair should expose one
explicit current body observation from tracker-owned associations, while keeping
raw fragments and refusing genuinely conflicting identities. Removing the
duplicate-ID guard or unioning arbitrary same-ID boxes is not accepted by this
diagnosis. Any resulting change to selected-target geometry needs corresponding
feature/provenance treatment and the existing input-path review. No repair or
deployment is claimed here, and this finding does not explain the pilot's zero
learned start proposals.

All copied artifacts are byte-pinned by `archive-manifest.json`. The original
slot-4 log hash was verified before and after the pure diagnostic. Reproduction:
from repository root run the original
`data/diagnostics/range-fragment-contract-20260922/diagnose.py` with
`uv run --offline --no-project python -B`; its only output is its sibling report.
