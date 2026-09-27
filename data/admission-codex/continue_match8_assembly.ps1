$ErrorActionPreference='Stop'
$repo='C:/Users/volpe/repos/rivals-agent'
Set-Location -LiteralPath $repo
$sid='20260927T055006-068Z-150600-8'
$priorSid='20260927T060021-195Z-150600-10'
$priorRoot=Join-Path $repo "data/admission-codex/runs/$priorSid"
$runRoot=Join-Path $repo "data/admission-codex/runs/$sid"
$deadline=[DateTime]::UtcNow.AddHours(2)
try {
    # The existing -10 supervisor owns the decoder through its serial stages.
    while(Get-Process -Id 134288 -ErrorAction SilentlyContinue) {
        if([DateTime]::UtcNow -gt $deadline){throw 'Timed out waiting for -10 supervisor; do not take its slot'}
        Start-Sleep -Seconds 10
    }
    foreach($step in @('vote','scan','regime','motor','propose','evidence')) {
        $prior=Get-Content -Raw -LiteralPath "$priorRoot/$step.run.json" | ConvertFrom-Json
        if($prior.exit_code -ne 0 -or $prior.failure){throw "Prior -10 $step failed; reconcile decoder state first"}
    }
    foreach($step in @('assemble','receipt')) {
        & "$repo/data/admission-codex/run_intake.ps1" -Step $step -Session $sid
        $run=Get-Content -Raw -LiteralPath "$runRoot/$step.run.json" | ConvertFrom-Json
        if($run.exit_code -ne 0 -or $run.failure){throw "-8 $step failed; inspect run record"}
    }
    & herdr agent prompt admission-codex 'Match -8 assembly and pending receipt completed. Reconcile runs/20260927T055006-068Z-150600-8/{assemble,receipt}.run.json and match-admission.pending.json. Lead preauthorized acceptance citing b35afbf LAND and final frame-review97ff9e59 by fullSHA. Write accepted receipt under the same wording after validation, land/push explicit paths, notify lead/IDM for authority refresh before use. No other admission decoder queued.'
    if($LASTEXITCODE -ne 0){throw 'Completion notification failed'}
} catch {
    & herdr agent prompt admission-codex "Match -8 queued assembly failed: $($_.Exception.Message). Reconcile data/admission-codex/continue-match8-assembly.stderr.log and run records; do not infer success or slot state."
    throw
}
