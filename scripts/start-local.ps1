param([switch]$WithTestIdentities)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot
Set-Location -LiteralPath $root
& "$root/.venv/Scripts/python.exe" scripts/configure-wechat-local.py
if ($LASTEXITCODE -ne 0) { throw 'WeChat configuration failed' }
& npm.cmd run build:parent
if ($LASTEXITCODE -ne 0) { throw 'Parent build failed' }
& "$PSScriptRoot/local.ps1" start -WithTestIdentities:$WithTestIdentities
