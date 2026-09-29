# Independent delta re-review v2: phase-one paired camera access audit, VUH-1353, 2026-09-29

Reviewer: live-review (Claude Opus 5.5, `w2:p3E`, the v1 reviewer, outside the IDM lane). Read-only. I did **not** run
`audit.py` `main()` and opened no video, ledger, corpus or denylist file. I ran only the packet's synthetic unit tests
and a synthetic path check, both of which call `refuse_sealed` with fake rows, with bytecode writing disabled.

Scope: D1, D2, N1 and N2 from [review v1](../idm-paired-camera-access-20260929/review-v1.md) (receipt
`7407c6f7…25e8`).
- All 8 entries in the v2 `SHA256SUMS.json` match. They include `audit.py` `d57ea321…`, `test_refusals.py` `5bc5ff54…`
  and `agent/human_intake.py` `6000f4a6…` (the landed authenticated loader).
- The v1 packet is unchanged.
- The only differences from the v1 `audit.py`, after line-ending normalization, are the four fixes below plus the
  `human_intake` import.

## Verdict: **LAND**

- **D1 fixed.** `main()` now calls `I.load_denylist(deny, sha256_pin=DENY)`. That is one LF-normalized read, whose
  bytes are both authenticated and parsed, with schema and row validation. The raw `sha(deny)` check and the second
  `read_text()` are gone. The test shows that a CRLF denylist authenticates against the LF pin with a single
  `read_bytes`, that a wrong pin refuses, and that an incomplete row refuses.
- **D2 fixed.** `normalized_path` (`replace('\\', '/').casefold()`) is applied to **both** sides.
  - The owner's test refuses on session ID, session group, media hash, and a forward-slash or backslash path, each
    alone, and passes a non-matching control.
  - Independently, I built fake denylist rows from the audit's real `SOURCES`, where the path is a `WindowsPath`
    rendered with backslashes. The ID and hash never matched, so only the path clause could fire. All six variants
    refused: forward slashes, backslashes and upper case, for both sources.
- **N1 fixed.** `utf-8` is explicit for `metadata.json`, `inputs.jsonl`, `frames.csv` and the output.
- **N2 fixed.** The output records `ledger_pin_policy: trust-on-first-use at reviewed audit access; enforce in later
  packet`.

Everything else reuses v1: which paths are opened, the ordering (sealed check before any source access), no admission,
labels, fit or decode, the exclusive-create write only on D:, and failures raising. The v1 no-execution condition is
lifted by this LAND. A later mapping or inference phase needs its own frozen review.

## Tests

`python -m unittest discover -s <v2 packet> -p test_refusals.py` in the live venv: **3 tests OK**, plus my six-variant
synthetic path check. Neither calls `main()`.
