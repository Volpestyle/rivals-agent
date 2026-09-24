# Human demonstration execution contract (v1)

Owner: importer lane, VUH-1309 / VUH-1326. Consumer: w2:p1 execution policy.
This is a new keyboard/mouse domain; it does not change `agent/demos.py` or
translate human controls to gamepad controls. Independent review is required
before relying on this importer for training/evaluation admission.
*Superseded 2026-09-23: semantic actions + degrees through the pad, see [docs/lanes/end-to-end-fit.md](lanes/end-to-end-fit.md).*

## Policy API

`agent.human_demos` is standard-library only. All public record dataclasses are
frozen, with tuples for collections. `Sample` contains `session_id`,
`session_group`, `split`, `segment_id`, `anchor_ns`, `frames: tuple[FrameRef, ...]`,
`past_events: tuple[InputEvent, ...]`, `state: HeldState`, and
`future: tuple[ActionBin, ...]`. `control_type` is always `keyboard_mouse`.
`Sample.observation()` returns only the causal fields (never `future`).

`FrameRef` references the original `video_path`, zero-based decoded `frame_index`,
integer file `pts` and rational `timebase_num/timebase_den`, matched
`packet_index`, and integer OBS `composition_ns`. No copied media or encoder
embeddings are generated. Frames are selected by composition time <= anchor,
never nearest-frame sampling that can choose a future frame.

`InputEvent(t_ns, seq, type, payload_json)` retains every raw field, including
device, VK, scan, flags, relative counts, mouse edges and wheel values. The JSON
string makes the payload immutable; `.payload` returns a fresh dictionary.
`HeldState` has these exact fields:

```python
keys: tuple[PhysicalKey, ...]
unknown_physical_vk: tuple[int, ...]
mouse_buttons: tuple[int, ...]
observed: bool
```

`PhysicalKey(device, vk, scan, flags)` identifies a device/key using the native
VK, scan and E0/E1 flags (`raw_flags & 6`). Device IDs are session-local: use
them to reconstruct holds, not as transferable model features. Every raw event
keeps the original flags, including break/up. Repeated key make events remain
in `events`; they are not necessarily new presses. Compare prior holds before
deriving a press target. Mouse buttons use 1=left, 2=right, 3=middle, 4=X1, 5=X2.

A focus snapshot's held keyboard VKs enter `unknown_physical_vk`, not `keys`.
Generic Shift/Ctrl/Alt snapshot aliases normalize to the observed sided VKs.
If only a generic alias is present, both sides remain unknown. A raw event
resolves only its observed side (Shift scan 42/54, Ctrl/Alt E0 for right).
An observed make resolves that side's physical identity; a release clears it.
Opposite-side uncertainty is preserved. Raw generic and sided VK values are
retained; held-key updates match device, scan and extended flags, so a sided
release correctly clears a generic make. Repeated makes cannot duplicate holds.
The `physical_keys_known` property is `observed and not unknown_physical_vk`.
Mask physical key labels until that condition holds. Snapshot mouse VKs map
directly to button holds. Focus snapshots themselves are never press events.
An unobserved state is unknown; its empty tuples must not be read as neutral.
Admission explicitly requires one participating physical keyboard and one
participating physical mouse, attested in `device_scope`. A participating
device is one that emits a control-affecting packet: every keyboard packet;
mouse movement, button edge, wheel event, or absolute-position packet. Raw
ancillary mouse packets with zero motion, buttons and wheel remain preserved
in `InputEvent` but do not make their device a second control source. Multiple
participating device IDs within either control class reject the session before
holds are used. This conservative restriction avoids falsely releasing a
button while a second device still holds it. Snapshot VKs have no device
identity: the review attestation is necessary, since a second device held
throughout a focus interval may never emit a packet and cannot be excluded
from logs alone. Full multi-device hold reconstruction is an unsupported gate,
not a guessed merge.

Each `ActionBin` covers `(start_ns, end_ns]`, strictly after the anchor, with
raw `events`, `held_start`, `held_end`, relative `mouse_dx/mouse_dy` (null for
absolute/unknown motion), and wheel totals. No future event is in observation.
The first bin starts at anchor; bins are contiguous and non-overlapping.
`relative_motion_known` is false when either mouse delta is null. A valid,
focused interval with no mouse packet has known zero relative motion. An
absolute packet makes that bin's aggregate relative motion unknown; its raw
coordinates and independent buttons/wheels are still retained. Malformed or
missing motion mode is rejected, not guessed. Motion is raw counts, never
pixels, angular velocity, normalized stick input or controller buttons.

Consumer entry points:

```python
from agent.human_demos import load_dataset, export_dataset

dataset = load_dataset("imported-demo.jsonl", splits="session-splits.json")
samples = dataset.samples(history_ns=500_000_000, frame_step_ns=100_000_000,
                          bin_ns=100_000_000, bins=5, stride_ns=100_000_000)
for sample in samples:
    model_inputs = sample.observation()
    labels = sample.future
export_dataset(dataset, "samples.jsonl", history_ns=500_000_000,
               frame_step_ns=100_000_000, bin_ns=100_000_000,
               bins=5, stride_ns=100_000_000)
```

Import is explicit: one named session directory, one human review document,
one complete session split registry, one output file. No directory discovery.
Train/val/test splitting is by session group; test access requires deliberate
`unseal=True` / `--unseal-test`. Refusal happens before session/media/sample reads.
The split registry is supplied again on load to catch changed placement.
Use `load_datasets([explicit_paths...], splits=...)` when assembling a run: it
also rejects duplicate sessions, identical media hashes in different groups
or splits, and mixed patch/cooldown values. Group all recordings from the same
play session together, including restarted OBS clips. Filename differences
are not session independence. Registry groups are human assignments: neither
the importer nor timestamps can prove independent humans/play sessions.

Import preserves the recorder's uncalibrated capture latency. Reviewed provenance
must include settings, bindings, game patch and cooldown regime. Samples for
training require either a documented alignment assumption or a measured latency
bound with evidence. Composition time is an OBS clock, not perfect behavioral
synchronization. Focus/pause/gap boundaries must never be crossed by a sample.

## Review and split inputs

One complete registry for the experiment, `session-splits.json`:

```json
{
  "schema_version": 1,
  "sessions": [
    {
      "session_id": "replace-with-recorder-session-id",
      "session_group": "human-play-session-001",
      "split": "train",
      "video_path": "C:/Users/volpe/Videos/recording.mkv"
    }
  ]
}
```

Paths may be absolute or relative to the registry. Each session appears once;
a group and an original media path cannot appear in multiple splits. `split`
is `train`, `val` or `test`. Optional `sealed` must equal `split == "test"`.
Choosing `test` seals the session even when `sealed` is absent. Changing the
registry after import invalidates the artifact's placement, rather than
silently moving samples. The registry itself opens no session or video.

### Importing unchanged Windows recordings on another machine

The recorder's `metadata.json` is immutable, including its Windows `video_path`.
Copy the finalized session's metadata, input log, frame log and original video
without rewriting metadata or remuxing/re-encoding media. Compute SHA-256 on the
finalized source video on Windows; in PowerShell:

```powershell
(Get-FileHash -LiteralPath 'C:\Users\volpe\Videos\recording.mkv' -Algorithm SHA256).Hash.ToLowerInvariant()
```

In the destination machine's registry, use a local `video_path` and add both
`recorded_video_path` and `expected_media_sha256`. For example, this one session
row points to a Mac-local path relative to the registry (replace the illustrative
hash with the digest computed on the source machine):

```json
{
  "session_id": "replace-with-recorder-session-id",
  "session_group": "human-play-session-001",
  "split": "train",
  "video_path": "media/recording.mkv",
  "recorded_video_path": "C:\\Users\\volpe\\Videos\\recording.mkv",
  "expected_media_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
}
```

`recorded_video_path` must exactly equal the JSON string in recorder metadata,
including slash style and case. It is an opaque source identity, never resolved
as a local path or opened on the destination. The expected digest must contain
64 lowercase hexadecimal characters. The two relocation fields are optional
only as a pair: omit both for the original same-machine path-identity behavior;
providing one, null, or malformed values is an error. There is no path fallback
and no command-line relocation override.

Use the existing import command with this registry. Import first checks sealed
placement, then literal source identity, then the transferred video's hash before
ffprobe runs. Decoded `FrameRef.video_path` values point to the destination media;
the complete recorder metadata remains unchanged in the artifact payload.
Session identity, group and split retain their existing meaning. A source digest
cannot be assigned to different groups/splits under different local filenames.

Both relocation fields are saved in the artifact placement header and sample
export. Loading requires the same local path, source literal and expected digest
in the supplied registry, checks the current local media bytes, and rechecks
the preserved metadata identity. Changing or removing relocation fields invalidates
the saved artifact; relocating again requires a new explicit import from the raw
session. Older same-machine artifacts with no relocation header fields still load.
Sealed refusal still precedes session metadata, artifact payload and media access.
This transfer mechanism does not supply missing reviews or authorize corpus
admission, training, or test access.

A separate explicit human review, `review.json` (values below are illustrative,
not accepted settings or timing):

```json
{
  "schema_version": 1,
  "session_id": "replace-with-recorder-session-id",
  "reviewer": "reviewer identity",
  "reviewed_at": "2026-09-22T00:00:00Z",
  "device_scope": {
    "kind": "single_keyboard_mouse",
    "source": "review confirms one participating keyboard and mouse; ancillary raw packets are catalogued"
  },
  "pts_anchor": {
    "kind": "independent_muxer_offset",
    "offset_num": 21,
    "offset_den": 1000,
    "source": "reviewed blank-scene calibration under the same untouched OBS 32.0.1 NVENC/MKV profile; 21 ms established independently"
  },
  "provenance": {
    "hero": "Spider-Man",
    "settings": {
      "value": {"dpi": 800, "game_sensitivity": 2.0, "swing_mode": "hold"},
      "source": "reviewed settings evidence location"
    },
    "bindings": {
      "value": {"move_forward": {"vk": 87, "scan": 17, "flags": 0}},
      "source": "reviewed complete bindings evidence location"
    },
    "game_patch": {"value": "exact recorded patch", "source": "patch evidence"},
    "cooldown_regime": {"value": "normal", "source": "reviewed HUD/settings evidence"}
  },
  "alignment": {
    "kind": "assumption",
    "statement": "Use composition time as the labeling clock; capture/display/input latency remains uncalibrated.",
    "source": "explicit experiment decision/reviewer"
  },
  "segments": [
    {
      "segment_id": "gameplay-001",
      "start_ns": 100000000000,
      "end_ns": 110000000000,
      "reviewed_gameplay": true,
      "imitation_suitability": "accepted",
      "suitability_reason": "review found clear, observable action evidence",
      "evidence": "human review of this precise source interval"
    }
  ]
}
```

Use the actual integer monotonic nanoseconds from the recording, not UTC or
floating-point seconds. Reviewed segments are sorted, disjoint `[start,end)`
intervals. Settings, full bindings, patch and cooldown values need sources;
the importer checks presence/structure, while the reviewer establishes truth
and completeness. It does not infer good gameplay from successful recording.
The source must target `Marvel-Win64-Shipping.exe` and identify Spider-Man.

**An independent muxer-offset anchor is an admission prerequisite.** The
example 21/1000 seconds is not approved for a new recording merely because
fitting that recording produces it. Supply independently established evidence
for the current recording/output configuration. A fit to the same timestamps,
a copied earlier fitted result, or a claim that the file is unedited is not an
independent anchor. Without such evidence, import is blocked; timing inspection
may report a candidate offset but may not label frames for training/evaluation.
Anchor truth is part of independent review, like gameplay/provenance truth.

For an externally measured bound use
`{"kind":"measured_bound","min_latency_ns":0,"max_latency_ns":20000000,"source":"measurement evidence"}`.
These example numbers are not a measurement. The bound is documented context,
not an automatic frame shift or proof every action was a reaction to the image.
`{"kind":"uncalibrated"}` permits integrity import/inspection but blocks
training sample generation. Recorder metadata always preserves
`capture_latency_calibrated:false`; accepting a labeling assumption never
changes that fact. Input receive time, OBS composition time and player-visible
game time are different concepts.

## Files and commands

```powershell
uv run python scripts/import_human_demo.py import --session C:/explicit/session --review review.json --splits session-splits.json --output imported-demo.jsonl
uv run python scripts/import_human_demo.py export --dataset imported-demo.jsonl --splits session-splits.json --output samples.jsonl --history-ns 500000000 --frame-step-ns 100000000 --bin-ns 100000000 --bins 5 --stride-ns 100000000
```

`ffprobe` must be on PATH, or provide `--ffprobe C:/path/ffprobe.exe`. Imports
decode actual integer frame PTS via ffprobe and hash the original media with
SHA-256. No images, video copies or embeddings are written. The original
recording and raw sidecars remain in place. Outputs use exclusive creation;
an existing output is an error. Export refuses to create a file if no samples
are eligible. Errors return exit code 1 with a JSON error on stderr.

`--inspection-only` on export sets `for_training=False`; it does not make
uncalibrated examples approved training data. Test access additionally requires
`--unseal-test`, and test sample generation requires inspection/evaluation mode.
Only use these under a separately authorized evaluation. There is no automatic
folder scan, automatic review, automatic split assignment or automatic unseal.

The imported artifact has exactly two JSONL lines:

1. Placement header: `format:"rivals-human-demo-v1"`, `session_id`,
   `session_group`, `split`, `video_path`, `sealed`, `media_sha256`,
   `payload_sha256`, plus `recorded_video_path` and `expected_media_sha256`
   (both null for a new same-machine artifact; absent in older artifacts).
2. Integrity payload: complete `metadata`, explicit `review`, raw `events`,
   callback `packets`, and `decoded` integer PTS, timebase and dimensions.

`load_dataset` reads only the header before a sealed refusal. For accessible
data it checks the payload hash, original media hash and registry, then reruns
admission and matching against the preserved decoded PTS. Hashes catch changed
inputs; they are not cryptographic attestations that a review was performed.

The sample export starts with `format:"rivals-human-samples-v1"` plus placement,
sealing, media hash, review/provenance, timing audit and sampling options.
Subsequent lines are `Sample.to_dict()` records. Tuples become JSON arrays;
`InputEvent.payload_json` remains a JSON string so the in-memory record stays
immutable. Parse `.payload` to get a fresh dictionary. Keep all nanoseconds as
integers (including in any JS consumer; JSON numbers exceed JS safe integers).
Do not feed `future`, future holds, review outcomes, split identifiers or future
eligibility into the temporal model. Decode `FrameRef.frame_index` in presentation
order, not packet order; reference PTS/timebase are preserved for verification.

## Admission and sampling details

- Both raw streams together must cover every event sequence from zero through
  `events_attempted - 1`. Per-stream order, packet indices, metadata counts,
  clean completion, raw registration, required fields and zero loss counters
  are checked. Gaps, duplicate sequences, malformed/truncated records, writer
  errors, missing CTS and raw-input error events reject the session.
- N decoded frames must match the first N callback packets, sorted by rational
  PTS. All remaining packets are a callback-order suffix. This preserves the
  real B-frame stop behavior without accepting an interior missing packet.
  Every pair must be within one file tick of the **independently supplied**
  offset, and pairwise offset spread must be <= one tick. The supported
  timebase must distinguish frames unambiguously. This validates file/packet
  correspondence, not capture latency. Constant-shift fitting alone cannot
  detect a perfectly regular leading trim: dropping the first file frame can
  look exactly like a larger shift and an unwritten stop tail. Consequently
  `match_frames` refuses an absent anchor by default. Explicit
  `inspection_only=True` permits a fitted candidate but returns
  `pts_alignment_verified:false`. `import_session` / `load_dataset` never use
  that inspection exception. A false independent anchor is still a false
  review attestation; it cannot be established by fitting these same pairs.
- Only one video stream/track zero is supported. Repeated CTS are retained as
  separate file frames; duplicate PTS are rejected. Pauses are aligned through
  individual CTS, never one global PTS-to-wall-clock mapping.
- Inputs sort by `(t_ns, seq)`, including same-timestamp boundaries. Each focus
  or pause event closes a continuous interval. Resume needs a new active focus
  snapshot. Inputs outside active focus are invalid, not neutral intervals.
- History and all future bins must fit a single reviewed continuous interval,
  with the final label endpoint strictly before its boundary. Frame requests
  use the last CTS <= request, with full history and no pre-boundary images.
  Capture gaps greater than two nominal frame periods exclude any window
  intersecting the gap. Samples also need recorded video through label end.
  The two-period cutoff is a conservative admission rule, not a measured
  capture latency bound.
- Events exactly at anchor are causal history/state. Events exactly at a bin
  end belong to that bin, never the next. Changing future input values cannot
  change an existing sample's observation. Future validity can remove a sample;
  that admission decision must never be used as an observation feature.
- OS delivery losses invisible to the recorder and very brief focus changes
  cannot be certified away. No perfect physical-event or behavioral alignment
  claim follows from nanosecond storage.
- A segment's `imitation_suitability` is independently reviewed as `accepted`,
  `rejected`, or `unresolved`, with a required reason. `reviewed_gameplay:true`
  only says the interval was inspected; it does not establish imitation
  suitability. Training samples are generated only from accepted segments.
  Rejected and unresolved segments remain available with `for_training=False`
  for inspection and audit, preserving their labels without silently turning
  them into positives or dropping their provenance.

## Verification and remaining evidence

Default targeted suite: `uv run pytest tests/test_human_demos.py -q`. It is
synthetic and does not open `data/`, recordings or sealed sessions. It covers
callback-order B-frame tails, interior frame loss, sequence/event losses,
completion/CTS, focus-held unknowns, physical extended keys and repeats, mouse
edges/holds/wheels/absolute motion, focus/pause boundaries, prefix causality,
integer precision, causal frame flooring, alignment gates, split leakage,
sealed refusal, media mutation and import/load/export CLI round trips.
Relocation regressions also cover exact foreign-path identity, source hash
verification before probing, immutable metadata, required paired fields, stale
registry refusal before payload/media reads, copied-source split leakage and
legacy same-machine artifact compatibility. These tests use generated synthetic
files only; they do not transfer or admit a real recording.
After the final review fixes: **66 synthetic tests passed**, with the blank-fixture
test skipped by default. The authorized fixture previously passed separately.
CLI import help and the import/export round trips passed.

Authorized real timing fixture:
`C:/Users/volpe/obs-input-logger/integration-artifacts/sessions/20260922T031536-308Z-34988-1`.
Direct importer matching reproduced **714 callbacks, 711 decoded frames, 3
unwritten callback-tail packets, +21 ms muxer offset, exactly 1/3000 second
maximum residual**. No gameplay/human input was present. No training import
or samples were made from this fixture. These are unanchored timing-inspection
results (`pts_alignment_verified:false`), not admitted frame identities. A
dedicated opt-in test reruns them:

```powershell
$env:RIVALS_HUMAN_TIMING_FIXTURE = 'C:/Users/volpe/obs-input-logger/integration-artifacts/sessions/20260922T031536-308Z-34988-1'
uv run pytest tests/test_human_demos.py::test_authorized_blank_obs_timing_fixture -q
Remove-Item Env:RIVALS_HUMAN_TIMING_FIXTURE
```

In a restricted sandbox, the equivalent verified runner uses
`uv --cache-dir "$env:TEMP/rivals-human-demo-uv" run --no-sync pytest ...` to
reuse the installed environment without touching the inaccessible default cache.

Authorized physical timing/integrity inspection of
`C:/Users/volpe/Videos/RivalsInput/20260922T032454-642Z-24328-1` reproduced
**3,610 callbacks, 3,609 decoded frames, one candidate unwritten tail packet,
+21 ms fitted offset, 1/3000 second maximum residual**. Combined sequences,
metadata counts and focus continuity passed; 115 key packets and 2,501 mouse
packets span one active focus interval. This is still unanchored timing
inspection (`pts_alignment_verified:false`), not corpus admission.

The physical session contains one keyboard device ID and two mouse IDs. The
ancillary mouse packet has zero motion, button and wheel effects; the
control-affecting mouse is device **65618** with 2,500 packets. It therefore
does not constitute a second participating control source under this importer,
although the session still lacks the required reviewed settings/provenance and
independent target anchor. Full multi-device hold reconstruction remains a
documented unsupported gate. No training artifact or samples were produced.
The recorder's separate report is
`C:/Users/volpe/obs-input-logger/verification/20260922T032454-642Z-24328-1.md`.
Settings, patch, bindings and latency provenance remain unknown.

The first independent review identified leading-frame loss disguised as a
fitted offset, generic/sided modifier alias uncertainty, and multi-device hold
collapse. The fixes require an independent offset anchor, normalize snapshot
modifier aliases while preserving the opposite side, and restrict admission
to an explicitly reviewed single keyboard/mouse. Regression tests exercise
all three reported cases. The follow-up review caught zero-scan key identity
collisions; those are fixed by retaining VK identity when no scan code exists.
The execution consumer refuses unsupported zero-scan controls. Final independent
review accepted these software boundaries and the imitation-suitability gate.

Still required for an actual corpus admission: independent PTS
offset evidence, a reviewed focused human recording at the real game workload,
inspection of key/mouse/focus/pause labels on that recording, actual
settings/bindings/patch/cooldown provenance, single-device review,
session-independent train/val/test assignment, and an explicit alignment
assumption or measured end-to-end latency bound before training. No physical
keyboard/mouse execution or keyboard/mouse-to-pad transfer is established here.
