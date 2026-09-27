# Paired event bounds on archived command predictions

2026-09-26. Research-only, controlled label coarsening. No production gate,
training set, current experiment or game input was changed.

## Result

Two archived history-only seeds produced predictions on the same 24,556
development steps. Both reproduced their archived teacher-forced macro press-F1,
camera error and every action's press counts and tolerance-F1 within 1e-6 (the
reported aggregate values were identical). The paired frontier evaluator then
bounded seed 0 minus seed 1 under artificially coarsened command labels.

| Coarsening cell, in 33.33 ms steps | Comparisons | Paired resolves | Separate resolves | Paired strictly narrower | Mean paired width | Mean separate width |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 27 | 17 | 17 | 0 | 0 | 0 |
| 2 | 27 | 7 | 6 | 11 | 0.03368 | 0.05934 |
| 4 | 27 | 0 | 0 | 16 | 0.08523 | 0.17242 |
| 8 | 27 | 0 | 0 | 17 | 0.11908 | 0.23318 |

Widths are in F1 units. Each comparison is one action in one session/run, not
an independent statistical sample. Three action/run pairs without true events
were excluded explicitly; ties are not counted as resolved. These are not
global macro-F1 rankings or evidence for choosing a deployment checkpoint.

The additional resolved comparison is **Web-Swing in session 171533**: 25 true
command-onset bins, 40 seed-0 predictions and 49 seed-1 predictions. At two-step
coarsening, separate bounds on the difference are [-0.031601, +0.114761], whereas
paired bounds are [+0.022453, +0.060707]. The fully observed difference is
+0.029938. Thus the shared-truth constraint removes a spurious possible ranking
reversal. The original full-history DP independently reproduced the same exact
endpoints, 54/2405 and 146/2405, in a 0.025 s local check. This is a second
implementation check, not independent peer review.

All 108 bound calculations contained the known logged-label difference, and
paired bounds were contained in separate bounds. Singleton intervals reproduced
the exact difference. The complete analysis, including the separate bounds,
took 5.07 s locally; maximum frontier size was six. This is a single timing
observation, not a controlled performance benchmark.

## Contract and limits

- The event is a **logged semantic command onset**, not a visible cast or hit.
  Each positive bin denotes one binary onset even if the raw logger counted
  more than one edge inside it. This follows the archived metric's target.
- The two streams are thresholded press-head probabilities (0.5), conditioned
  on true previous human commands. They are not decoded pad output and do not
  demonstrate autonomous behavior. Matching keeps the teacher-forced tolerance:
  one step early, zero late, preventing simple after-the-fact echo credit.
- A truth onset at t is hidden inside the fixed cell containing t, of width
  1, 2, 4 or 8 steps. Each cell retains its exact event count; distinct events
  require distinct bins. Cells stop at the run boundary. No missing events are
  allowed, justified here by the fully known logged-command targets only.
  Positive-only HUD evidence would require the missing-event variant instead.
- Labels are hidden **from the evaluator only**. The frozen predictors saw
  the original history. This is a controlled benchmark, not a joint model of
  naturally uncertain history, timestamps or annotations. In particular it
  cannot measure real annotation-cost savings.
- Both runs have valid, known press labels at every exported step; the script
  refuses gaps or unknowns. Predictions, counts and matches never cross runs.
- The two old history-only seeds and two development sessions are narrow
  evidence. The gains are modest, disappear as sign certificates at wider
  coarsening, and do not establish novelty over existing partial-identification
  methods or gains for the current vision policy.

## Provenance and execution

The archived `interim94-s012/report.json` identifies sessions
`20260923T171533-187Z-33696-5` and `20260923T205528-900Z-45572-3` as development
roles (their table headers say train). The report hash, both step-table hashes
and both checkpoint hashes were checked before inference. Source rows total
24,735; eligible normal-regime runs contain 4,630 and 19,926 steps.

Current cohort validation, sealed-denylist checking and patch equivalence were
preserved. Source code differs from the historical closure, so reproduction is
established by the explicit metric checks, not a claim of byte-identical code.
The [seed-0](command-seed0-receipt.json) and [seed-1](command-seed1-receipt.json)
receipts pin the current imported code and match one another on that closure.
No sealed payloads, image caches, native media or frame encoders were opened.
Shape placeholders serve only the history-only model's blank-frame interface;
an attempted image access raises an error.

The [exporter](history_command_export.py) ran locally using CPU PyTorch 2.14.0,
one compute thread, below-normal process priority, and an isolated environment
assembled offline from cached dependencies. The shared repository environment
was not synchronized. Seeds 0 and 1 took 26.69 s and 22.75 s respectively.
Four named files totaling 37,234,807 bytes were copied at a 4,096 Kbit/s cap;
no remote inference or training was launched. This bounded resource use does
not prove literally zero impact on concurrent work.

The [analysis](command_coarsening_pilot.py) needs only Python's standard library.
Its [result](command-coarsening-pilot.json) records all comparisons, exclusions,
export hashes, source hashes and algorithm hashes. Prediction payloads and
export receipts remain under `scratchpad/research-executable-imitation/history-export/`;
that directory is not gitignored and its source arrays should not be committed.

```powershell
uv run --offline --no-project --with torch --with numpy --with filelock==4.0.3 python docs/research/executable-imitation/history_command_export.py --root scratchpad/research-executable-imitation/history-export --seed 0
# Repeat for --seed 1.
uv run --no-sync python docs/research/executable-imitation/command_coarsening_pilot.py --root scratchpad/research-executable-imitation/history-export --output docs/research/executable-imitation/command-coarsening-pilot.json
```

## Consequence

The missing paired prediction export is now supplied for a bounded logged-command
experiment. The method has demonstrated one additional defensible ranking on
real frozen model outputs under controlled coarsening. The stronger empirical
gap remains: naturally interval-labeled visible effects, missing-event
sensitivity, meaningful annotation effort, and comparisons relevant to a vision
policy. More synthetic refinements cannot substitute for that evidence.
