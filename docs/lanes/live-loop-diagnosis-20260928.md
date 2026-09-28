# Camera/FPS refusal diagnosis, 2026-09-28

Owner: live-loop. Scope: saved evidence and source inspection, $0, no live input,
desktop capture, GPU, or native-video decode. This is a diagnosis and proposed
repair, not an accepted camera map or qualified implementation.

## No-pad drift claim withdrawn

The lead corrected the timeline in
`data/calibration/alt-cam-20260928/SITTING.md` and supplied `lead-shots/times.txt`.
I inspected `f0.png` (17:55:49) and `close1.png` (17:58:13): the pillar, pillars
beside it, and floor retain the same viewpoint. These endpoints do not support
the claimed approximately 90-degree persistent no-pad drift. They alone do not
prove there was no intervening movement. The lead identifies the large k5-to-f0
turn as occurring during the pad-attached keep-alive, including walk and RT.

One-file ffprobe of the explicitly named native recording reports 564.579 s.
Its size is 1,532,941,074 bytes; filesystem creation/last-write times are
17:48:01/17:57:26 CDT. This agrees with the corrected timeline, not the initial
estimated 18:03 recording stop. No video frames were decoded: Marvel processes
180724 and 114704 remain present. The withdrawn drift claim does not warrant a
new controller fix.

## Ready-attach: correlation refusal, not excessive measured displacement

The recorded failure has band displacement (0.375, -1.041) px, phase score
0.957, and raw correlation 0.944. `unchanged_pose` requires displacement <=1.5
band px, phase >=0.5, and correlation >=0.95. Only the correlation condition
fails; increasing the displacement tolerance would not fix this case.

I inspected `yaw-01/ready-attach.png` and the last retained before-attach frame
`frames/0000029-before-attach.png`. They show the same general architecture and
viewpoint, but the latter has broad chromatic ghosting/distortion, extending
beyond the hero. This is a visual observation, not proof of its rendering cause
or of exactly zero camera motion. The current `l4.band` already excludes the
hero's usual region: x=660..1190, y=120..420 at width 1280, reduced to 265x150.
Adding the same hero exclusion again is not a sufficient repair.

Proposed repair: distinguish demonstrated movement from insufficient image
quality. Evaluate several textured, spatially separated scenery patches, with
registration and agreement checks, retaining an absolute displacement bound
against the original operator-approved reference. Do not update that reference
incrementally (which could permit accumulated drift), or let correlation after
registration conceal a real translation. A short bounded wait for a provable
frame may handle transient distortion while neutral; an unprovable frame must
never authorize attach/send. Explicit movement still refuses. The existing
scope deadline, fresh range/idle/focus/key proof, and final post-token pose check
remain binding. An operator can also choose a more textured distant scene.

Before selecting thresholds, replay all retained frames and controls for small
translations, sustained drift, blank/repeated texture, blur/distortion, unrelated
views, and hero-only animation. No numeric threshold change is justified by one
failed pair. Pure analysis needs owner tests; integrating a changed pose guard
into the live-input driver requires an independent exact-byte receipt.

## FPS startup: slow returned frame; static-scene timeout not established

`inference-fps-aba/startup.json` records six non-None captures, zero no-frame
events, and no phase or completed prediction. The first proof cost 467.6 ms
(capture 203.3 ms, range reader 238.8 ms) and was discarded before priming.
Two subsequent proofs primed startup. The sixth returned frame took 104.512 ms
to acquire and 107.464 ms including proof, exceeding the unchanged 100 ms limit
after priming. A cold prediction was still pending. Its contribution, if any,
to capture latency is unknown.

Source inspection of the installed DXCAM shows one-shot `grab()` defaults to
`new_frame_only=True`. Its DXGI implementation calls `AcquireNextFrame(0)`;
an unchanged/timeout outcome returns None. There is no configured 100 ms wait
in this path. Copy/readback, driver work, CPU scheduling, or inference contention
remain possible causes of the slow returned frame. The existing timing cannot
separate them. `new_frame_only=False` would reuse cached pixels and must not be
used to manufacture fresh proof.

Proposed FPS-only repair: keep acquisition/proof priming active throughout the
entire unmeasured startup, including the cold forward. Discard over-age frames
and reacquire within a fixed startup/recovery budget; never submit their pixels
as fresh input. Require fresh consecutive proofs and timely warm predictions
on the same worker before starting A1. Retain immediate key/focus/range/idle
refusals and unchanged 100/250 ms limits during measured phases. Record gaps,
recovery counts, call start/end, and prediction overlap. Test a slow returned
frame after priming, repeated stalls, None frames, late inference, recovery,
and every stop condition. This actuator-free runner needs owner tests, not
independent pre-run review.

GDI is an optional explicit backend qualification, not yet a demonstrated fix.
If used for A/B/A, select it before startup, record it, and use it unchanged in
all three phases; its overhead is part of that measurement. Do not switch
backends silently mid-run. A fresh GDI screen copy is different from a cached
DXCAM frame. Validate geometry, freshness, reader behavior, and cadence in the
desktop session before using it. Changing shared `scripts/capture.py` or the
camera driver's capture boundary would require live-input review; an isolated
FPS-only backend choice would not.

## Implemented candidate (lead authorized, review pending)

The subsequent repair is in `docs/evidence/live-loop-repair-20260928/RESULT.md`.
CPU-only saved-PNG and fake-timing replay is authorized while the game runs;
native video decoding and GPU work remain held. No desktop or input was used.
The next arrival is through the lead's `reenter.py`, with no hand-posing.

The retained frame replay does **not** reproduce the exact failing .9438 raw
correlation: the last saved frame has .9897. `frame-retention.json` records 86
dropped frames and 30 written frames. Thus the exact refusal capture is absent
or unidentified; passing retained neighbors is not an exact failed-frame pass.
The candidate retains unknown-quality refusal and bounded neutral recovery.
