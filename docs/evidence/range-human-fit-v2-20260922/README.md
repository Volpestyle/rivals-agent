# Six-label human Web-Cluster diagnostic

The M5 Max trained the accepted six-label event dataset on MPS, and Windows CPU
reloaded the exact checkpoint. The model reproduced all six training labels.
An ammo-positive rule reproduced three; never-start reproduced four. This is a
small numerical diagnostic from one recording, not evidence of useful timing or
generalization. No human-trained checkpoint has played the game.

The reviewed coordinate merge retains 108 original grid positions: six known,
102 masked, two unique casts. Three non-starts have positive ammo. Bins 137 and
142 have identical five-observation ammo histories (all three) but opposite
outcomes. All unknowns remain masked; the job opened numerical JSON only.

| Check | Actual result |
|---|---|
| Mac code | `8f78ae9f98f2d40c7aff0f53a7c4f7a6185e5b75` |
| Windows code | `cb10887fb428cf1c8929a961a952ca3c32868001`; policy bytes unchanged |
| Training | PyTorch 2.14.0, parameters on `mps:0`, 1.043 seconds |
| Configuration | GRU hidden 8, five causal observations, 100 epochs, batch 2, learning rate 0.01, seed 7 |
| Model training confusion | 4/4 non-starts and 2/2 starts |
| Ammo-positive baseline | 1/4 non-starts and 2/2 starts; three false starts |
| Never-start baseline | 4/4 non-starts and 0/2 starts |
| MPS to Mac CPU reload | Same predictions; max probability difference 2.794e-9 |
| Mac CPU to Windows CPU | Same predictions and event metrics; max probability difference 2.329e-9 |
| Independent validation / deployment binding | None |

The report's request-to-bracket distance is an offline forecast metric on
training rows. It is not measured input latency or human reaction time.

## Retained artifacts

Checkpoint on both machines:
`data/diagnostics/range-event-human-fit-v2-20260922/run-1/model.pt`

SHA-256: `da29a97f0542210e6c69bc7dfa488afec97c33668a27deea98e3177919834987`.

Input: `data/human/skill-events/032454-train-diagnostic-v2/examples.json`

SHA-256: `b12f7013b24482b505e44468eb723245a03d1e5a56bb46ab9d282cdf3e1001d5`.
Typed evidence digest:
`871f6bcaef37f405a87660eac4eeb9962a360ba608f4e122ef678666cff89191`.

[Independent support review](independent-review.json),
[combined admission decision](admission-decision.json),
[coordinate map](coordinate-map.json) and
[materialization checks](validation-receipt.json) are exact receipt copies.
The combined decision also binds the [prior admission authority](../range-first-human-fit-20260922/README.md).
Six newly inspected coordinates overlay previously uninspected rows; the other
102 original rows, including prior observed unknowns and accepted casts, retain
their original content. Only origin/review fields change in chosen source rows.
Candidate files and the first accepted dataset/checkpoint remain immutable.

[Mac report](mac-report.json) SHA-256:
`5cd1e957975cd2842f53866ac7e97b30796e7ba2434a98b6242c47a9cb479bcc`.
[Windows report](windows-report.json) SHA-256:
`f300ce80c6fbebb225968f84e9ec3f8097fe34e2fb181aa2278996af43eeee5e`.
Reports preserve exact input/model/code hashes and the known Windows State-file
CRLF-only conversion against its Mac-commit Git blob. No artifact hash was relaxed.

## Scope and reproduction

Luna is a named visual supervision source, not the designated Galacta benchmark
target. The nearby Galacta recovery row and historical two-row contrast use
window-reset tracking; continuous replay loses or selects a different target.
Earlier motor settings remain unknown. All rows share the same evening TRAIN
group, with overlapping histories and calibration dependencies. Independent
validation and measured runtime cast projection remain outstanding.

The [fit driver](fit.py) and [Windows verifier](verify_windows.py) are exact
copies of the executed scripts. Restore them beneath
`data/diagnostics/range-event-human-fit-v2-20260922/` with the named numerical
inputs/receipts. The fit creates `run-1` exclusively: preserve the completed
artifact and use a separate checkout for reproduction.

```text
# Mac, niced durable job; recorded exit status 0
uv run --offline --locked --group execution python -B data/diagnostics/range-event-human-fit-v2-20260922/fit.py
# Windows, isolated cached CPU Torch; no live IO imports
uv run --offline --no-project --with torch python -B data/diagnostics/range-event-human-fit-v2-20260922/verify_windows.py
```
