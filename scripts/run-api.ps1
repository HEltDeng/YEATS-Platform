$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot
Set-Location -LiteralPath $root
& "$root\.venv\Scripts\uvicorn.exe" yeats.main:app --app-dir services/api --host 127.0.0.1 --port 8930 --no-access-log
