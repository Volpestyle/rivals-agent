$ErrorActionPreference='Stop'
$repo='C:/Users/volpe/repos/rivals-agent'
Set-Location -LiteralPath $repo
$sid='20260927T061900-143Z-150600-12'
$runRoot=Join-Path $repo "data/admission-codex/runs/$sid"
try {
    foreach($step in @('vote','scan','regime','motor','propose','evidence')) {
        $prior=Get-Content -Raw -LiteralPath "$runRoot/$step.run.json" | ConvertFrom-Json
        if($prior.exit_code -ne 0 -or $prior.failure){throw "Prior -12 $step failed; reconcile first"}
    }
    foreach($step in @('assemble','receipt')) {
        & "$repo/data/admission-codex/run_intake.ps1" -Step $step -Session $sid
        $run=Get-Content -Raw -LiteralPath "$runRoot/$step.run.json" | ConvertFrom-Json
        if($run.exit_code -ne 0 -or $run.failure){throw "-12 $step failed; inspect run record"}
    }
    & herdr agent prompt admission-codex 'Match -12 assembly and pending receipt completed. Reconcile runs/20260927T061900-143Z-150600-12/{assemble,receipt}.run.json and match-admission.pending.json. Lead preauthorized acceptance citing b35afbf LAND and final frame-review09029de4 by fullSHA. Write accepted receipt under the same wording after validation, land/push explicit paths, notify lead/IDM for authority refresh before use. Then send lead a one-line summary of all accepted night matches and their minutes; this completes the night set. No other admission decoder queued.'
    if($LASTEXITCODE -ne 0){throw 'Completion notification failed'}
} catch {
    & herdr agent prompt admission-codex "Match -12 assembly failed: $($_.Exception.Message). Reconcile data/admission-codex/continue-match12-assembly.stderr.log and run records; do not infer success or slot state."
    throw
}
