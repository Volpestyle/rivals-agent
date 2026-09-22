# First admitted human-event fit, September 22, 2026

The Mac M5 Max trained the first reviewed human Web-Cluster event checkpoint on
MPS. Windows CPU loaded the exact returned checkpoint and reproduced the Mac CPU
probabilities exactly. This completes a numerical fit/reload diagnostic. It does
not establish useful timing, generalization or learned gameplay.

The dataset contains 108 fixed-grid coordinates from the earlier normal-resource
practice recording: one unique cast onset, one observed continuation with no new
cast, and 106 unknowns. Both known rows are in the same TRAIN-only evening group.
The negative has zero ammo; a rule that starts whenever ammo is positive scores
both rows correctly too. Their preceding feature histories overlap. Per-window
tracker IDs and unknown source motor settings remain explicit.

| Check | Measured result |
|---|---|
| Code on both machines | `8f78ae9f98f2d40c7aff0f53a7c4f7a6185e5b75` |
| Training | PyTorch 2.14.0, actual parameters on `mps:0`, 2.615 seconds |
| Configuration | GRU hidden 8, five causal observations, 100 epochs, batch 2, learning rate 0.01, seed 7 |
| Training labels predicted | 2/2, one start event; ammo baseline also 2/2 |
| Mac MPS versus CPU reload | Same predictions; maximum probability difference 6.985e-10 |
| Mac CPU versus Windows CPU | Exact probabilities and event report equality |
| Independent validation | Not performed |
| Runtime binding or game input | None |

The reported request-to-bracket distance is an offline forecast metric on these
training rows. It is not measured human reaction time, physical button timing or
game-visible execution latency. The job opened numerical artifacts only, not video.

## Artifacts and provenance

Checkpoint, retained on both machines:
`data/diagnostics/range-event-human-fit-20260922/run-1/model.pt`, SHA-256
`7f6f9dafc14e3459e6e7835707b177c3c7fd6357574fc13969a3db25ead1cdc8`.

Accepted input:
`data/human/skill-events/032454-train-diagnostic-v1/examples.json`, SHA-256
`582440d076a952773b0872b2b58451751308f4830f2aeeaa30c2a305482952ab`.
Typed evidence digest:
`5e540cd76b10e56b1742e8f9dbf7065b2a339a09b56be00836e215f933ef709a`.

[Independent review](independent-review.json),
[lead admission decision](admission-decision.json) and
[constructor validation](validation-receipt.json) are exact copies of the genuine
receipts bound by the dataset. The frozen candidate and its images remain unchanged.
These copies record the already completed review; no new audit is implied.

[Mac report](mac-report.json) and [Windows report](windows-report.json) contain the
input/code hashes, source identity, probabilities, masks, baselines and limits.
Mac report SHA-256:
`d5fd7574ca3b815cf718cbb2a376f6028790b67f76c5a752b02ac44d3ea998c4`.
Windows report SHA-256:
`f93485d3c83b1ac3a6b2b12ee4fa9edbafa74d344c7bf4f9546f35016928da57`.

The first Windows check stopped on a raw code-hash difference: `agent/state.py`
has Windows CRLF checkout conversion. The follow-up verified its LF-normalized
bytes against the exact Mac-commit Git blob and Mac hash; both new policy files
were byte-identical. The Windows report retains both raw hashes and this single
explicit conversion. Model/data hashes were never relaxed.

## Reproduction

The archived [fit script](fit.py) and [Windows verifier](verify_windows.py) are
copies of the actual executed jobs. Restore them to
`data/diagnostics/range-event-human-fit-20260922/` beside the named input paths.
The fit creates `run-1` exclusively; preserve the existing run rather than
overwriting it. Use a separate checkout for a rerun. On the Mac, from the recorded
revision, the actual command was:

```text
uv run --locked --group execution python -B data/diagnostics/range-event-human-fit-20260922/fit.py
```

It ran through a niced, durable SSH job with log/PID/exit receipt. Exit status was
zero. Windows used cached isolated CPU Torch, leaving the shared environment and
game GPU alone:

```text
uv run --offline --no-project --with torch python -B data/diagnostics/range-event-human-fit-20260922/verify_windows.py
```

Next evidence: a bounded inspection of the remaining already-authorized source
for target-agreed, ammo-available non-starts and additional genuine starts.
Independent-session validation and measured runtime cast projection remain
separate requirements for accepted live use. No standing-idle footage is needed.
