# Intake Timed Practice banner references (203745)

Two crops of the practice range's top-left banner, taken from `2026-09-25 15-37-45.mkv` (session
`20260925T203745-207Z-49728-2`). Each is one native 2560x1440 frame, decoded with
`ffmpeg -ss <file s> -frames:v 1 -vf crop=310:56:110:28` and stored as PNG. The crop is
`intake_session.BANNER_BOX` = (110, 28, 420, 84).

| File | File s | Logger s | Banner | sha256 |
|---|---|---|---|---|
| `banner-range.png` | 2,199.92 | ~2,200.0 | PRACTICE RANGE | `1857860c80c77dfe6bc40a6fe0d4cac3900fb38f53866e1d85009df28e9d9cf3` |
| `banner-timed.png` | 2,259.92 | ~2,260.0 | TIMED PRACTICE | `71a80b2f629d7f777c7344ac1670cfde4738a30c6d9fcae718aaa248a819dace` |

The intake's `timed` step matches every native frame's banner against both references. It uses normalized
correlation on grayscale, and a label needs one score >= 0.9 while the other stays below it. The step then places the
`timed_practice` cut with `agent.human_intake.timed_practice_span` (lead decision 2026-09-25).

On the 720p review frames of 203745, the two banners score about 0.998 against their own reference and 0.46 against
the other. The hashes are pinned in `intake_session.BANNER_REFS`. The references are used by
`tests/test_human_intake_timed.py`.
