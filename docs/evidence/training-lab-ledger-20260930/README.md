# Training lab: canonical run timeline

Deployed 2026-09-30 23:01:50 UTC to
<https://jamess-macbook-pro.tailb90f24.ts.net:9443/>.

The timeline now parses the eight-column table in `docs/runs-ledger.md`, including
the full decision text and Yes / No / Pending classification. The duplicate
hardcoded run array is removed. The existing background PC metadata poll carries
the bounded ledger text to the Mac; new PC rows appear on the board's next cached
refresh without a deployment. The live check returned **27 rows from the PC
checkout**, including the still-start result added after the original dispatch.
The page labels its source observation and warns on malformed/missing rows or a
failed PC refresh. Billing remains the separate dated snapshot sourced from
`docs/steering/spend-ledger-20260927.md`; timeline costs are not summed.

Visual references resolve to existing allowlisted image copies when available.
Other Linear assets are links and unmatched paths remain text. No ledger path is
opened as media. Existing path, symlink and size guards and the same-origin image
CSP remain intact. No new images, recordings, models or held-back data were read
or transferred for this update. No paid work or game input occurred.

Verification:

- `python -m pytest tests/test_job_board.py -q`: **34 passed**. Added coverage for
  escaped table delimiters, decisions, malformed/duplicate rows, appended rows,
  PC source precedence, stale/missing data, separate billing and visual references.
- Scoped Ruff and `git diff --check` passed.
- Mac Python 3.9 compiled/imported the changed code. Deployed hashes and `.bak`
  paths are in [deployment.json](deployment.json). One kickstart, PID 18376,
  nice 10 and `taskpolicy -b`; listener remains `127.0.0.1:8766` behind tailnet.
- The immediate first request preceded socket binding and was refused. Subsequent
  read-only checks returned 200 for `/`, `/api/status`, `/idm-review/`, and
  `/idm-review/span/2873352801/172/v2-cd`; there was no second restart.
- Desktop 1440×1080 and phone 390×844 have no horizontal overflow or JavaScript
  errors. All seven visible images decoded in the final check. A desktop image
  needed one reload after HTTP 502; earlier checks also saw intermittent media
  502s. The local media endpoint returned the expected bytes/hash. This transport
  limitation is retained in [browser-check.json](browser-check.json), not treated
  as a clean first-load media pass.

Screenshots: [desktop](desktop.png), [phone](phone.png),
[desktop latest result](desktop-timeline.png), [phone latest result](phone-timeline.png).
Only board/helper/manifest and maintenance documentation changed; footage's viewer
implementation is untouched. Footage received the restart/check handback.

Two source discrepancies were reported to the lead, **w2:p3P**: ledger row 26
still says three RL hits, while the accepted `fe1d795` correction reports one real
hit and false-reward-contaminated updates; row 16 still says recall 0.98 instead
of 0.969. The earlier accepted correction is recorded in
[the prior snapshot](../training-lab-20260930/current-snapshot.md). The board has
no hardcoded overrides; the ledger owner should correct those rows. Acceptance,
project publication and routing those corrections remain with the lead.

[artifact-sha256.json](artifact-sha256.json) pins the deployment and browser evidence.
