# Every automated check, from scratch (the PowerShell twin of scripts/check_all.sh, which CI runs): a fresh virtual
# environment from requirements-dev.lock, pytest in zero-cost mode, then each browser suite on its own. Exits 1 if
# anything fails. Usage: powershell -File scripts\check_all.ps1 [output-dir]   env: CHECK_SUITES, BROWSER
param([string]$Out = "check-all-out")
Set-Location (Join-Path $PSScriptRoot "..")
$suites = if ($env:CHECK_SUITES) { $env:CHECK_SUITES -split " " } else { "workflows", "overlays", "panes", "explanations", "drawings", "backtest", "visual_audit" }
New-Item -ItemType Directory -Force $Out | Out-Null
$failed = @()

$venv = Join-Path ([IO.Path]::GetTempPath()) ("v2check-" + [Guid]::NewGuid().ToString("N").Substring(0, 8))  # short path
py -3.12 -m venv $venv
if (-not $?) { Write-Output "FAIL: could not create a Python 3.12 virtual environment"; exit 2 }
$vpy = Join-Path $venv "Scripts\python.exe"
& $vpy -m pip install --disable-pip-version-check -q -r requirements-dev.lock *> (Join-Path $Out "install.txt")
if ($LASTEXITCODE -ne 0) { Write-Output "FAIL: install (see $Out\install.txt)"; exit 2 }
& $vpy -m pip check *> (Join-Path $Out "pip_check.txt"); if ($LASTEXITCODE -ne 0) { $failed += "pip check" }
$frozen = & $vpy -m pip freeze --all --exclude pip
$locked = Get-Content requirements-dev.lock | Where-Object { $_ -notmatch "^#" }
$frozen | Set-Content (Join-Path $Out "freeze.txt")
if (Compare-Object $locked $frozen) { $failed += "installed packages differ from requirements-dev.lock" }

$before = git status --porcelain
$env:ZERO_COST_MODE = "1"
& $vpy -m pytest -q -p no:cacheprovider *> (Join-Path $Out "pytest.txt"); if ($LASTEXITCODE -ne 0) { $failed += "pytest" }
Write-Output ("pytest: " + (Get-Content (Join-Path $Out "pytest.txt") -Tail 1))
$env:PYTHON = $vpy
foreach ($suite in $suites) {
  node scripts\qa\run.mjs (Join-Path $Out "qa-$suite") $suite
  if ($LASTEXITCODE -ne 0) { $failed += "browser suite $suite" }
}
if (Compare-Object @($before) @(git status --porcelain)) { $failed += "the checks changed tracked files" }

foreach ($f in $failed) { Write-Output "FAIL: $f" }
Write-Output ("check_all: " + $(if ($failed.Count) { "FAILED" } else { "PASSED" }) + " (logs in $Out)")
exit $(if ($failed.Count) { 1 } else { 0 })
