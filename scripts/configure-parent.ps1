param([ValidateSet('development','acceptance','production')] [string]$Environment='development',[string]$ApiBase='http://127.0.0.1:8930',[string]$AppId='touristappid')
$ErrorActionPreference='Stop'
$root=Join-Path (Split-Path (Split-Path $PSScriptRoot)) 'YEATS-Parent'
if($Environment -ne 'development' -and (!$ApiBase.StartsWith('https://') -or $AppId -eq 'touristappid')){throw 'HTTPS and independent YEATS AppID required'}
$local=[ordered]@{apiBase=$ApiBase;environment=$Environment;developmentLogin=($Environment -eq 'development')}
$json=$local|ConvertTo-Json -Compress
$path=Join-Path $root 'config.ts'
[IO.File]::WriteAllText($path,"// Generated environment configuration; no secrets.`nexport const config = $json;`n",[Text.UTF8Encoding]::new($false))
$projectPath=Join-Path $root 'project.config.json'
$project=Get-Content -LiteralPath (Join-Path $root 'project.config.template.json') -Raw|ConvertFrom-Json
$project.appid=$AppId
$project|ConvertTo-Json -Depth 10|Set-Content -Encoding utf8 $projectPath
Write-Output "Configured YEATS $Environment; AppSecret is never part of client configuration."
