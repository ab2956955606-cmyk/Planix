param(
    [string]$Version = "1.1.4",
    [switch]$CreateGitHubRelease
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$CleanVersion = $Version.TrimStart("v")
$Tag = "v$CleanVersion"
$ReleaseDir = Join-Path $Root "release"
$InstallerName = "Planix-$Tag-windows-x64.msi"
$HashName = "Planix-$Tag-windows-x64.sha256"
$InstallerPath = Join-Path $ReleaseDir $InstallerName
$HashPath = Join-Path $ReleaseDir $HashName
$DesktopDir = Join-Path $Root "apps\desktop"
$TauriTargetDir = Join-Path $DesktopDir "src-tauri\target\release\bundle\msi"
$WebIndexPath = Join-Path $Root "apps\web\dist\index.html"
$DesktopResourceIndexPath = Join-Path $Root "apps\desktop\src-tauri\resources\index.html"
$SidecarPath = Join-Path $Root "apps\desktop\src-tauri\resources\binaries\planix-api.exe"

New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null

& (Join-Path $PSScriptRoot "build-web.ps1")
if (-not (Test-Path $WebIndexPath)) {
    throw "Missing frontend asset after web build: $WebIndexPath"
}
if (-not (Test-Path $DesktopResourceIndexPath)) {
    throw "Missing desktop frontend resource after web build: $DesktopResourceIndexPath"
}

& (Join-Path $PSScriptRoot "build-backend.ps1")
if (-not (Test-Path $SidecarPath)) {
    throw "Missing packaged resource sidecar: $SidecarPath"
}

Push-Location $DesktopDir
try {
    if (Test-Path "node_modules") {
        npm.cmd install
        if ($LASTEXITCODE -ne 0) {
            throw "npm install failed for apps/desktop."
        }
    }
    elseif (Test-Path "package-lock.json") {
        npm.cmd ci
        if ($LASTEXITCODE -ne 0) {
            throw "npm ci failed for apps/desktop."
        }
    }
    else {
        npm.cmd install
        if ($LASTEXITCODE -ne 0) {
            throw "npm install failed for apps/desktop."
        }
    }

    & (Join-Path $PSScriptRoot "check-packaging-toolchain.ps1")

    $env:RUST_BACKTRACE = "1"
    $BuildLog = Join-Path $Root "desktop-build-error.log"
    $BuildOutput = & cmd.exe /d /s /c "npm.cmd run build 2>&1"
    $BuildExitCode = $LASTEXITCODE
    $BuildOutput | Tee-Object -FilePath $BuildLog
    if ($BuildExitCode -ne 0) {
        Write-Host "Tauri/Rust build failed. Full error log: $BuildLog" -ForegroundColor Red
        throw "npm run build failed for apps/desktop. See $BuildLog for details."
    }
}
finally {
    Pop-Location
}

$Msi = Get-ChildItem -Path $TauriTargetDir -Filter "*.msi" -Recurse -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if (-not $Msi) {
    throw "Tauri build did not produce an MSI under $TauriTargetDir"
}

Copy-Item -LiteralPath $Msi.FullName -Destination $InstallerPath -Force
$Hash = Get-FileHash -Algorithm SHA256 -LiteralPath $InstallerPath
Set-Content -Path $HashPath -Value "$($Hash.Hash.ToLower())  $InstallerName" -Encoding ASCII

Write-Host "Release installer: $InstallerPath"
Write-Host "SHA256 file: $HashPath"

if ($CreateGitHubRelease) {
    $NotesPath = Join-Path $Root "docs\release-v$CleanVersion.md"
    if (-not (Test-Path $NotesPath)) {
        $NotesPath = Join-Path $Root "docs\release-v1.1.4.md"
    }
    & (Join-Path $PSScriptRoot "check-packaging-toolchain.ps1") -RequireGitHubAuth
    $GhCommand = Get-Command "gh.exe" -ErrorAction SilentlyContinue
    if (-not $GhCommand) {
        $GhCommand = Get-Command "gh.cmd" -ErrorAction SilentlyContinue
    }
    if (-not $GhCommand) {
        throw "GitHub CLI is required for local release publishing."
    }

    git diff --quiet
    if ($LASTEXITCODE -ne 0) {
        throw "Working tree has uncommitted changes. Commit before publishing a GitHub Release."
    }

    & $GhCommand.Source release view $Tag *> $null
    if ($LASTEXITCODE -eq 0) {
        & $GhCommand.Source release upload $Tag $InstallerPath $HashPath --clobber
    }
    else {
        & $GhCommand.Source release create $Tag $InstallerPath $HashPath --title "Planix $Tag" --notes-file $NotesPath
    }
}
