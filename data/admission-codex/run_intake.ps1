param([Parameter(Mandatory=$true)][string]$Step,[Parameter(Mandatory=$true)][string]$Session,[double]$VoteFrom=60,[ValidateSet('initial','ping-a1')][string]$Revision='initial')
$ErrorActionPreference='Stop'
$repo='C:/Users/volpe/repos/rivals-agent'
$allowed=@('20260927T051206-888Z-150600-4','20260927T052001-827Z-150600-5','20260927T053118-260Z-150600-6','20260927T053838-153Z-150600-7','20260927T055006-068Z-150600-8','20260927T060021-195Z-150600-10','20260927T061107-953Z-150600-11','20260927T061900-143Z-150600-12')
if ($Session -notin $allowed -or $Step -notin @('vote','scan','regime','motor','propose','evidence','assemble','receipt')) { throw 'Outside bounded night-match scope' }
if ($Session -eq '20260927T052001-827Z-150600-5' -and ($Revision -ne 'ping-a1' -or $Step -notin @('propose','evidence','assemble','receipt'))) { throw 'Match -5 only permits the authorized ping delta here' }
$python='C:/Users/volpe/.uv-envs/admission-codex/Scripts/python.exe'
$runRoot=Join-Path $repo "data/admission-codex/runs/$Session"
if ($Revision -eq 'ping-a1') { $runRoot=Join-Path $runRoot 'ping-a1' }
New-Item -ItemType Directory -Path $runRoot -Force | Out-Null
$out=Join-Path $runRoot "$Step.stdout.log"
$err=Join-Path $runRoot "$Step.stderr.log"
$receipt=Join-Path $runRoot "$Step.run.json"
if ((Test-Path -LiteralPath $receipt) -or (Test-Path -LiteralPath $out)) { throw 'Run record exists; reconcile before retry' }
function Check-Resources {
  if (Get-Process -Name 'Marvel*','obs64' -ErrorAction SilentlyContinue) { throw 'Marvel or OBS active' }
  $freeBytes=[long](Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory*1024
  if ($freeBytes -lt 2GB) { throw 'Free physical memory below 2 GiB' }
  return $freeBytes
}
$freeBefore=Check-Resources
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
$arguments=@('-u','data/human/sessions/intake_session.py',$Step,$Session,'--scratch','data/admission-codex/intake','--snapshot','code-snapshot-f8fd92c-bounded-20260927')
if ($Revision -eq 'ping-a1') {
  if ($Step -notin @('propose','evidence','assemble','receipt')) { throw 'Ping revision permits proposal, evidence, assembly and receipt only' }
  $arguments=@('-u','data/human/sessions/intake_session.py',$Step,$Session,'--scratch','data/admission-codex/intake','--snapshot','code-snapshot-f8fd92c-ping-20260927','--supersedes','Lead 2026-09-27: exclude held middle-mouse ping wheel plus 2 s settle; preserve prior packet')
  if ($Step -eq 'evidence' -and $Session -in @('20260927T051206-888Z-150600-4','20260927T052001-827Z-150600-5')) { $arguments+=@('--ping-delta') }
}
if ($Step -eq 'vote') { $arguments+=@('--vote-from',$VoteFrom.ToString([Globalization.CultureInfo]::InvariantCulture)) }
if ($Step -in @('propose','evidence')) { $arguments+=@('--earlier-snapshot','code-snapshot-f8fd92c-6046514b') }
if ($Step -eq 'assemble') { $arguments=@('-u','data/human/sessions/assemble_session.py',$Session,'--independent-verdicts',"data/human/sessions/$Session/independent-review.verdicts.json",'--snapshot','code-snapshot-f8fd92c-6046514b') }
if ($Step -eq 'assemble' -and $Revision -eq 'ping-a1') { $arguments+=@('--supersedes','Lead 2026-09-27: ping-wheel boundary correction; prior assembly retained in versioned files and assembly-ping-a1-supersedes.json') }
if ($Step -eq 'receipt') { $arguments=@('-u','data/human/sessions/match_admission.py',$Session,'--snapshot','code-snapshot-f8fd92c-6046514b','--out',(Join-Path $runRoot 'match-admission.pending.json')) }
$started=[DateTime]::UtcNow.ToString('o')
$statusCode="import sys; from scripts.job_status import write; write('admission-'+sys.argv[1],owner='admission-codex',stage=sys.argv[3],host='pc',evidence=sys.argv[2],progress=sys.argv[4])"
& $python -c $statusCode $Session $out 'running' $Step
Add-Type -Path (Join-Path $PSScriptRoot 'OwnedProcessJob.cs')
$job=[AdmissionOwnedJob]::Start($python,[string[]]$arguments,$repo,$out,$err)
$p=$job.Process
$peak=@{}
$failure=$null
try {
  while (-not $p.HasExited) {
    $freeNow=Check-Resources
    $all=@(Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,WorkingSetSize)
    $owned=[Collections.Generic.HashSet[int]]::new()
    [void]$owned.Add($p.Id)
    do {
      $changed=$false
      foreach ($r in $all) { if ($owned.Contains([int]$r.ParentProcessId) -and -not $owned.Contains([int]$r.ProcessId)) { [void]$owned.Add([int]$r.ProcessId);$changed=$true } }
    } while ($changed)
    foreach ($r in $all) {
      if (-not $owned.Contains([int]$r.ProcessId)) { continue }
      $key=[string]$r.ProcessId
      $peak[$key]=[Math]::Max([long]$peak[$key],[long]$r.WorkingSetSize)
      if ([long]$r.WorkingSetSize -ge 2800000000) { throw "Owned process $key exceeded 2.8 GB working set" }
    }
    Start-Sleep -Seconds 1
    $p.Refresh()
  }
  $p.WaitForExit()
  if ($job.ActiveCount -ne 0) { throw 'Parent exited with surviving owned descendants; closing job to terminate them' }
  if ($p.ExitCode -ne 0) { throw "Intake exit $($p.ExitCode); see $err" }
  if ($Step -eq 'vote') {
    $mapping=Get-Content -Raw -LiteralPath "$repo/data/human/sessions/$Session/slot-mapping.json" | ConvertFrom-Json
    if ($mapping.equals_051828_and_032454 -ne $true) { throw 'Vote mapping differs; stop and inspect' }
  }
} catch {
  $failure=$_.Exception.Message
} finally {
  try { $job.Dispose() } catch { $failure="Job cleanup failed: $($_.Exception.Message); previous failure: $failure" }
  [ordered]@{session=$Session;step=$Step;started=$started;finished=[DateTime]::UtcNow.ToString('o');pid=$p.Id;exit_code=$p.ExitCode;failure=$failure;free_bytes_before=$freeBefore;process_peak_working_set_bytes=$peak;arguments=$arguments} | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 -LiteralPath $receipt
}
if ($failure) { & $python -c $statusCode $Session $out 'failed' $Step; throw $failure }
& $python -c $statusCode $Session $out 'done' $Step
Get-Content -LiteralPath $out -Tail 6
