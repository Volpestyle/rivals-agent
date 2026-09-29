# Camera-map preparation, 2026-09-29

Owner: live-loop; VUH-1319 after VUH-1384. Produced offline, not live-approved.

New loader and signed profile data are standalone. `integration.patch` is
**unapplied**: controller.py and startup.py remain pinned for the calibration
sitting. It also includes loop.py wiring and eight synthetic integration tests.
Apply only after calibration acceptance, then obtain exact-byte live review
and a new deployment freeze. No active live-input path changed in this packet.

`verify_patch.py --root <checkout>` checks the three runtime preimages, copies
only named code/map/kit files into a disposable directory, applies the patch
there and tests it. It never edits the checkout or opens a real pad. Run it with
`uv run python docs/evidence/live-loop-rebind-20260929/verify_patch.py --root .`.
Any later loop safety edit requires a revised patch/preimage packet, leaving
this historical packet untouched.

Owner result: **296 targeted tests passed**, including 31 loader checks, eight
pending integration cases and the existing controller/startup/loop/range-pulse
regressions. An additional deterministic trace matched **1,500 exact pad reports
and camera-state pairs** against the pinned, pre-patch controller. Ruff passed
on the new module/tests and all three pending runtime files. See owner-tests.txt
and receipt.json for hashes. No game, desktop, GPU, paid compute or recordings
were used. All nine v2 calibration runtime hashes remained equal.

Broad verification is not reported as passing: the stdlib suite on 8331c45 with
other lanes' changes is still running and has baseline failures; the perception
group stops during collection because tests/test_spatial_yaw_local.py imports
torch, which is absent from that group. A run excluding only that module is
underway. The subsequent loop-safety delivery will record names, outcomes and
baseline/CRLF diagnosis; these are not failures of an applied camera patch.

The +0.45 alt point stays candidate. Native-count evidence now rules out the
77 deg/s alias and bounds the approximately 154 deg/s rate, but the lead will
accept the full map as a unit after the remaining points exist.

The lead authorized a separate next delta in loop.py: continuous focus, range,
idle, all-key/mouse takeover, deadline and guaranteed release for every live
mode. That gap currently blocks the brief compatibility check. Live-review
will receive that delta and the updated pending camera patch together.

Detailed constants inventory, profile contract and short live-check plan are
in `docs/lanes/live-loop.md`. Linear publication remains with the lead; this
packet does not close VUH-1319 or accept VUH-1384.
