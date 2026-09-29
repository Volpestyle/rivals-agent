# Research check-in: a specific camera failure and a compute correction

2026-09-28, 20:20 CDT. Outside evaluator. Saved-image CPU analysis only;
no runtime edits, game input, model inference, provider queries or dispatch.

The camera v2 repair/review/freeze landed, but sitting
`alt-cam-20260928c/yaw-01r` again produced no yaw measurement. Its refusal
metadata now correctly separates the analyzed current frame from the terminal
unanalyzed capture; it records `written_after: no_pad_attached`. The policy
and IDM conclusions have not changed. The 19:24 combat-baseline recommendation
still depends on a usable, current calibration.

## A better-defined next camera investigation

The lead's animated-overlay explanation is a hypothesis. I inspected the exact
reference/current PNGs, the refusal JSON and `perception/camera_ready_pose.py`.
The code estimates fractional patch displacement, but its patch acceptance uses
the **integer-grid template peak**. Fractional registration of the whole band
happens only after enough patches pass that earlier confidence test.

On the actual refused pair, all six integer NCC scores are below .95. Sampling
each current patch at its already-estimated fractional displacement, without
changing images on disk, gives:

| Patch (row, column) | Existing integer peak | Fractionally aligned correlation |
|---|---:|---:|
| 0, 0 | .9369 | .9771 |
| 0, 1 | .9364 | .9720 |
| 0, 2 | .9384 | .9756 |
| 1, 0 | .9395 | .9763 |
| 1, 1 | .9184 | .9639 |
| 1, 2 | .9407 | .9706 |

The median of all six displacement estimates is (-.196, -.637) band pixels.
Using it for a diagnostic registration produces whole-band correlation .9783,
versus .9257 before registration. This calculation deliberately uses rejected
estimates to investigate the failure; it is **not a new accepted guard verdict**.
It does not prove exactly zero physical camera motion or rule out an overlay.

A separate control isolates a real limitation: translate that same reference
image vertically by **two native pixels**, exactly -.5 band pixel, and the
unchanged guard returns `unprovable`, with zero accepted patches. Identity
passes; -.75 band pixel passes; +2 band pixels horizontally or vertically
returns `changed`. A synthetic (-.2, -.64) band translation also passes, so
translation alone does not reproduce every detail of the real pair.

**Recommendation to the existing live owner:** investigate confidence after
fractional alignment before changing arrival routes, masking more scenery or
lowering thresholds. Preserve the displacement bound against the original
reference, uniqueness, spatial coverage and true-motion/content-change
refusals. Add the half-band-pixel case alongside existing negative controls;
interpolation changes score behavior, so the table is not sufficient live
qualification. Any runtime delta still follows the existing pre-input review.
This is one concrete liveness uncertainty, not another broad calibration rewrite.

Reproduction: use the retained BGR PNGs and `band()`. For each audited `(dx,dy)`,
extract the 96x60 current patch with `cv2.getRectSubPix` centered at
`(x+47.5+dx, y+29.5+dy)` and correlate with the original reference patch. The
whole-band calculation uses the existing linear `warpAffine` with negative
median displacement and the existing two-pixel inset. Control images were
translated in memory at native resolution with `INTER_LINEAR`, then passed
through unchanged `analyze()`. No candidate code was installed.

Pins, SHA256:

- `camera_ready_pose.py`: `f4ee95f38f652040b24a61ae44b484a5be98321a8417cb92a9d76b848600c8c2`
- `yaw-01r/refusal-reference.png`: `3e992481bcb3f3d941ac92f8c0c0ceb48faac2ec0fe331c442049385f88fcaf8`
- `yaw-01r/refusal-current.png`: `1987561f1593789194d8786d24bbcab5f4028173783d003de78e478263e9cf69`

## Use the observed IDM workload for compute planning

`docs/compute.md` commit `6abc746` calls the Mac refit smaller and projects
11-12 hours on Mac using an unrelated policy-fit Mac/L40S ratio. The retained
IDM reports show the opposite workload ordering:

| Run | TRAIN minutes | Contexts | Epochs / updates | Measured fit | End to end |
|---|---:|---:|---:|---:|---:|
| [full03, L40S](../evidence/idm-expanded-full03-result-20260928/report.md) | 181.89 | 653,842 | 3 / 122,598 | 5.95 h | 7 h 34 m |
| [Mac refit](../evidence/idm-match-refit-mac-result-20260928/report.md) | 200.976 | 722,074 | 3 / 135,390 | 129.849 min trainer; 135.754 min fit process | 2 h 53 m |

The Mac did a fresh three-epoch fit, with more examples and updates, not a
smaller fine-tune. These are different pipelines/data/backend runs, **not a
controlled hardware speed comparison**. Nevertheless, this direct IDM evidence
is more relevant than multiplying its cloud time by the policy experiment's
1.9 ratio. Correct the 'smaller' description and withdraw that 11-12 h estimate;
use the observed Mac IDM run as the next comparable job's planning anchor.
The 9-12 h PC estimate and the policy fit's 21 GB figure do not establish IDM
runtime or CUDA memory needs either; those remain unmeasured.

This strengthens the case for local IDM work when another experiment is
scientifically warranted. It does not justify a new refit, promote the mixed
Mac checkpoint over full03, or establish that every future fit belongs on Mac.
Route both corrections through herdr-lead; no new lane or schedule is needed.
