param([switch]$WithTestIdentities)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot
Set-Location -LiteralPath $root
if ((git rev-parse --show-toplevel).Trim().Replace('/','\') -ne $root) { throw 'YEATS repository identity mismatch' }
if (Get-NetTCPConnection -LocalPort 8930 -State Listen -ErrorAction SilentlyContinue) { throw 'Port 8930 is already in use. Verify the existing YEATS service instead of starting a duplicate.' }
$env:YEATS_ENVIRONMENT='development'
$env:YEATS_ENABLE_DEVELOPMENT_LOGIN=if($WithTestIdentities){'true'}else{'false'}
& "$root\.venv\Scripts\python.exe" scripts/resume-postgres.py
if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL startup failed' }
& "$root\.venv\Scripts\alembic.exe" upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Database migration failed' }
& "$root\.venv\Scripts\python.exe" scripts/configure-wechat-local.py
if ($LASTEXITCODE -ne 0) { throw 'Independent WeChat configuration unavailable' }
& npm.cmd run build:parent
if ($LASTEXITCODE -ne 0) { throw 'Native build failed' }
& "$root\.venv\Scripts\python.exe" scripts/run-api.py
