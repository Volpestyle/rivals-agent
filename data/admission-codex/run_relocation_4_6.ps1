param([Parameter(Mandatory=$true)][ValidateSet('051206','053118')][string]$Short)
$ErrorActionPreference='Stop'
$repo='C:/Users/volpe/repos/rivals-agent'
Set-Location -LiteralPath $repo
[Diagnostics.Process]::GetCurrentProcess().PriorityClass='BelowNormal'
$python='C:/Users/volpe/.uv-envs/admission-codex/Scripts/python.exe'
$session=@{'051206'='20260927T051206-888Z-150600-4';'053118'='20260927T053118-260Z-150600-6'}[$Short]
$jobName="relocation-$Short-20260927"
$runRoot=Join-Path $repo "data/admission-codex/$jobName"
New-Item -ItemType Directory -Path $runRoot -Force | Out-Null
$out=Join-Path $runRoot 'relocate.stdout.log'
$err=Join-Path $runRoot 'relocate.stderr.log'
$receipt=Join-Path $runRoot "relocation-$Short-mac.json"
$runRecord=Join-Path $runRoot 'run.json'
if ((Test-Path -LiteralPath $out) -or (Test-Path -LiteralPath $receipt) -or (Test-Path -LiteralPath $runRecord)) { throw 'Existing attempt; reconcile instead of overwriting' }
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
$PID | Set-Content -LiteralPath (Join-Path $runRoot 'supervisor.pid')
$statusCode="import sys; from scripts.job_status import write; write('$jobName',owner='admission-codex',stage=sys.argv[1],host='pc',evidence=sys.argv[2],progress=sys.argv[3])"
function Write-Status([string]$stage,[string]$progress) {
    & $python -c $statusCode $stage $receipt $progress
    if ($LASTEXITCODE -ne 0) { throw 'Status write failed' }
}
function Check-Resources {
    if (Get-Process -Name 'Marvel*','obs64' -ErrorAction SilentlyContinue) { throw 'Marvel or OBS active; relocation stopped' }
    $available=[long](Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory*1024
    if ($available -lt 4GB) { throw 'Free physical memory below 4 GiB; relocation stopped' }
    return $available
}
$started=[DateTime]::UtcNow.ToString('o')
$failure=$null; $job=$null; $p=$null; $peak=@{}; $freeBefore=$null
try {
    Write-Status 'running' 'Checking resources before source hashes'
    $freeBefore=Check-Resources
    Add-Type -Path (Join-Path $PSScriptRoot 'OwnedProcessJob.cs')
    $arguments=@('-u','data/admission-codex/relocate_matches_4_6.py',$session,$receipt)
    $job=[AdmissionOwnedJob]::Start($python,[string[]]$arguments,$repo,$out,$err)
    $p=$job.Process
    $heartbeat=[DateTime]::UtcNow
    while (-not $p.HasExited) {
        $freeNow=Check-Resources
        $all=@(Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,WorkingSetSize)
        $owned=[Collections.Generic.HashSet[int]]::new(); [void]$owned.Add($p.Id)
        do {
            $changed=$false
            foreach ($r in $all) { if ($owned.Contains([int]$r.ParentProcessId) -and -not $owned.Contains([int]$r.ProcessId)) { [void]$owned.Add([int]$r.ProcessId); $changed=$true } }
        } while ($changed)
        foreach ($r in $all) {
            if (-not $owned.Contains([int]$r.ProcessId)) { continue }
            $key=[string]$r.ProcessId
            $peak[$key]=[Math]::Max([long]$peak[$key],[long]$r.WorkingSetSize)
            if ([long]$r.WorkingSetSize -ge 2800000000) { throw "Owned process $key exceeded 2.8 GB working set" }
        }
        if (([DateTime]::UtcNow-$heartbeat).TotalSeconds -ge 60) {
            $progress=(Get-Content -LiteralPath $out -Tail 1) -join ''
            Write-Status 'running' "$progress; free_bytes=$freeNow"
            $heartbeat=[DateTime]::UtcNow
        }
        Start-Sleep -Seconds 1
        $p.Refresh()
    }
    $p.WaitForExit()
    if ($job.ActiveCount -ne 0) { throw 'Parent exited with surviving descendants; closing owned job' }
    if ($p.ExitCode -ne 0) { throw "Relocation exit $($p.ExitCode); see stderr log" }
    if (-not (Test-Path -LiteralPath $receipt)) { throw 'No verified relocation receipt' }
} catch {
    $failure=$_.Exception.Message
} finally {
    if ($job) { try { $job.Dispose() } catch { $failure="Job cleanup failed: $($_.Exception.Message); previous failure: $failure" } }
    $code=if ($p) {$p.ExitCode} else {$null}
    [ordered]@{session=$session;started=$started;finished=[DateTime]::UtcNow.ToString('o');supervisor_pid=$PID;exit_code=$code;failure=$failure;free_bytes_before=$freeBefore;minimum_free_bytes=4GB;process_peak_working_set_bytes=$peak;receipt=$receipt} | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 -LiteralPath $runRecord
}
if ($failure) { Write-Status 'failed' $failure; throw $failure }
Write-Status 'done' 'All six immutable files copied; source and destination SHA256 match'

& herdr agent prompt admission-codex "Relocation $Short job completed. Reconcile data/admission-codex/relocation-$Short-20260927/run.json, source-manifest and relocation-$Short-mac.json; verify all six byte/hash pairs before reporting completion to lead/IDM. The serial -4/-6 transfer continuation may still be running the next session; do not duplicate."
if ($LASTEXITCODE -ne 0) { throw "Relocation completion notification failed" }
