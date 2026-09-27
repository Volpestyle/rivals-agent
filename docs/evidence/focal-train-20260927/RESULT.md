# Named TRAIN focal attempt — refused

VUH-1384, camera-analysis, 2026-09-27. **Focal and focal bounds remain unknown.**
This result does not justify skipping the focal sweep. No calibration or
cross-account transfer is accepted. The actual source attempt is
[existing-20260927T190413/result.json](existing-20260927T190413/result.json).

## Actual observations and computation

The three already decoded native 2560x1440 stills from the admitted TRAIN take
were checked against the existing inspection's SHA256 pins and visually inspected:

- Row 7: pitched-down view from an upper platform; nearby rail and stairs.
- Row 1807: airborne Spider-Man in active bot combat, different nearby barriers.
- Row 3606: ground-level close combat beside stairs; a different camera position.

They are about 60 seconds apart. A bounded single-thread CPU LK attempt seeded
up to 100 scene corners at 1280 analysis scale, checked forward/backward error
below 0.5 px and retained only tracks spanning all three stills. **Zero tracks
survived.** The fitter refused its minimum continuous-track requirement before
searching focal values. Empty attempted tracks are retained in
[attempted-tracks.json](existing-20260927T190413/attempted-tracks.json).
This is a failed source attempt, not a numerical focal fit disguised as a result.

The exact raw mouse log was streamed and SHA256-verified. Between rows 7/1807,
there were 104,786 absolute yaw counts and 44,883 absolute pitch counts; peak
step-average yaw was 25,860 counts/s and 1,290 steps had movement/actions.
Between rows 1807/3606, those figures were 115,946 / 49,245 counts,
41,610 counts/s, and 1,413 movement/action steps. Net yaw counts (-8,838 and
+288) cannot turn these moving intervals into stationary yaw measurements.
Both greatly exceed the roughly 200–1,400 counts/s gain evidence.

The named table's input-only scan found one provisional slow yaw window,
rows **833:860** (about 28.68 s, +368 net counts, peak 1,140 counts/s).
No buttons held does not prove stationary pose; native continuous tracks and
pose inspection are absent. No new native video was opened or decoded because
Marvel was running. Existing replay evidence remains unchanged.

## Identity and limitations

The existing `fixed_selection()` loader first ran its denylist and admitted
TRAIN checks. Only session `20260923T051828-422Z-33696-1` was opened:

| Item | SHA256 |
|---|---|
| steps | `d49224e3c4382a62ebb4c4252bcc5800138782688e1d0f60e03e46ce4b6e7edb` |
| original recording identity, reused from admitted source | `ad14e5bc0a1e0da23527a8f4a092e591ddf568ac925cfd0b2907e38dc94b9aaf` |
| raw mouse log, streamed and verified in this attempt | `f6188c34c850eab8e4fd4a1199513b2b01342f6e0fe1516801bddf0273f40990` |
| settings identity from table | `a8dea3bacebbe9377c8ea9bc7f517e7d907e126c61634676883599dbf2e3d1fd` |

The lead checked sensitivity 1.89/1.89 and 800 DPI in the source settings and
independent record. Account identity is not explicit; neither skin nor campaign
wording establishes main versus alt. Alt focal-transfer equivalence is unverified.
Smoothing and acceleration are enabled; logger metadata states capture latency
is uncalibrated. Moving visual endpoints are not assigned timing-free raw counts.

No video hash pass, native decode, dataset write, sealed-source access, GPU,
cloud, desktop interaction, or game input was performed. CPU work was
BelowNormal, OpenCV/BLAS single-threaded, $0. The status receipt is
`~/jobs/focal-train-existing.status.json` (`done`, refused result).

## Reusable code and owner checks

`scripts/fit_focal_train.py` supplies an actual rectilinear landmark model:
`x = 640 + f*tan(theta_track - yaw)`. It searches f=350..1100 at 1280 scale
without assuming 640. Vertical cylindrical-height residuals flag pitch/roll
or translation; horizontal residuals/profile width reject inconsistent or
unidentified geometry. Raw count impulses support delayed exponential smoothing
nuisance fits, with a deliberately conditional union of focal profiles. Those
profiles are not statistical confidence intervals and do not bound unknown
camera latency, acceleration, or non-exponential smoothing.

Even a clean single-window diagnostic returns no promoted focal: far stationary
scenery, adequate gain support, multiple independent tracks/windows and both
signs still need evidence. The optional native-sample path uses the existing
fixed-source decoder and PCGuard, the global two-decode check, at most two FFmpeg
threads and new attempt directories. It was **not executed or validated on
native continuous data** in this delivery; game/OBS absence and a native
inspection are prerequisites. No follow-on extraction is running or queued.

Owner tests: **15 passed in 0.35 s**, private environment, CUDA hidden.
They cover projected tracks at focal 465/640/760 in both signs, parallax,
pitch/roll, underdetermined span, outside-search focal, delayed count response,
missing tracks, input-only stationarity limits, and no-overwrite evidence writes.
These tests validate the implementation, not the source focal.

The first attempt failed before source/pixel reads because a fractional job
start time exceeded the status writer's whole-second update time. Its exact
failure is retained in [existing/startup-failure.json](existing/startup-failure.json).
The successful bounded refusal uses `int(time.time())` and a separate directory.

Next consumer: live-loop. Keep focal unknown and the live sitting unchanged.
Any future native attempt must wait for a quiet PC and obtain suitable
stationary continuous footage; it is not silently launched by this handoff.
