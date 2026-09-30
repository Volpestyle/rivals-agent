# Training lab

The private board is at <https://jamess-macbook-pro.tailb90f24.ts.net:9443/>.
`scripts/job_board.py` owns job metadata and routing; `scripts/training_lab.py`
renders the timeline from `docs/runs-ledger.md` and other achievement snapshots
from `scripts/training_lab.json`. Historical experiments remain in a fold.

Add or correct timeline rows only in `docs/runs-ledger.md`, preserving its eight
columns. `Keep?` starts with Yes, No or Pending. The existing background PC
metadata poll carries the bounded ledger text to the Mac every 60 seconds;
the board's 30-second snapshot cache picks it up on page refresh. No restart or
JSON edit is needed for new rows. The page identifies the source observation;
before the first PC fetch it uses the Mac checkout copy, and failed refreshes
are labelled as cached. Missing/malformed rows produce a visible warning, never
a fallback to the old hardcoded timeline. This does not recompute scores or billing.

The achievement JSON is a curated projection of existing evidence, not a second
result ledger. Its source pointers lead to the owners' lane verdicts, sitting
records and recording ledger. Missing measurements remain
unknown. Three-seed averages and single candidates are separate rows; live
readiness requires both hold >= 0.30 and turn >= 0.20. This is a screening check,
not autonomous-play acceptance.

For non-timeline snapshot updates, read only named result documents or small
reports, then edit the projection and its `as_of`. Do not enumerate recordings, labels, feature caches
or held-back data. To refresh spend, use the read-only command
`modal billing report --for "this month" --profile rivals --json` in workspace
`volpestyle`, aggregate each row once by UTC date and app description, and record
the observation time. No Modal function is involved. The outcome-attributed
subset uses owner run costs, including estimates; it is intentionally separate
from the complete billing total. Shared app totals must never be summed as
individual run costs.

Images are explicit copies in ignored `data/job-board-media/`. The JSON manifest
records each original source, byte count, SHA-256 and optional reference URLs.
Timeline references matching this manifest show the existing image copy;
other Linear asset URLs are links, and unmatched paths remain text. The ledger
never grants access to arbitrary files. Only manifest-named PNG,
JPEG and GIF basenames can be served; traversal, symlinks, forbidden paths and
files above 16 MiB are refused. Asset URLs are same-origin. Unsigned Linear
downloads returned HTTP 401 during this delivery, so native local equivalents
were used. The grid-i3 visual was unavailable locally; its measured trend is
rendered directly from the reported numbers. No third-party footage is included
in achievement visuals.

The separate private viewer belongs to footage: `idm_board.py` handles
`/idm-review/*` before board scanning and owns its CSP, ranges and queue POSTs.
Other POSTs receive 404. Do not modify those implementations from the board lane.

Deployment uses exact files and verifies all media hashes, keeps a timestamped
`.bak`, and kickstarts `com.volpestyle.rivals-job-board`. The service remains
bound to loopback behind the existing tailnet route. Coordinate one restart
with footage, verify both `/` and `/idm-review/`, then check desktop and phone.
Run `python -m pytest tests/test_job_board.py` before deployment. A results update
needs no fit, decode, cloud job, game input or new data access.
