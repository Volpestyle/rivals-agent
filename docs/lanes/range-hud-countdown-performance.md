# VUH-1346 countdown candidate filtering

Frozen software delta for F's independent changed-boundary review. Root owns
integration and any later live use. Only `_countdown_char` in production changes.

The distance expression remains unchanged, including its float64 result and
rounding. NumPy selects the candidates satisfying `d <= MAX_DIST`, then subtracts
one full-bank minimum from those candidates and applies the original strict
`< MIN_MARGIN`. Python converts/deduplicates only selected labels. An empty
eligible set never computes a minimum or subtraction; a shorter label sequence
still truncates candidates like the original zip, without truncating the minimum.
Classify's fast return, topology/hole logic, templates, thresholds, layouts and
cross-frame behavior remain unchanged.

The unedited production baseline is frozen as
`data/diagnostics/range-hud-countdown-performance-20260922/baseline_hud.py`, SHA-256
`5f865e5567f16cf72962cb5148e2e7342272229ec59f54fe5082df90d9b0d3e2`.
The before-edit regression failed with 1,024 minimum reductions in both copies;
the repaired function performs one and returns the same label. This synthetic
work-count test does not imply that the native frames encounter 1,024 candidates.

Exact-output evidence: all 23 authorized frames match the frozen implementation
through individual `read_cooldown`, full `read`, and `state_kwargs -> State`.
These are the three efficiency-run JPEGs `000000/000012/000054`, the previously
authorized 17 mapped source controls, and three named PAD controls. Input hashes,
complete outputs and observation times are retained in `before.json`/`after.json`.
Unknowns match too; equality supplies no new labels or reader-support claims.

The new test file has **30 passing checks**, including actual computed-distance
equality/nextafter boundaries for both predicates, label deduplication, negative
and unknown topology results, classify fast return, empty/prefix banks, nonfinite
short-circuit behavior, strict NumPy error propagation and full reader controls.
The previously accepted readiness selection adds **22 passing checks**, with six
unrelated tests deselected.

One alternating fresh-process old/new pair per current JPEG measured the following
unprofiled `hud.read` calls (decode, imports and State export excluded):

| JPEG | Old ms | New ms | Observed reduction ms |
| --- | ---: | ---: | ---: |
| 000000 | 24.488 | 24.128 | 0.360 |
| 000012 | 25.047 | 21.496 | 3.551 |
| 000054 | 23.574 | 21.658 | 1.916 |

Each of these six children then made one separate cache-cleared profiled read.
`_countdown_char` cumulative times were 6.968/6.920/8.986 ms before and
4.585/5.305/5.782 ms after. Its set-comprehension self times fell from
2.425/2.345/2.651 to .030/.028/.025 ms; candidate filtering now also incurs NumPy
work outside that comprehension, so the latter difference is not total savings.
Both versions made 30 `_countdown_char` calls per frame, and 23/22/22 fallback
comprehension calls. Full-reader ndarray minimum counts stayed 32/25/22: on these
frames the demonstrated benefit is removing Python per-template predicates, not
removing repeated minima. Classification counts remain 30/27/32. Nested profile
times overlap and are not added together.

Runtime: isolated cached Python 3.11.9, NumPy 2.3.5, OpenCV 4.13.0, unchanged
default 32 OpenCV threads; exact build/platform/executable receipts are in each
report. Torch and native capture/pad factories were never imported. The three
pairs establish measured direction only, with no statistical speedup estimate,
live deadline gain or causal native-loop claim. No production thread setting or
input was changed. Earlier accepted evidence remains immutable.

Reproduce the frozen software checks from the repository root:

```powershell
uv run --offline --no-project --with opencv-python-headless --with numpy --with pytest python -m pytest tests/test_hud_countdown_performance.py --corpus -q
uv run --offline --no-project --with opencv-python-headless --with numpy --with pytest python -m pytest tests/test_hud.py -k 'readiness_reconciliation or an_unidentifiable_slot' --corpus -q
```

The new diagnostic `measure.py` permits only the named timing frames and fixed
equivalence references. `summary.json` joins the frozen results; `freeze-sha256.json`
pins the changed reader, tests, this document and diagnostic files. No commit,
deployment, Linear mutation or live gameplay was performed. Next action is F's
review of this function delta, then root's integration decision.
