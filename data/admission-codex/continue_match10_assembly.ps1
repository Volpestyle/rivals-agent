$ErrorActionPreference='Stop'
$repo='C:/Users/volpe/repos/rivals-agent'
Set-Location -LiteralPath $repo
$sid='20260927T060021-195Z-150600-10'
$priorSid='20260927T061107-953Z-150600-11'
$priorRoot=Join-Path $repo "data/admission-codex/runs/$priorSid"
$runRoot=Join-Path $repo "data/admission-codex/runs/$sid"
$deadline=[DateTime]::UtcNow.AddHours(2)
try {
    # The existing -11 supervisor owns the decoder through its serial stages.
    while(Get-Process -Id 110148 -ErrorAction SilentlyContinue) {
        if([DateTime]::UtcNow -gt $deadline){throw 'Timed out waiting for -11 supervisor; do not take its slot'}
        Start-Sleep -Seconds 10
    }
    foreach($step in @('vote','scan','regime','motor','propose','evidence')) {
        $prior=Get-Content -Raw -LiteralPath "$priorRoot/$step.run.json" | ConvertFrom-Json
        if($prior.exit_code -ne 0 -or $prior.failure){throw "Prior -11 $step failed; reconcile decoder state first"}
    }
    foreach($step in @('assemble','receipt')) {
        & "$repo/data/admission-codex/run_intake.ps1" -Step $step -Session $sid
        $run=Get-Content -Raw -LiteralPath "$runRoot/$step.run.json" | ConvertFrom-Json
        if($run.exit_code -ne 0 -or $run.failure){throw "-10 $step failed; inspect run record"}
    }
    & herdr agent prompt admission-codex 'Match -10 assembly and pending receipt completed. Reconcile runs/20260927T060021-195Z-150600-10/{assemble,receipt}.run.json and match-admission.pending.json. Lead preauthorized acceptance citing b35afbf LAND and final frame-review3d7aafa2 by fullSHA. Write accepted receipt under the same wording after validation, land/push explicit paths, notify lead/IDM for authority refresh before use. No other admission decoder queued; -12 is next after explicit slot coordination.'
    if($LASTEXITCODE -ne 0){throw 'Completion notification failed'}
} catch {
    & herdr agent prompt admission-codex "Match -10 queued assembly failed: $($_.Exception.Message). Reconcile data/admission-codex/continue-match10-assembly.stderr.log and run records; do not infer success or slot state."
    throw
}
