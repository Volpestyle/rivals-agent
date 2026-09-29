# Camera turn analysis — VUH-1384 — 2026-09-27

**Status (2026-09-29): HISTORY.** The first alt rate (153.9°/s at RX +0.45) came from a native turn count ([camera-native-turn-20260929](../evidence/camera-native-turn-20260929/README.md)), not this estimator; calibration is now open-loop ([`scripts/calibrate_camera_schedule.py`](../../scripts/calibrate_camera_schedule.py)).

Owner: camera-analysis; next consumer and integration owner: live-loop.
Scope: the new offline `perception/camera_turn_analysis.py`, its synthetic tests,
and this note only. No capture, actuator, native-game, GPU, corpus, or Linear
writes. This is exploratory analysis under James's `2e00d3f`: owner tests, no
independent code-review gate. No calibration is accepted by this work.

## Delivered API

`analyze(rows, on, off, deflection)` takes the same positional arguments as
`scripts/measure_camera_turns.py:return_candidates`. Rows contain monotonic
timestamps and the original 150x265 l4 bands. The original candidate fields are
preserved: `acceptance`, `motion`, `returns`, `correlations`, `periods_s`,
`repeatability_pass`, and `candidate_signed_deg_s`. Additional fields retain
return sample brackets, timing uncertainty, interval angle brackets, rate bounds,
and explicit `refusal_reasons`. Results are JSON serializable with `allow_nan=False`.

Refusals return `candidate_signed_deg_s: null`; they do not import or raise the
actuator-dependent l4 exception. Live-loop owns its adapter, which raises
`l4.MotionRefused(result)` on a null candidate, retains the raw NPZ and refusal,
and prevents the next command. Existing capture/input code was not edited here.

## Geometry, motion, and return timing

The crop is x=660..1190, y=120..420 at 1280 scale; band pixels are half-scale.
Its centre is x=285 relative to the optical centre, not x=0. A provisional
600-pixel focal maps that rectilinear crop into a cylindrical strip. This
removes much of yaw's perspective distortion, including its vertical component.
It is not a fitted or accepted focal length. Rectification uses only pixels
inside the supplied crop, with resize's half-pixel convention.

Every adjacent post-warmup pair is phase-correlated, without l4's fixed 40 ms
subsampling. As in l4, arrays are copied before the Hanning-window phase call;
flat/static frames, wrong direction, weak response, and off-axis shifts refuse.
The analyzer additionally checks the actual non-wrapped aligned overlap.
Every pair must pass: no invalid pair is silently skipped or filled in.
Capture gaps exceeding twice the median interval refuse.

Each adjacent shift independently yields an angle bracket: convert from the
provisional cylindrical angle back to a symmetric pixel displacement at x=285,
then use both focal extremes 465 and 760 at 1280 scale. A declared 15% model
allowance widens that coarse bracket. Integrate all overlapping adjacent pairs
between returns, including fractional endpoint overlaps. The full-turn test
requires `225 <= lower <= 360 <= upper <= 540` degrees. Thus both the known
half-turn and every-fifth-return aliases fail, even when their periods repeat.
This is a gross-alias diagnostic, not a calibrated angle uncertainty bound.

Returns come from reference-registration zero crossings in the commanded
direction, rather than requiring a sampled raw correlation above 0.85.
Linear interpolation supplies a sub-sample timestamp. Each return retains its
entire bracketing sample interval: its uncertainty is the larger distance from
the interpolated timestamp to either sample. An interval adds both return
uncertainties conservatively and must stay within 5% of its duration. At least
four returns / three intervals and <=5% period spread remain necessary.
The rate bounds include observed period spread and sampling uncertainty, rather
than shrinking uncertainty by an unjustified independent-noise assumption.

## Mouse-count focal candidates

`focal_from_counts(rows, gain_deg_per_count, gain_relative_uncertainty)` requires
exactly six far-landmark edge-to-edge yaw sweeps, three with each count sign.
Each row has this schema (references here are illustrative):

```json
{
  "far_landmark": true,
  "level_camera": true,
  "signed_counts": 2721,
  "endpoint_count_uncertainty": [2, 3],
  "gain_evidence": {"ref": "closure-receipt", "sha256": "64 hexadecimal characters"},
  "native_evidence": {"ref": "video-and-endpoint-annotation", "sha256": "64 hexadecimal characters"}
}
```

All six rows must cite the same gain evidence. Each endpoint bound is in counts
and must include uncertainty locating the visual edge in the input stream;
mouse events are not assumed to coincide with video frames. Their sum must be
positive. Near-landmark controls are explicitly excluded from this six-row fit.

For absolute count span `c`, summed endpoint bound `e`, gain `g`, and fractional
gain error `r`, the FOV is `c*g` and the total angular bound is
`g * (e + (c + e)*r)`. This includes the gain/count-error product. Each bound
must be <=0.5 degrees and the six FOV values must span <=1 degree. FOV and
1280-scale focal bounds are retained, along with all input evidence references.
Invalid inputs raise `ValueError`, matching the old focal-sweep style.

The caller must verify the cited bytes, annotations, applicable settings, and
gain identity: this pure numeric API validates the pin structure and preserves
it, but never opens a reference (`evidence_refs_verified: false`). Candidate
output is `candidate_only_landmark_review_required`, the existing focal-candidate
label; that means inspected native landmark evidence, not a new independent
exploratory code-review requirement.

The requested gain citation is verified in
[calibration-take.md, section 2](../evidence/whole-session-intake-20260923/calibration-take.md):
10,884.8 counts per revolution, **0.0330738 degrees/count**, about +/-2 counts
(**0.02%**, so pass **0.0002** as the relative uncertainty). The
[turn-driver advisory](../evidence/camera-turns-20260927/HANDBACK-review.md) also
cites it. The original measurement states that it covers the slow closure
turn's speeds and settings; the helper does not promote that into a universal
mouse-gain bound or silently supply it as a default.
The inspected calibration-note bytes have SHA256
`c97745de70119181879eb5a3fc3db14ec5534819cd9f1d1bf4eb02662389d9b6`.

The offline module CLI reads only the explicitly supplied JSON array (up to
1 MiB); evidence references are never dereferenced. Both gain parameters are
required. It preserves the SHA256 of the exact input bytes, including BOM or
line endings, and creates a new output file with exclusive creation:

```powershell
uv run --no-project --python C:/Users/volpe/AppData/Local/Temp/live-loop-cuda-env/Scripts/python.exe python -m perception.camera_turn_analysis --counts-json sweeps.json --gain .0330738 --gain-relative-uncertainty .0002 --output focal-candidate.json
```

An existing output or invalid input exits with code 2. Invalid inputs create no
output; existing output bytes are preserved. Output parent directories must
already exist. No changes to the reviewed live script are needed for this CLI.

## Owner verification

Command, CUDA hidden, without modifying the shared project environment:

```powershell
$env:CUDA_VISIBLE_DEVICES=''
uv run --no-project --python C:/Users/volpe/AppData/Local/Temp/live-loop-cuda-env/Scripts/python.exe python -m pytest tests/test_camera_turn_analysis.py -q
```

**47 passed in 19.66 s.** Tests importorskip numpy and cv2 before importing the
module. Synthetic validity uses static world texture on a cylinder and rays
from a yawing rectilinear camera, so one world revolution really is 2*pi. It
does not claim that rolling a flat image supplies known 360-degree geometry.

| Period | Sampling | Candidate, degrees/s | Maximum interval timing bound |
|---|---:|---:|---:|
| 2.23 s | 30 Hz | 161.4385 | 2.55% |
| 2.23 s | 60 Hz | 161.4379 | 1.36% |
| 2.23 s | 120 Hz | 161.4243 | 0.61% |
| 0.87 s | 30 Hz | refused: adjacent-motion confidence | none claimed |
| 0.87 s | 60 Hz | 413.7938 | 3.45% |
| 0.87 s | 120 Hz | 413.7952 | 1.54% |

The table uses seed 42 and focal 600. True rates are 161.43498 and 413.79310.
Additional valid negative-direction controls use a different texture seed.
The suite verifies half-turn symmetry refusal, every-fifth-return detection
refusal (full adjacent motion retained), static/sign/off-axis/ambiguous/flat and
flat-periodic controls, focal-bracket endpoint controls, malformed rows, explicit
timing refusal, full-rate pair counts, and the count-sweep uncertainty gates.
CLI checks include actual `python -m` execution, exact source-byte hashing,
exclusive output creation, missing gain, malformed/oversized JSON, invalid
numeric parameters, and invalid sweep sets. Ruff was not available in the
requested private environment; the owner pytest checks completed there.

## Limits and next action

- No native turn count, live candidate, accepted focal, or accepted calibration
  resulted from these synthetic tests. Native video must count one actual turn
  per proposed return interval and establish the required pose and scenery.
- The provisional rectification can refuse valid motion near focal-bracket
  endpoints (observed at 465 and 760), fast 30 Hz sampling, or whenever even one
  adjacent pair is ambiguous. Broad focal limits do not ensure successful fits.
- Texture symmetry and temporal aliasing cannot be eliminated for arbitrary
  scenes/speeds from sampled images alone. The independent coarse angle bracket
  addresses the demonstrated gross aliases only. Its 15% allowance is not a
  measurement-certified error bound.
- Perspective, nearby geometry/parallax, moving scenery, pitch/roll, lens
  differences, acceleration inside a sample, timestamps with capture latency,
  and imperfect reference registration remain possible model errors. Timing
  bounds describe sampling brackets under the registered-crossing model, not a
  proof of physical latency or feature identity.
- Live-loop owns CLI/input integration and any native measurement. No further
  review lane, recording request, or Linear transition was created here.
