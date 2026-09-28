$ErrorActionPreference='Stop'
$repo='C:/Users/volpe/repos/rivals-agent'
Set-Location -LiteralPath $repo
$sid='20260927T061107-953Z-150600-11'
$priorSid='20260927T061900-143Z-150600-12'
$priorRoot=Join-Path $repo "data/admission-codex/runs/$priorSid"
$runRoot=Join-Path $repo "data/admission-codex/runs/$sid"
$deadline=[DateTime]::UtcNow.AddHours(2)
try {
    # The existing -12 supervisor owns the decoder through its serial stages.
    while(Get-Process -Id 154560 -ErrorAction SilentlyContinue) {
        if([DateTime]::UtcNow -gt $deadline){throw 'Timed out waiting for -12 supervisor; do not take its slot'}
        Start-Sleep -Seconds 10
    }
    foreach($step in @('vote','scan','regime','motor','propose','evidence')) {
        $prior=Get-Content -Raw -LiteralPath "$priorRoot/$step.run.json" | ConvertFrom-Json
        if($prior.exit_code -ne 0 -or $prior.failure){throw "Prior -12 $step failed; reconcile decoder state first"}
    }
    foreach($step in @('assemble','receipt')) {
        & "$repo/data/admission-codex/run_intake.ps1" -Step $step -Session $sid
        $run=Get-Content -Raw -LiteralPath "$runRoot/$step.run.json" | ConvertFrom-Json
        if($run.exit_code -ne 0 -or $run.failure){throw "-11 $step failed; inspect run record"}
    }
    & herdr agent prompt admission-codex 'Match -11 assembly and pending receipt completed. Reconcile runs/20260927T061107-953Z-150600-11/{assemble,receipt}.run.json and match-admission.pending.json. Lead preauthorized acceptance citing b35afbf LAND and final frame-reviewba8b031b by fullSHA. Write accepted receipt under the same wording after validation, land/push explicit paths, notify lead/IDM for authority refresh before use. No other admission decoder queued; -12 owner review and independent review remain.'
    if($LASTEXITCODE -ne 0){throw 'Completion notification failed'}
} catch {
    & herdr agent prompt admission-codex "Match -11 queued assembly failed: $($_.Exception.Message). Reconcile data/admission-codex/continue-match11-assembly.stderr.log and run records; do not infer success or slot state."
    throw
}
