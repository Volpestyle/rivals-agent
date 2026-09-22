# Bounded countdown-filter result, 2026-09-22

See `docs/lanes/range-hud-countdown-performance.md` for the software boundary,
measurements and limitations. Pending independent review; no live use in this lane.

- `baseline_hud.py`: complete unchanged production reader, hash asserted on import.
- `before.json`, `after.json`: exact full cooldown/Hud/State equality for 23 allowlisted
  frames; before was generated before the production edit. All input hashes included.
- `timed-*.json`: six fresh-process reports, one unprofiled cold `read` each plus
  one separate cache-cleared cProfile read. Full runtime/build/thread receipts included.
- `summary.json`: equality checks, old red reproduction, new green controls, joined
  timing and selected work counts. Profile timings are nested, not additive.
- `measure.py`: reproduction harness. `summarize.py`: stdlib-only report join.
- `freeze-sha256.json`: SHA-256 pins, excluding itself and disposable bytecode.

The single timing pass order was old/new for `000000.jpg`, new/old for `000012.jpg`,
and old/new for `000054.jpg`. Each child used this command with the corresponding
name/version and a unique output filename (existing results refuse overwrite):

```powershell
uv run --offline --no-project --with opencv-python-headless --with numpy --with pytest python data/diagnostics/range-hud-countdown-performance-20260922/measure.py timed baseline --name 000000.jpg --out timed-000000.jpg-baseline.json
```

Snapshot invocation replaces `timed` with `snapshot` and omits `--name`. No further
timing is necessary for this bounded result. No input, capture, model, labels,
thread-pool setting or original artifact was changed. Saved-JPEG timings are not
an original-input replay or proof of native speedup. In particular, the native
minimum-reduction counts stayed equal; Python per-template predicate work shrank.
