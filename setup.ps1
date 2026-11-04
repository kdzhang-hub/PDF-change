param([string]$Python = '')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not $Python) {
    $bundled = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $bundled) { $Python = $bundled }
    else { $Python = (Get-Command python -ErrorAction Stop).Source }
}
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    & $Python -m venv --without-pip .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 is required.' }
}
& $Python -m pip --python .venv\Scripts\python.exe install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
Push-Location frontend
try {
    & npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw 'npm ci failed.' }
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
} finally { Pop-Location }
Write-Output 'Ready. Run start.ps1. Local models can be provisioned with setup-models.ps1.'
