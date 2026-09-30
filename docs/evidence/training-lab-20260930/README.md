# Training lab: achievements view

Deployed 2026-09-30 at 20:53:18 UTC to
<https://jamess-macbook-pro.tailb90f24.ts.net:9443/>.

The board now leads with measured progress and the unresolved live-readiness
gate. It contains the lead's 23 results plus the later static-augmentation
verdict and first online-RL sitting, spend by app/day, policy trends and
candidate checks, three live sitting cards, IDM comparisons, four world-model
GIFs and explicitly scoped recording cohorts. Job metadata remains available;
early experiments and job history are folded.

Results and billing are dated snapshots. The observed Modal bill is $282.12250741
against $500; [billing.json](billing.json) is the read-only report from profile
`rivals`, workspace `volpestyle`. Kept/discarded spend is explicitly a partial
owner-cost attribution, not a reconciliation of mixed app invoices. There were
no paid launches, fits, decodes or game inputs in this delivery.

Validation:

- `python -m pytest tests/test_job_board.py`: **30 passed**. Includes both live
  thresholds, unknown measurements, HTML escaping, media size/allowlist/path
  guards, same-origin image CSP and first-dispatch viewer GET/POST hooks.
- Scoped Ruff check passed for `job_board.py`, `training_lab.py` and the tests.
- Mac system Python 3.9 imported the deployed board and footage viewer
  successfully. All 15 copied image hashes matched the manifest.
- One coordinated `launchctl kickstart -k` followed footage's READY. The prior
  board is retained at
  `/Users/james/dev/rivals-agent/scripts/job_board.py.20260930T205318Z.bak`.
  [deployment.json](deployment.json) pins the deployed code/data hashes.
- The service stayed bound to `127.0.0.1:8766`, behind the unchanged tailnet
  route. Its PID was 17229, nice level 10; `taskpolicy -b -p 17229` succeeded.
- GET `/`, `/idm-review/` and
  `/idm-review/span/2873352801/172/v2-cd` returned 200 after the restart.
  Footage owns clip playback/strip verification and the viewer implementation;
  this result establishes the routing and board deployment only.
- The deployed HTTPS page was checked in headless Chrome at 1440×1080 and
  390×844. Both document widths equal their viewport, all seven visible media
  elements decoded, and neither page raised a JavaScript error. Closed visual
  disclosures load on demand. [browser-check.json](browser-check.json) records
  the measurements.

Screenshots: [desktop](desktop.png) · [phone](phone.png). These are full-page
captures of the deployed URL, not a simulated job snapshot. The top and sitting
sections were also inspected at native viewport size during verification.

The only viewer edits in this lane are the requested imports and GET/POST
delegation in `job_board.py`; footage owns `idm_board.py` and
`idm_clip_renderer.py`. No third-party frames were uploaded to Linear. Some
unsigned Linear image URLs returned 401, so existing local equivalents were
copied. Grid-i3's unavailable standalone image is represented by its reported
numeric trend instead. See [maintenance notes](../../training-lab.md) for the
explicit snapshot and asset update procedure.
