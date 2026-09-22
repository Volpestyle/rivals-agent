# Human received-request fit

One admitted human Web-Cluster request and four no-new-request controls trained on
Mac MPS and reloaded on Windows CPU. The model reproduced all five training labels;
the ammo-positive rule reproduced two, and never-start reproduced four. This is a
numerical training/save/reload result from one recording, not generalization or
learned gameplay. No human-trained model has controlled the game.

The new `web-cluster-request-v1` semantic revision predicts a fresh received RMB
request in the next 100 ms. Its positive anchor is 14.1 seconds, 97.984 ms before
received down event 2757; all five actual observations precede that event. Native
HUD/control association and a separately observed cast toward the causal Luna
target support the label. That lead time is not physical input or reaction latency.
The earlier visual-onset models and labels retain their historical meanings.

| Check | Observed result |
|---|---|
| Windows and Mac code | `7feee7b603d874ce831b866aacdc19d27565b654` |
| Training | PyTorch 2.14.0, `mps:0`, 1.895 seconds, one fit |
| Configuration | GRU hidden 8, five causal observations, 100 epochs, batch 2, learning rate 0.01, seed 7 |
| Full grid | 108 coordinates: 5 known, 103 masked, 1 unique request |
| Model training confusion | 4/4 no-new, 1/1 start; no extra start |
| Ammo-positive baseline | 1/4 no-new, 1/1 start; 3 extra starts |
| Never-start baseline | 4/4 no-new, 0/1 start |
| MPS to Mac CPU | Same predictions; max probability delta 2.328e-9 |
| Mac CPU to Windows CPU | Same predictions and event metrics; max delta 1.630e-9 |
| Independent validation / deployment binding | None |

The known coordinates are 137, 141, 144, 200 and 206. Bins 137 and 141 have
identical five-step ammo histories (three) and opposite labels. Three negative
controls have positive ammo; n200 is an observed held continuation/release.
No-new-request does not mean standing still, no other ability, or no ongoing cast.
Target-disagreement n198 and all 102 uninspected coordinates remain unknown.

## Data and software acceptance

The [independent source review](independent-review.md) supports the five labels.
[The decision](admission-decision.json) and [its independent receipt](independent-receipt.json)
record the actual authority. [Corrected dependencies](dependencies.json) include
focus event 37 and retained carry-in states: all six observed evidence footprints
start at 0.421919351 and retain their original latest endpoints. Gameplay bounds
10.979..22.229 and all 30 snapshots/780 feature values and known bits are unchanged.
[The materialization receipt](validation-receipt.json) records the real constructors,
cohort, exact mapping, roundtrip and purge checks. [The source profile](source-profile.json)
preserves unknown motor settings and only the reviewed displayed RMB/web association.

[Independent software acceptance](software-review.json) closes RT1: every supplied
raw log is tied to its canonical session/group/split, including negative and masked
rows. Shared-log validation aliases reject before inference, while independent logs
and legitimate same-session distinct media remain valid. The independent reviewer
passed 150 no-fit checks and eight actual visual/request checkpoint-to-main joins
with fake devices. Existing visual checkpoint semantics remain separate.

## Exact artifacts and reproduction

Input: `data/human/skill-events/032454-request-diagnostic-v1/examples.json`

SHA-256: `bd6cf4cb298379ac1a63fd226652e517ad6773ed6b4cead92dfb790abca91570`.
Typed evidence digest: `736496a3ecdff0db286bec51c6c9da9b27076e41f8b64608de51d3cf5b6a9968`.

Checkpoint on both machines:
`data/diagnostics/range-request-human-fit-20260922/run-1/model.pt`

SHA-256: `6ee388070599e3df042ea73876e391340bf228a9e626cc212c60875d8191aeef`.

[Mac report](mac-report.json), [Windows report](windows-report.json),
[executed fit driver](fit.py) and [Windows verifier](verify_windows.py) retain the
exact inputs, code, source identity, configuration and actual probabilities.
[Artifact sources](artifact-sources.json) pins every verbatim evidence copy.
The only code-byte difference was the existing Windows State file's CRLF conversion;
its normalized contents matched the Mac commit exactly.

Restore the drivers under `data/diagnostics/range-request-human-fit-20260922/`
and the named numerical inputs/receipts. The fit creates `run-1` exclusively;
preserve the existing completed run and use a separate checkout to reproduce.

```text
# Mac: one niced durable job, recorded exit status 0
uv run --offline --locked --group execution python -B data/diagnostics/range-request-human-fit-20260922/fit.py
# Windows: exact returned checkpoint, isolated cached CPU Torch
uv run --offline --no-project --with torch python -B data/diagnostics/range-request-human-fit-20260922/verify_windows.py
```

The first transfer archive was rejected before extraction/training because two
Windows manifest paths used backslashes. The corrected archive normalized names;
all destination hashes matched before the single fit was launched. No model run
was repeated or selected by its score.

All rows share the same evening TRAIN group and overlapping evidence dependencies.
Luna is a named source, not the designated Galacta benchmark. Window-reset selection
on n200/n206 is not continuous-live target agreement. One positive cannot establish
useful timing, robustness, expert mechanics or full-match performance. The current
next boundaries are independent-session evaluation and a genuine request-semantic
runtime binding before learned-live reliance; the repeated-kill milestone remains open.
