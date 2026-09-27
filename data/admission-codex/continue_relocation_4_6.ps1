$ErrorActionPreference='Stop'
$repo='C:/Users/volpe/repos/rivals-agent'
Set-Location -LiteralPath $repo
try {
    & "$repo/data/admission-codex/run_relocation_4_6.ps1" -Short '051206'
    & "$repo/data/admission-codex/run_relocation_4_6.ps1" -Short '053118'
} catch {
    & herdr agent prompt admission-codex "Serial -4/-6 relocation stopped: $($_.Exception.Message). Reconcile data/admission-codex/relocation-051206-20260927 and relocation-053118-20260927 run/status/receipt files and relocation-4-6.supervisor.stderr.log. Do not assume either transfer complete or retry over an existing partial."
    throw
}
