$ErrorActionPreference='Stop'
$repo='C:/Users/volpe/repos/rivals-agent'
Set-Location -LiteralPath $repo
[Diagnostics.Process]::GetCurrentProcess().PriorityClass='BelowNormal'
$python='C:/Users/volpe/repos/rivals-agent/.venv/Scripts/python.exe'
$session='later-7-8-10-11-12'
$jobName='idm-later-match-relocation-20260928'
$runRoot=Join-Path $repo 'data/idm/range-to-match-20260928'
$out=Join-Path $runRoot 'relocate.stdout.log'
$err=Join-Path $runRoot 'relocate.stderr.log'
$receipt=Join-Path $runRoot 'relocations-complete.json'
$runRecord=Join-Path $runRoot 'run.json'
if ((Test-Path -LiteralPath $out) -or (Test-Path -LiteralPath $receipt) -or (Test-Path -LiteralPath $runRecord)) { throw 'Existing attempt; reconcile instead of overwriting' }
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
$PID | Set-Content -LiteralPath (Join-Path $runRoot 'supervisor.pid')
$statusCode="import sys; from scripts.job_status import write; write('$jobName',owner='idm-owner',stage=sys.argv[1],host='pc',evidence=sys.argv[2],progress=sys.argv[3])"
function Write-Status([string]$stage,[string]$progress) {
    & $python -c $statusCode $stage $receipt $progress
    if ($LASTEXITCODE -ne 0) { throw 'Status write failed' }
}
function Check-Resources {
    $available=[long](Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory*1024
    if ($available -lt 4GB) { throw 'Free physical memory below 4 GiB; relocation stopped' }
    return $available
}
$started=[DateTime]::UtcNow.ToString('o')
$failure=$null; $job=$null; $p=$null; $peak=@{}; $freeBefore=$null
try {
    Write-Status 'running' 'Checking resources before source hashes'
    $freeBefore=Check-Resources
    Add-Type -Path (Join-Path $repo 'data/admission-codex/OwnedProcessJob.cs')
    $arguments=@('-u','data/idm/range-to-match-20260928/transfer-later.py')
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
Write-Status 'done' 'All five later-match immutable relocations verified; decode pending'

& 'C:/Users/volpe/.herdr/packages/standalone/releases/0.9.1-x86_64-pc-windows-msvc/herdr.exe' agent prompt idm-owner 'IDM LATER MATCH RELOCATION COMPLETE: read data/idm/range-to-match-20260928/run.json and relocations-complete.json. All five originals/tables copied and hash-verified. Continue authorized serial Mac stores and frozen full03/prior/zero diagnostic; no fit or paid step. Mac slot reserved by lead.'
if ($LASTEXITCODE -ne 0) { throw 'Completion notification failed; receipts retained' }
