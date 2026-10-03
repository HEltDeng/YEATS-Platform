$ErrorActionPreference = 'Stop'
$secretDir = Join-Path $env:LOCALAPPDATA 'YEATS\secrets'
New-Item -ItemType Directory -Force -Path $secretDir | Out-Null
$sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
& icacls.exe $secretDir /inheritance:r /grant:r "*${sid}:(OI)(CI)F" '*S-1-5-18:(OI)(CI)F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Cannot restrict secret directory ACL' }
$path = Join-Path $secretDir 'wechat.dev.env'
if (!(Test-Path -LiteralPath $path)) {
    [System.IO.File]::WriteAllText($path,"YEATS_WECHAT_APPID=`nYEATS_WECHAT_SECRET=`n",[System.Text.UTF8Encoding]::new($false))
}
Write-Output "Secret template: $path (values not printed)"
Write-Output 'Upload key must use a separate file; no upload key created.'
