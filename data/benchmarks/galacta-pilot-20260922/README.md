# Galacta near/mid pilot — unexecuted allocation

`schedule.json` is input to the **existing** offline benchmark CLI. It allocates
ten learned and ten existing-scripted 20-second trials, five near/five mid per
policy, in ten matched adjacent pairs. It contains no observations or completed
trial claims. All actual settings/readiness/boards/outcomes remain missing.

```powershell
uv run --offline --no-project python -m scripts.range_benchmark score data/benchmarks/galacta-pilot-20260922/schedule.json
```

`unexecuted-result.json` preserves the actual CLI stdout: exit 0, twenty retained
setup failures, zero attempts, no matched executed baseline, no passing gate.
The preview's numerical fractions are not gameplay measurements.
`verification.json` records source/input pins and bounded schedule/height checks;
`verify.py` reproduces them but refuses to overwrite the saved reports.

Keep this schedule unchanged and fill a separate `filled.json`, preserving all
twenty allocations. The root handoff with exact evidence fields, existing caller
commands and real joins is [galacta-pilot.md](../../../docs/lanes/galacta-pilot.md).
`spec.track=0` is only a required-constructor placeholder: no track was observed.
Run/epoch/target-incarnation placeholders must be bound to actual evidence.
Shared null settings matching in the preview is not verified condition matching.

Root's next inputs are the actual Galacta setup/condition profile, same-epoch
native scoreboard baseline + readiness aligned with the phase clock, and its
guarded scripted collection path. Root then fills and audits trial evidence;
F reviews that changed evidence interface when real filled evidence exists.
No launch, new capture, training, source changes, commit or Linear action occurred.
