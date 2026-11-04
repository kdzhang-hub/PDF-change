param([string]$Python = '')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not $Python) { $Python = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' }
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { throw 'Run setup.ps1 first.' }
& $Python -m pip --python .venv\Scripts\python.exe install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu124
if ($LASTEXITCODE -ne 0) { throw 'Torch installation failed.' }
& $Python -m pip --python .venv\Scripts\python.exe install paddlepaddle==3.0.0 paddleocr==3.0.3 'paddlex[ocr]==3.0.3' hydra-core==1.3.8 iopath==0.1.10
if ($LASTEXITCODE -ne 0) { throw 'OCR installation failed.' }
$env:SAM2_BUILD_CUDA='0'
& $Python -m pip --python .venv\Scripts\python.exe install --no-build-isolation 'https://github.com/facebookresearch/sam2/archive/2b90b9f5ceec907a1c18123530e92e794ad901a4.zip'
if ($LASTEXITCODE -ne 0) { throw 'SAM installation failed.' }
& .\.venv\Scripts\python.exe scripts\download_models.py
if ($LASTEXITCODE -ne 0) { throw 'Model download failed.' }
Write-Output 'Local models are ready. Downloads are checksum-verified against models.lock.json.'
