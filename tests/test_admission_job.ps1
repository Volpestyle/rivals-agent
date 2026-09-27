$ErrorActionPreference='Stop'
$repo=Split-Path -Parent $PSScriptRoot
Add-Type -Path (Join-Path $repo 'data/admission-codex/OwnedProcessJob.cs')
$python='C:/Users/volpe/.uv-envs/admission-codex/Scripts/python.exe'
$temp=Join-Path ([IO.Path]::GetTempPath()) ('admission-job-test-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temp | Out-Null
$fixture=Join-Path $temp 'parent.py'
@'
import os,subprocess,sys,time
child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(120)'])
print(child.pid,flush=True)
time.sleep(0.3)
os._exit(int(sys.argv[1]))
'@ | Set-Content -Encoding UTF8 -LiteralPath $fixture
$sleeper=Join-Path $temp 'unrelated.py'
'import time; time.sleep(120)' | Set-Content -Encoding UTF8 -LiteralPath $sleeper
$unrelated=Start-Process -FilePath $python -ArgumentList $sleeper -WindowStyle Hidden -PassThru
try {
  foreach ($code in @(0,1)) {
    $stdout=Join-Path $temp "$code.out"
    $stderr=Join-Path $temp "$code.err"
    $job=[AdmissionOwnedJob]::Start($python,[string[]]@($fixture,[string]$code),$repo,$stdout,$stderr)
    try {
      if (-not $job.Process.WaitForExit(10000)) { throw 'Fixture parent timed out' }
      if ($job.Process.ExitCode -ne $code) { throw 'Wrong parent exit code' }
      $childId=[int](Get-Content -LiteralPath $stdout -Raw).Trim()
      $child=Get-Process -Id $childId
      $retained=$child.Handle
      if ($job.ActiveCount -lt 1) { throw 'Live descendant missing from job after parent exit' }
    } finally { $job.Dispose() }
    if (-not $child.WaitForExit(10000)) { throw 'Owned orphan survived job close' }
    $unrelated.Refresh()
    if ($unrelated.HasExited) { throw 'Unrelated control was terminated' }
    Write-Output "PASS parent exit ${code}: owned child terminated; unrelated process preserved"
  }
} finally {
  $unrelated.Refresh()
  if (-not $unrelated.HasExited) { $unrelated.Kill(); $unrelated.WaitForExit() }
}
Write-Output "Evidence: $temp"
