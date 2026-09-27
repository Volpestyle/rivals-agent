# Calibration focal — bounded refusal — 2026-09-27

Current result: [actual native attempt and refusal](../evidence/focal-calibration-20260927/RESULT.md).
After the 15:24 CDT release, four alt poses were inspected and 96 adjacent frames
produced 52 tracks. All 20 timing models refused: best horizontal/vertical RMS
3.64/3.84 px exceeds both 1.5 px gates. Focal and defensible bounds remain unknown.
Seven owner tests pass. All owned decode/fit/test processes stopped; no further
decode planned. Lead received the verdict and chose yaw + FPS only. No calibration
acceptance, independent review, or cross-account transfer is claimed.

The following preserves the earlier static preparation state.

Owner: camera-analysis; integration and release owner: live-loop (VUH-1384).

Lead authorized exactly three existing CALIBRATION takes, never split data.
Only their metadata, provenance and old analysis code were read. James is
playing/recording: no video access/hash/decode, tests, image processing, GPU or
queued probe. No staging/commit without a coordinated slot. Old evidence remains
immutable. Focal and defensible bounds are still unknown.

[Static readiness and proposed windows](../evidence/focal-calibration-20260927/STATIC-READINESS.md)
records the fixed windows and source identities. Start with alt-left 162648;
keep main-right 060921 separate. Rightward 030045 account is unassigned from the
records read, despite known 1.89/1.89 and 800 DPI settings provenance.

Important dependency: existing near-360 gain corrections used assumed focal465.
Their speed/sign agreement is evidence, not an independent focal measurement.
Capture latency remains uncalibrated; smoothing/acceleration are on. Existing
pitch-control failure and slow rightward mouse1/pitch disturbance are retained
as limitations and source controls.

Prepared only: fixed-source metadata/window helpers and five unrun synthetic
checks in the assigned new script/test paths. No decoder or fit invocation is
exposed in the static-phase script. Next work awaits the lead's explicit
game-closed release: tests, tiny inspected native sample, then bounded adjacent
tracks if warranted. Nothing is automatically scheduled.
