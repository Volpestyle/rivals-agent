# Six-app shakedown attempt 01 ? INCOMPLETE

EXPLORATORY launcher evidence, 2026-09-27. No scientific yaw result was produced.

All six host children exited with code 1 before AppCreate. Five refused the
provider billing report rate limit before reserving. Slot 02 reserved $0.480734,
then `scripts.job_status.write` raised `ValueError: updated precedes started`:
`started=time.time()` had fractional seconds while the default `updated` was
rounded down to whole seconds. The status call preceded the runner's cleanup
`try` block. No watchdog or AppCreate was started. The first local wrapper also
had a generated-newline SyntaxError before imports; its original source/log are
retained alongside the syntax-checked correction. That wrapper failure made no
guard call or reservation.

The packet used accepted modal_guard v1.0.2, release
`732dc08f9d0351b3a601a0a613dbc31f5c2476b6eaddc8cb49e1575d004b78ce`, unchanged,
and immutable base image `im-FNjy4v5u4XYF29SBGvT0KD` plus a native SDK source mount.
All 83 inventory files (82 cloud files and host job_status) and all six specs were
rehashed before launch. Inventory SHA-256:
`0408a07c1d030f147c50c63be0ee26aa8de586ccce685450177c685a6fd83734`.
The six-slot bootstrap reserved at most $2.884404 against the approved $3 probe
allocation inside the $24 experiment. No image build occurred.

The canonical billing refresh before launch reported $48.03386987 metered floor,
$0 outstanding, and $51.96613013 headroom against the $100 workspace cap. This is
workspace accounting, distinct from the historical explore lane REPORT.

## Recovery and next step

The only reservation was settled as `NEVER_CREATED` at **$0**, with no outstanding
probe holds. The proof contains 26 authenticated snapshots spanning 61.880355791
seconds. This was reconciled through the unchanged accepted
`lifecycle.teardown` and `Ledger.settle` path. Settlement requires FENCED state,
zero RPCs, authenticated repeated absence at least 60 seconds apart and the
original funded envelope. See `outcome.json` and the pinned proof for the final
state; no manual credit, fresh cleanup allowance or ledger rewrite was used.
The post-settlement totals display refused stale billing after saving the proof
and settlement; a separate read-only journal check confirmed `NEVER_CREATED`.
The consumed bootstrap slot still counts its original $0.480734 toward that
campaign's finite cumulative reservation limit; it cannot be recycled.

No app creation window remains reserved. No automatic retry or fits follow this
failed shakedown. modal-port owns the shared guard fixes and their required spend
review. The original six-slot campaign is not silently redefined or recycled.
Mac dual-grid extraction remains queued behind IDM's explicit slot release.

Artifacts copied here are byte-for-byte receipts from
`/Users/james/dev/range-bc-data/explore/nitrogen-spatial-yaw-20260927/probe-launch-01/`;
`SHA256SUMS.json` pins them. No datasets or sealed inputs were opened by this
attempt. Six-way GPU overlap, tensor work, checkpoint round-trip and full-fit
performance remain unmeasured.
