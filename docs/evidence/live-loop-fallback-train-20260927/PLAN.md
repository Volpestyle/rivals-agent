# Fixed fallback TRAIN diagnostic

Lead-requested pre-booking readiness; live-fps owns implementation and result,
live-loop owns integration and booking. Offline, no input/capture, no independent
review required by the lead for this analysis. Existing source loader/denylist
and PC process/RSS guards remain unchanged.

Before predictions, select precisely session `20260923T051828-422Z-33696-1`,
rows `[7:3607]`: 3600 consecutive 30-Hz rows (119.9999988 s) from its admitted,
normal-cooldown TRAIN run `[7:12557]`. No search, cherry-picking, alternate source,
validation/test access, arbitrary source CLI or threshold tuning.
Step SHA256 `d49224e3c4382a62ebb4c4252bcc5800138782688e1d0f60e03e46ce4b6e7edb`;
original media SHA256 `ad14e5bc0a1e0da23527a8f4a092e591ddf568ac925cfd0b2907e38dc94b9aaf`.
Use the named original at `C:/Users/volpe/Videos/2026-09-23 00-18-28.mkv`.
Hash it by streaming before decoding, after the existing sealed denylist and
step loader pass. Inspect native rows 7, 1807 and 3606 before long inference.

Replay exact fallback `2d5183cba12913a36327e0a459ec0c0b2a1238d26a7df98f7823929af3129f18`
with its existing support/settings artifact, compact-bgr, two CPU threads and
explicit CUDA only under `profile_range_bc_live.PCGuard` with no game or OBS.
Run BelowNormal, two FFmpeg threads, <3 GB Python RSS, job-status receipt and
15-minute per-command wall limit. Only one native 2560x1440 BGR observation is
yielded at a time; pipe backpressure bounds decoding. No cached/upscaled inputs.
Select exact decoded ordinals with `cache.select_expression`, verify showinfo
sequence number, PTS and timebase before each observation reaches the predictor.
Native YUV-to-BGR uses the existing cache colour conversion without changing size.

Initialize recurrent state and prior action empty. Every next step gets the
previous decoded, supported semantic held/press/release and **raw requested camera
classes**, with no teacher forcing. Fixed .5 thresholds and original support mask.
This is an uninterrupted ideal 30-Hz history convention; no actual executor,
saturation or neutral-gap claim. Report action-only neutrality separately from
action+raw-camera neutrality. Do not use `harness.decode(..., cal=None)`, which
would zero camera. Pad rotation remains unknown until a measured accepted map.

Human comparisons use `steps.target` with header calibration; yaw uses a slow-turn
gain and pitch is derived from equal sensitivity, not independently measured.
Report all and supported human press steps plus raw count totals, per-action
rates, raw yaw/pitch absolute mean/p95/totals, known denominators and neutrality.
Preserve all per-step targets/predictions, probabilities, FrameRefs and verified PTS.

If >=99% of predictions are neutral in both supported actions and raw camera,
recommend camera+FPS only. Any less-neutral result still needs inspection of
action/camera deficit; this is a train-distribution sanity check, not promotion.
The fallback's existing failed frozen-dev self-fed result (press F1 0.0) remains
explicit and is not superseded by this diagnostic. No booking until the owner
receives the measured verdict.
