# Galacta near/mid pilot, second predeclaration: unexecuted allocation

`schedule.json` is input to the **existing** offline benchmark CLI. It allocates ten learned and ten existing-scripted
20-second trials, five near / five mid per policy, in ten matched adjacent pairs, in the first pilot's order. The learned
policy is checkpoint `698d8831a6740d1d060ed3691dc2102fc1a39987ad4c7a03ad4c96a49df9ce1b` at confidence 0.7; the shared
condition is `galacta-shared-02`. It contains no observations and no completed-trial claims.

```powershell
uv run --offline --no-project python -m scripts.range_benchmark score data/benchmarks/galacta-pilot-20260923/schedule.json
```

`unexecuted-result.json` is that command's stdout: exit 0, twenty retained setup failures, zero attempts, no matched
executed baseline, no passing gate. Its fractions are arithmetic on an unexecuted allocation, not gameplay.
`verification.json` pins the schedule (`cc0614fd…`), sources and height-boundary checks; `verify.py` reproduces them,
checks the pair order equals the first pilot's and that no episode or run name is shared, and refuses to overwrite its
reports.

`fragment_accounting.py <run_dir>` produces each learned trial's VUH-1314 accounting (`collection.fragment_boundary_accounting`)
and flags the anomalies that stop the pilot. On the first pilot's slot-4 log it reports NOT EXERCISED (that runtime had no
body witness) and flags its pre-repair refusal storm (12 of 194 decisions, a run of 6).

This is a new pilot. `galacta-pilot-20260922` keeps all 20 of its allocations, 16 of them unexecuted and not resumed.
Keep this schedule unchanged and fill a separate `filled.json` with the same twenty entries in the same order. The
binding procedure, operator checklist and time estimate are in
[`data/runtime/galacta-pilot-20260923-preflight/README.md`](../../runtime/galacta-pilot-20260923-preflight/README.md);
the field-by-field fill contract is the first pilot's, in [galacta-pilot.md](../../../docs/lanes/galacta-pilot.md).
