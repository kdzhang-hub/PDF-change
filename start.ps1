param([int]$Port=8765,[switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { throw 'Run setup.ps1 first.' }
if (-not (Test-Path -LiteralPath 'frontend\dist\index.html')) { throw 'Build frontend with setup.ps1 first.' }
$url = 'http://127.0.0.1:' + $Port
$running = $false
try { $status = Invoke-RestMethod -Uri ($url + '/api/health') -TimeoutSec 2; $running = $status.ok -eq $true -and $null -ne $status.models } catch {}
if (-not $running) {
    New-Item -ItemType Directory -Path work -Force | Out-Null
    $logStamp=Get-Date -Format 'yyyyMMdd-HHmmss-fff'
    foreach($logName in @('server.log','server-error.log')){
        $oldLog=Join-Path $PSScriptRoot ('work\'+$logName)
        if((Test-Path -LiteralPath $oldLog) -and (Get-Item -LiteralPath $oldLog).Length -gt 0){
            $archive=Join-Path $PSScriptRoot ('work\'+$logStamp+'-'+$logName)
            Copy-Item -LiteralPath $oldLog -Destination $archive
        }
    }
    $env:PYTHONUTF8='1'
    $process = Start-Process -FilePath (Join-Path $PSScriptRoot '.venv\Scripts\python.exe') -ArgumentList "-m uvicorn backend.app:app --host 127.0.0.1 --port $Port" -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot 'work\server.log') -RedirectStandardError (Join-Path $PSScriptRoot 'work\server-error.log') -PassThru
    $process.Id | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'work\server.pid')
    for ($attempt=0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Milliseconds 500
        try { $status=Invoke-RestMethod -Uri ($url+'/api/health') -TimeoutSec 1; if ($status.ok) { $running=$true; break } } catch {}
    }
    if (-not $running) { throw 'Server failed to start. See work/server-error.log.' }
}
Write-Output ('LayerDeck is available at ' + $url)
if (-not $NoBrowser) { Start-Process $url }
