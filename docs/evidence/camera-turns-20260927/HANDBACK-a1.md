# a1: signed short pulses and full-rate bands

Owner live-loop; VUH-1384. Review only the changed input boundary under James's
2e00d3f rule. Original reviewed packet and receipt remain unchanged. No desktop,
input or GPU was used for these tests. Sources: `source-hashes-a1.json`.

The same `scripts/measure_camera_turns.py` is the short-pulse wrapper:
`--pulse-axis rx|ry --seconds .02|.033|.04|.067|.08`. Yaw uses the existing signed
deflection set; pitch permits only +/-0.5 and +/-1.0. Still at most four distinct
deflections per block, <=180 s, and a fresh lead token before each pulse. Supply
`--focal-receipt <json>` with `acceptance: accepted`, positive finite
`focal_px_1280` and an evidence reference. The parsed receipt bytes are hashed
in the manifest. The receipt is a lead-owned measured calibration, not the
640-pixel planning hypothesis. This wrapper never accepts focal or a map.

Each pulse reuses `l4.pulse` and `l4.checked_shift`. A small proxy routes fresh
proof through the existing focus/key/HUD/idle/freshness checks and adds the hard
block deadline to the pulse's guarded send. All axes/buttons other than the
specified axis are neutral. The accepted l4 pulse releases in finally and
refuses >10 ms overrun. Every sign has its own native before/after frames and
measured report-return interval; there is no automatic return pulse. Results
are displacement and mean speed during that pulse, explicitly not steady rates.
Native frames are encoded only while neutral in their own files, never through
the background writer's private methods. Any failed shift stops the block.

Yaw collection now retains every new `Live.fresh` timestamp; the fixed 20 ms
sleep is removed. Pad renewals are independently limited to once per 40 ms,
with unchanged <=100 ms leases capped to segment end. Capture/guard processing
can still miss display frames; actual timestamp gaps remain evidence, never
an assumption of camera rate. Independent stop monitor is unchanged.

Exploratory analysis moved to the offline `perception/camera_turn_analysis.py`
owner. Its hash is recorded for reproducibility but is not a live-input receipt
dependency: later offline math fixes do not change the permitted input space or
its hard guards. The wrapper stops with a retained refusal when the analysis
has no candidate, including alias/uncertainty/insufficient-motion cases. The raw
NPZ and native evidence permit later offline analysis. This analysis is not an
independent-review gate under 2e00d3f; the owner tests its projected geometry.
Native video must still count every full turn before a map is accepted.

Owner tests: **26 passed**, Ruff passes. New cases cover both signs on both
axes with synthetic translated native frames through the real l4 shift/pulse
helpers, independent hold durations, pulse bounds, no input beyond the block
deadline, and 240-Hz fake capture retaining >=20 bands over 100 ms while renewing
only 2–3 times. Existing blocked-capture key/focus/deadline closure, failure
release and stop-before-second-segment cases continue to pass.

Lead acknowledgement: write a temporary JSON, flush/close it, then atomically
rename to `continue-N.json` from the remote/agent side. Never use PC keypresses.
Place >=0.8 turn segments last or alone; refusals stop rather than retry.

Preparation example (no input; focal receipt must already exist):

```powershell
uv run --no-project --python C:/Users/volpe/AppData/Local/Temp/live-loop-cuda-env/Scripts/python.exe python scripts/measure_camera_turns.py --pulse-axis ry --deflections .5 -.5 1 -1 --seconds .04 --focal-receipt <accepted-focal.json> --output <new-output>
```

Repeat .04 and .08 blocks three times each for signed pitch. For short yaw use
`--pulse-axis rx --deflections .45 -.45 1 -1 --seconds .033` and .067, three
repeats. No pulse exceeds 80 ms. Live flags remain explicit `--live`, sitting,
native recording, foreground PID and a new matching review receipt.
