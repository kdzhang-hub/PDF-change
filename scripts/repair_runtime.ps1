param([Parameter(Mandatory=$true)][string]$Python)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$basePython=(Resolve-Path -LiteralPath $Python).Path
$configPath=Join-Path $projectRoot '.venv\pyvenv.cfg'
if(-not (Test-Path -LiteralPath $configPath)){throw 'Existing project virtual environment required.'}
$oldConfig=[IO.File]::ReadAllText($configPath)
$version=& $basePython -c "import sys;print('%d.%d' % sys.version_info[:2])"
if($LASTEXITCODE -ne 0 -or $oldConfig -notmatch ('(?m)^version = '+[regex]::Escape($version)+'(?:\.|\s|$)')){throw 'Base Python major/minor version must match the existing virtual environment.'}
$bits=& $basePython -c "import struct;print(struct.calcsize('P')*8)"
if($LASTEXITCODE -ne 0 -or $bits -ne '64'){throw 'A 64-bit Python is required for the existing native dependencies.'}
$backupRoot=Join-Path $projectRoot ('work\runtime-recovery-'+(Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Path $backupRoot | Out-Null
[IO.File]::WriteAllText((Join-Path $backupRoot 'pyvenv.cfg.before'),$oldConfig,(New-Object Text.UTF8Encoding($false)))
$newConfig=[regex]::Replace($oldConfig,'(?m)^home = .*',('home = '+(Split-Path -Parent $basePython)))
$newConfig=[regex]::Replace($newConfig,'(?m)^executable = .*',('executable = '+$basePython))
[IO.File]::WriteAllText($configPath,$newConfig,(New-Object Text.UTF8Encoding($false)))
& (Join-Path $projectRoot '.venv\Scripts\python.exe') -c "import sys,fitz,cv2,numpy,pptx,fastapi,skimage;print(sys.version);print('Project native dependencies imported successfully')"
if($LASTEXITCODE -ne 0){
 [IO.File]::WriteAllText($configPath,$oldConfig,(New-Object Text.UTF8Encoding($false)))
 throw 'Interpreter check failed; original virtual environment configuration restored.'
}
[IO.File]::WriteAllText((Join-Path $backupRoot 'pyvenv.cfg.after'),$newConfig,(New-Object Text.UTF8Encoding($false)))
Write-Output ('Recovered project environment; preserved original configuration at '+$backupRoot)
