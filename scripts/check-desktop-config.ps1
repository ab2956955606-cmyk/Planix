$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$ConfigPath = Join-Path $Root "apps\desktop\src-tauri\tauri.conf.json"
$CargoPath = Join-Path $Root "apps\desktop\src-tauri\Cargo.toml"
$MainPath = Join-Path $Root "apps\desktop\src-tauri\src\main.rs"
$SpecPath = Join-Path $Root "scripts\pyinstaller\mynotes-api.spec"
$EntryPath = Join-Path $Root "scripts\pyinstaller\mynotes_api_entry.py"
$HealthScriptPath = Join-Path $Root "scripts\wait-api-health.ps1"

foreach ($Path in @($ConfigPath, $CargoPath, $MainPath, $SpecPath, $EntryPath, $HealthScriptPath)) {
    if (-not (Test-Path $Path)) {
        throw "Missing required Phase 7 desktop file: $Path"
    }
}

$Config = Get-Content -Raw $ConfigPath | ConvertFrom-Json

if ($Config.productName -ne "MyNotes AI") {
    throw "Unexpected desktop productName: $($Config.productName)"
}

if ($Config.identifier -ne "com.mynotes.ai") {
    throw "Unexpected bundle identifier: $($Config.identifier)"
}

if ($Config.mainBinaryName -ne "mynotes") {
    throw "Unexpected mainBinaryName: $($Config.mainBinaryName)"
}

if ($Config.build.devUrl -ne "http://127.0.0.1:5173") {
    throw "Unexpected devUrl: $($Config.build.devUrl)"
}

if ($Config.build.frontendDist -ne "resources") {
    throw "Unexpected frontendDist: $($Config.build.frontendDist)"
}

if ($Config.bundle.windows.webviewInstallMode.type -ne "embedBootstrapper") {
    throw "Windows bundle should embed the WebView2 bootstrapper."
}

$Resources = $Config.bundle.resources
if ($Resources.'resources/index.html' -ne "resources/index.html") {
    throw "Desktop bundle must copy resources/index.html."
}
if ($Resources.'resources/assets' -ne "resources/assets") {
    throw "Desktop bundle must copy resources/assets."
}
if ($Resources.'resources/binaries/mynotes-api.exe' -ne "resources/binaries/mynotes-api.exe") {
    throw "Desktop bundle must copy resources/binaries/mynotes-api.exe."
}

$WebEntryPath = Join-Path $Root "apps\web\index.html"
if (-not (Test-Path $WebEntryPath)) {
    throw "Missing frontend entry: $WebEntryPath"
}

Write-Host "Desktop scaffold configuration looks ready for Phase 8 packaging."
