$ErrorActionPreference='Stop'
$repo='C:/Users/volpe/repos/rivals-agent'
Set-Location -LiteralPath $repo
$sid='20260927T061900-143Z-150600-12'
$runRoot=Join-Path $repo "data/admission-codex/runs/$sid"
try {
    foreach($step in @('vote','scan','regime','motor','propose','evidence')) {
        & "$repo/data/admission-codex/run_intake.ps1" -Step $step -Session $sid -VoteFrom 60
        $run=Get-Content -Raw -LiteralPath "$runRoot/$step.run.json" | ConvertFrom-Json
        if($run.exit_code -ne 0 -or $run.failure){throw "-12 $step failed; inspect run record"}
    }
    & herdr agent prompt admission-codex 'Match -12 guarded vote/scan/regime/motor/propose/evidence completed. Reconcile runs/20260927T061900-143Z-150600-12/*.run.json; visually inspect segments-evidence.json and review-frames before writing owner verdicts. Fresh proposal/evidence use reviewed ping snapshot. Send exact pins/segment list to frame-review and coordinate decoder slot. No other admission decoder queued. Relocation4/6 is complete; do not duplicate.'
    if($LASTEXITCODE -ne 0){throw 'Completion notification failed'}
} catch {
    & herdr agent prompt admission-codex "Match -12 intake continuation failed: $($_.Exception.Message). Inspect data/admission-codex/continue-match12-intake.stderr.log and run records; reconcile before retry."
    throw
}
