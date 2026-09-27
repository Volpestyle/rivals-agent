# Dual-grid cache attempt 01 — refused before payload reads

Source `677e4de866285d23ad305c2984d0ebf594180577`. Mac launch at
2026-09-27 23:23:43 UTC after IDM explicitly released the heavy slot.
Launcher PID 36871, worker PID 36884, nice 10 / two threads / intended MPS.
Worker exited 1 at 23:23:47 UTC; `subprocess.wait` proved terminal.
No feature extraction or paid compute occurred; the output cache root was not created.

The current archived `data/human/sealed-denylist.v2.json` includes the lead's new
sealed session. Its LF-normalized SHA-256 is
`09e8b9d350c89eb41c1581e1bce47548bfb855bca5805cf2e65955b9b23597b5`.
`policy/range_bc/steps.py` still pins
`439c80df6cd5d6daa60b48e0acb2d3a3fa833134ff14edddc4121348c2dceb20`.
The existing loader refused that mismatch before opening any step-table header/body
or pixel store. No sealed video, logger folder or frames were opened, hashed or copied.

The old denylist was not restored and the check was not bypassed. The lead was asked
to route the shared metadata-pin correction through the required independent review
of the sealed-data boundary. A fresh pinned launch/log is required after that fix;
these records and the original Mac records remain unchanged.

`collection.json` proves all six copied launch/log/terminal/manifest files match their
Mac SHA-256 values. The archive was 1,515,520 bytes with 82 pinned files:
SHA `9c07b2b2e9d86be3a5ec68b1ecfda176d9be53ccc1832d4025243751dd1acecf`.
The source-manifest SHA is
`36c330b386b39f1424e7d8f9759a5e412f581318037f8473427535932a07d596`.

The scientific implementation and 52 passing synthetic CPU tests are separately
landed at `677e4de`; this failure occurred at unchanged cohort admission, before that
implementation consumed any real arrays. No scientific yaw result exists yet.
