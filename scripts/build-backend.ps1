$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$Python = if (Test-Path $VenvPython) { $VenvPython } else { "python" }
$SpecPath = Join-Path $Root "scripts\pyinstaller\mynotes-api.spec"
$SidecarDir = Join-Path $Root "apps\desktop\src-tauri\binaries"
$TargetTriple = if ($env:MYNOTES_TAURI_TARGET) { $env:MYNOTES_TAURI_TARGET } else { "x86_64-pc-windows-msvc" }

if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) {
    throw "Python was not found. Create .venv or install Python 3.11+ before building the backend sidecar."
}

Push-Location $Root
try {
    & $Python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        throw "pip install failed for requirements.txt"
    }

    & $Python -m pip install -r requirements-build.txt
    if ($LASTEXITCODE -ne 0) {
        throw "pip install failed for requirements-build.txt"
    }

    & $Python -m PyInstaller --version *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller is not installed. Run: $Python -m pip install pyinstaller"
    }

    & $Python -m PyInstaller $SpecPath --noconfirm --clean --distpath (Join-Path $Root "build\pyinstaller-dist") --workpath (Join-Path $Root "build\pyinstaller-work")
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed to build mynotes-api."
    }

    New-Item -ItemType Directory -Force -Path $SidecarDir | Out-Null
    $BuiltExe = Join-Path $Root "build\pyinstaller-dist\mynotes-api.exe"
    if (-not (Test-Path $BuiltExe)) {
        throw "Expected sidecar was not created: $BuiltExe"
    }

    $TauriSidecar = Join-Path $SidecarDir "mynotes-api-$TargetTriple.exe"
    Copy-Item -LiteralPath $BuiltExe -Destination $TauriSidecar -Force

    if (-not (Test-Path $TauriSidecar)) {
        throw "Missing Tauri sidecar: $TauriSidecar"
    }

    Write-Host "Sidecar copied to $TauriSidecar"
}
finally {
    Pop-Location
}
