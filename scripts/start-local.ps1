param([switch]$WithTestIdentities)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot
$parent=Join-Path (Split-Path $root) 'YEATS-Parent'
Push-Location -LiteralPath $parent
try { & npm.cmd run build; if ($LASTEXITCODE -ne 0) { throw 'Parent build failed' } } finally { Pop-Location }
& "$PSScriptRoot/local.ps1" start -WithTestIdentities:$WithTestIdentities
