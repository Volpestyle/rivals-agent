"""The rl PowerShell launchers parse (PowerShell parameter names are case-insensitive: $Episodes vs $EpisodeS once
made launch-sitting.ps1 fail with "Duplicate parameter" before it ran)."""
import shutil
import subprocess
from pathlib import Path

import pytest

LAUNCHERS = sorted(Path("rl").rglob("*.ps1"))


@pytest.mark.skipif(shutil.which("powershell") is None, reason="needs Windows PowerShell")
@pytest.mark.parametrize("script", LAUNCHERS, ids=str)
def test_launcher_parses(script):
    command = ("$e = $null; $t = $null; [System.Management.Automation.Language.Parser]::ParseFile("
               f"'{script.resolve()}', [ref]$t, [ref]$e) | Out-Null; "
               "if ($e.Count) { $e | ForEach-Object { $_.Message }; exit 1 }")
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
