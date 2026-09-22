# Received mouse input versus two admitted visual-emission anchors

Both anchors occur after a received raw right-mouse down. This establishes recorded ordering on the shared OBS clock; it does not prove physical press timing, binding or causal delivery to the game. Admitted labels remain unchanged.

All times below are composition-relative seconds; deltas are milliseconds. Raw event IDs are original `seq`. Each window is anchor +/-0.6s.

| Bin / target | Five actual history times | Right down / up (seq; time) | Anchor; after down | Accepted visual bracket; delay after down | Confirmation |
|---|---|---|---|---|---|
| n142 / named Luna Snow hero simulation | 13.799999448, 13.899999444, 13.999999440, 14.099999436, 14.199999432 | down#2757 14.197983651; up#2791 14.337988351 | 14.2; +2.016349ms | (14.291666095, 14.299999428]; (+93.682444, +102.015777]ms | 14.308332761 |
| n199 / nearby Galacta | 19.499999220, 19.599999216, 19.699999212, 19.799999208, 19.899999204 | down#3983 19.875987851; up#4018 20.016096151 | 19.9; +24.012149ms | (19.958332535, 19.991665867]; (+82.344684, +115.678016]ms | 20.058332531 |

For each bin, four history frames precede right-down receipt and only the fifth follows it. The final actual frame follows receipt by2.015781ms (n142) and24.011353ms (n199). Right mouse remains held at each anchor and first-started frame. Holds last140.004700ms and140.108300ms, respectively.

n142 has a conflicting/overlapping left-button hold: down#2692 at13.944991151, up#2798 at14.384998151, spanning the anchor and visual onset. Its other received transitions are S/Space/D releases and presses before the anchor, then W, Space, E and A transitions afterward. n199 carries W/A/Space from earlier received downs into the window; their releases are#3845/#3872/#3954 before the anchor, followed by E down/up#4033/#4066 and Shift down#4114 afterward. These names denote raw VKs only, not inferred abilities or bindings. `report.json` preserves every control transition, original fields/device/seq/t_ns, repeated-down handling and held-state provenance.

The accepted n142 native interpretation is withdrawn wrist14.313 -> new forward pose/white emission14.321 -> expanded impact14.329. n199 uses last-not-started19.979 -> first-started20.013 -> impact confirmation20.079. Those file PTS facts are reused from frozen evidence, not re-decoded/re-annotated. The JSON joins each history/bracket/confirmation time to its actual CSV composition_ns, callback event_seq and original-specific+21ms file mapping.

If the observed right presses initiated these two casts, the model anchors are already after their request receipt. Thus the accepted task can forecast upcoming visible execution of an action already requested; these two positives do not establish a pre-request firing decision. Temporal correspondence and the existing native evidence make that association plausible, but button presence alone does not prove it, particularly with n142 overlapping left hold.

Receipt-to-first-visible-emission is102.015777ms and115.678016ms. These are comparable in scale to the lead-reported pad calibrationD100-150ms, not a validation of D or KBM-to-pad equivalence. Recorder SCHEMA states input timestamps are WM_INPUT receipt by the logger thread; frame CTS is OBS composition, not game render or player-view time. Physical device/input delivery and capture/display latency remain unmeasured. The2.016ms n142 ordering is numerical shared-clock ordering, not a sub-frame behavioral claim.

Reproduce from repository root: `uv run --no-sync python -B data/diagnostics/human-cast-request-timing-20260922/diagnose.py`. Stdlib only; reads only the named finalized032454 logs/schema and frozen numerical/evidence JSON. Writes this report and report.json here. Source hashes, exact nanoseconds, schema semantics and all control transitions are in report.json. No image/video decoding, labels, targets, model/horizon, old artifacts, policy/lane edits, training, input or admission changes.
