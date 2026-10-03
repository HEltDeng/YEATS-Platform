param([ValidateSet('start','status','stop','restart','restart-api')][string]$Action='status',[switch]$WithTestIdentities)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot
$python=Join-Path $root '.venv/Scripts/python.exe'
$runtime=Join-Path $root 'runtime'
$pgdata=Join-Path $runtime 'postgres-data'
$pgctl=Join-Path $runtime 'postgres-toolchain/pgsql/bin/pg_ctl.exe'
$runner=Join-Path $root 'scripts/run-api.py'
Set-Location -LiteralPath $root
if (!(Test-Path (Join-Path $root 'services/api/yeats/main.py'))) { throw 'Not a YEATS backend checkout' }
function Listener($port) { @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique) }
function OwnedApi {
  $ids=Listener 8930
  if (!$ids.Count) { return $null }
  if ($ids.Count -ne 1) { throw 'Multiple API listeners; refused' }
  $process=Get-CimInstance Win32_Process -Filter "ProcessId=$($ids[0])"
  if (!$process -or !$process.CommandLine -or !$process.CommandLine.Contains($runner)) { throw '8930 belongs to an unverified process. It will not be stopped.' }
  return $process
}
function CheckDb {
  & $python (Join-Path $root 'scripts/verify-local-db.py')
  if ($LASTEXITCODE -ne 0) { throw 'Existing YEATS PostgreSQL not ready or identity mismatch' }
}
function Health {
  try {
    $result=Invoke-RestMethod -Uri 'http://127.0.0.1:8930/health' -NoProxy -TimeoutSec 3
    return ($result.service -eq 'yeats' -and $result.status -eq 'ok' -and $result.database -eq 'postgresql')
  } catch { return $false }
}
function Status {
  $api=OwnedApi
  $db=Listener 55432
  Write-Host "YEATS API listening: $([bool]$api); healthy: $(Health); PostgreSQL listening: $([bool]$db.Count)"
  if ($db.Count) { CheckDb }
  Write-Host 'API: http://127.0.0.1:8930 | Health: /health'
  Write-Host "Local logs (do not upload): $runtime\api.stderr.log; $runtime\postgres.log"
  Write-Host "Preserved database: $pgdata | Uploads: $runtime\private-files"
}
if ($Action -in 'stop','restart','restart-api') {
  # Verify both identities before touching either service.
  $api=OwnedApi
  $db=Listener 55432
  if ($db.Count) { CheckDb }
  if ($api) {
    Stop-Process -Id $api.ProcessId -ErrorAction Stop
    # Windows may retain a terminated listener briefly; wait only for the
    # verified process to release it before re-evaluating port ownership.
    for ($attempt=0;$attempt -lt 50;$attempt++) {
      if (!((Listener 8930) -contains $api.ProcessId)) { break }
      Start-Sleep -Milliseconds 100
    }
    if ((Listener 8930) -contains $api.ProcessId) { throw 'Verified YEATS API listener did not release its port; restart stopped safely' }
  }
  if ($db.Count -and $Action -ne 'restart-api') {
    & $pgctl -D $pgdata -m fast -w stop
    if ($LASTEXITCODE -ne 0) { throw 'YEATS PostgreSQL stop failed' }
  }
  if ($Action -eq 'stop') { Status; exit 0 }
}
if ($Action -in 'start','restart','restart-api') {
  $api=OwnedApi
  if ($api) {
    CheckDb
    if (!(Health)) { throw 'Existing YEATS API unhealthy; inspect logs and explicitly restart' }
    Write-Host 'YEATS is already ready. Existing identity mode retained.'
    Status; exit 0
  }
  if (!(Test-Path (Join-Path $pgdata 'PG_VERSION'))) { throw 'Existing YEATS database required; will not initialize a new database' }
  if (!(Listener 55432).Count) {
    & $pgctl -D $pgdata -l (Join-Path $runtime 'postgres.log') -o '-h 127.0.0.1 -p 55432' -w start
    if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL startup failed' }
  }
  CheckDb
  $env:YEATS_ENVIRONMENT='development'
  $env:YEATS_ENABLE_DEVELOPMENT_LOGIN=if($WithTestIdentities){'true'}else{'false'}
  & $python -m alembic upgrade head
  if ($LASTEXITCODE -ne 0) { throw 'Migration failed' }
  $child=Start-Process -FilePath $python -ArgumentList ('"'+$runner+'"') -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtime 'api.stdout.log') -RedirectStandardError (Join-Path $runtime 'api.stderr.log') -PassThru
  $ready=$false
  for ($attempt=0;$attempt -lt 30;$attempt++) {
    if ($child.HasExited) { throw 'API exited before readiness; inspect local error log' }
    if (Health) { $ready=$true;break }
    Start-Sleep -Milliseconds 500
  }
  if (!$ready) { throw 'API readiness timed out; not reporting success' }
  $null=OwnedApi
}
Status
