# VUH-1294: native countdown/readiness reconciliation

2026-09-22. Independently reviewed and accepted by the lead for integration.
Reader repair only; no learned-policy or benchmark result.

Owned changes: `perception/hud.py`, `tests/test_hud.py`, this note, and
`data/diagnostics/range-hud-20260922/`. Separately, only stale current-result
sentences in `range-benchmark.md` were corrected to accepted main `f841527`.
Episode implementation is untouched. Outline/perception diagnosis belongs to
the other lane.

## Failure and repaired boundary

`read_ability` classified white countdown ink as a ready icon. `read()` retained
the countdown separately, but `Hud.state_kwargs()` correctly exports only the
existing State schema, so the wrong ready flag survived. At native source
19.821/20.021 s the mapped E uppercut read `(True, 0)` with countdown 3; at
21.921 s the mapped F pull read `(True, None)` with countdown 6.

Both standalone `read_ability()` and aggregate `read()` now use the same
reconciliation, before State conversion. Aggregate reads each countdown once.
No caller or State/model feature change is required. The caller must continue
to supply its source layout; MK/PAD defaults and slot mapping were not changed.

Rules, in priority order:

- An occluded slot remains unknown; a badge cannot override that guard.
- A visible zero charge badge means unavailable.
- A positive countdown on an uncharged ability means unavailable.
- Swing/uppercut may recharge with spare charges. A known positive badge retains
  the icon verdict, including red unavailable and blank/uncertain unknown.
  With unreadable charges, countdown ink cannot establish ready: a would-be
  True becomes unknown. Independent False/None stays False/None.
- Zero countdown on an uncharged slot cannot prove ready at the transition.
- An absent/unreadable countdown does not invent cooldown state; the remaining
  existing icon/badge evidence applies. `None` never becomes zero charges.

## Bounded native evidence

Inputs are exactly the 17 causal frames referenced by
`data/diagnostics/range-perception-20260922/diagnosis.json`, at native 2560x1440:
13.121–13.521 s (five), 19.421–20.021 s (seven), 21.521–21.921 s (five).
Each source SHA-256 was verified before reading. Calibration uses the first five
authorized frames through existing `slot_mapping`, yielding swing=swing,
get_over_here position=uppercut, uppercut position=get_over_here. No global
binding assumption was added. Exact native HUD crops are retained in this lane's
diagnostic directory. Visual inspection covered the failing 19.821/20.021/21.921
anchors, the clean 13.121/13.521 controls, red unavailable 13.221 control and
late 21.521/21.821 countdown/occlusion controls.

`before.json` and `after.json` execute real `read -> state_kwargs -> State`.
Across 51 mapped ability reads, 19 readiness flags change True to False:
11 uppercut, three swing and five pull. This is a count of reader corrections,
not independent trials or a general accuracy estimate. All charges/countdowns
are unchanged. The three existing occlusion unknowns remain unknown (swing at
21.821/21.921, uppercut at 21.921). E at 19.821/20.021 becomes False with zero
charges; F at 21.921 becomes False with countdown 6 retained in Hud.

Three expressly authorized native PAD regression images were read and visually
inspected by exact filename in `C:/rivals-agent/l2tag`, with no directory scan:

- `t0-a-untagged-000.jpg`
- `t0-b-after-web-cluster-003.jpg`
- `t0-b-after-web-cluster-028.jpg`

Their full Hud and exported State ability values are identical before/after:
swing ready with three charges, uppercut ready with two, pull/teamup ready,
no readable countdowns. `pad-before.json` and `pad-after.json` record immutable
source hashes and all results. The originals were not changed. These controls
do not establish PAD countdown accuracy or broaden tracer-tag accuracy.

## Verification and limits

Before production changes the new selection reproduced **6 failures, 14 passes**,
including the native mapped countdown failure. After repair plus a real blank
frame unknown control, **22 passed, 6 deselected** (1.32 s), using:

```powershell
uv run --offline --no-project --with opencv-python-headless --with numpy --with pytest python -m pytest tests/test_hud.py -k 'readiness_reconciliation or an_unidentifiable_slot' --corpus -q
uv run --offline --no-project --with opencv-python-headless --with numpy --with pytest python data/diagnostics/range-hud-20260922/diagnose.py after
```

The selected native tests are corpus-marked. The six deselected legacy tests
include broad corpus and external footage access; they were not run. No sealed
source, candidate/label edit, shared install, input, capture, training or commit.
The cached isolated tool environment was used; source and artifact SHA-256s are
in the reports and `freeze-sha256.json`.

The observed sample has no positive countdown paired with positive remaining
charges. That combination is covered by controlled subreader contracts through
the real aggregate/State boundary, **not native gameplay proof**. Unrecognized
countdowns and incorrect badge reads remain upstream reader limitations. Gold
in-use icon semantics, broader layouts/resolutions and PAD cooldown cases were
not newly established. No new full-health, KO, outcome or performance claim.

Independent review reproduced all 22 selected tests, the 19 native source
corrections and unchanged original PAD controls. It additionally inspected six
fresh native PAD frames from `scripted-diagnostic-20260922-1130`: pull countdowns
7/5/3/1 now produce False; uppercut countdowns 4/2 with unreadable badges now
produce unknown. Recovered white uppercut and existing red veto remain intact.
The in-use gold icon's existing ready verdict is explicitly not validated by
this repair. Root inspected the diff and frozen code/test hashes and accepted
this narrow boundary. Real episode/pilot evidence remains open.
