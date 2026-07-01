param(
    [string]$AppName = "MyNotes AI",
    [string]$HealthUrl = "http://127.0.0.1:8000/api/health",
    [int]$StartupSeconds = 8
)

$ErrorActionPreference = "Stop"

$InstallRoots = @(
    Join-Path $env:LOCALAPPDATA "Programs\$AppName",
    Join-Path $env:ProgramFiles $AppName,
    Join-Path ${env:ProgramFiles(x86)} $AppName
) | Where-Object { $_ -and (Test-Path $_) }

$AppExe = $null
foreach ($Root in $InstallRoots) {
    $Candidate = Get-ChildItem -Path $Root -Filter "MyNotes AI.exe" -Recurse -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($Candidate) {
        $AppExe = $Candidate.FullName
        break
    }
}

if (-not $AppExe) {
    throw @"
MyNotes AI does not appear to be installed.
Possible causes:
- MSI was not installed.
- App installed to an unexpected directory.
- Installation was incomplete.
"@
}

Write-Host "Installed app found: $AppExe"
$Process = Start-Process -FilePath $AppExe -PassThru
Write-Host "Started MyNotes AI with PID $($Process.Id). Waiting $StartupSeconds seconds..."
Start-Sleep -Seconds $StartupSeconds

try {
    $Response = Invoke-RestMethod -Uri $HealthUrl -Method Get -TimeoutSec 5
    if ($Response.status -ne "ok") {
        throw "Unexpected health response: $($Response | ConvertTo-Json -Depth 5)"
    }

    Write-Host "Health check passed:"
    $Response | ConvertTo-Json -Depth 5
}
catch {
    $LogPath = Join-Path $env:APPDATA "MyNotes AI\logs\desktop.log"
    throw @"
Installed app smoke test failed.
Health endpoint did not return {"status":"ok"} at $HealthUrl.

Possible causes:
- sidecar 未启动
- 8000 端口被占用
- WebView2 缺失
- 安装包不完整
- index.html 缺失
- asset not found: index.html

Please check: $LogPath

Original error:
$($_.Exception.Message)
"@
}

Write-Host "Smoke test complete. If the UI is visible and no asset-not-found dialog appears, the installed MSI is ready for manual release upload."
