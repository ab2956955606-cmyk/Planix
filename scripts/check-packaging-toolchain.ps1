param(
    [switch]$RequireGitHubAuth
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$Python = if (Test-Path $VenvPython) { $VenvPython } else { "python" }
$DesktopDir = Join-Path $Root "apps\desktop"
$Missing = New-Object System.Collections.Generic.List[string]
$CargoBin = Join-Path $env:USERPROFILE ".cargo\bin"
if ((Test-Path $CargoBin) -and ($env:Path -notlike "*$CargoBin*")) {
    $env:Path = "$CargoBin;$env:Path"
}

function Test-CommandPresent {
    param(
        [string]$Name,
        [string]$InstallHint
    )

    if (Get-Command $Name -ErrorAction SilentlyContinue) {
        Write-Host "OK: $Name"
        return
    }

    $Missing.Add("$Name missing. $InstallHint")
}

Test-CommandPresent "node" "Install Node.js 20+."
Test-CommandPresent "npm.cmd" "Install Node.js 20+."
Test-CommandPresent "npx.cmd" "Install Node.js 20+."
Test-CommandPresent "cargo" "Install Rust with rustup: https://rustup.rs/"
Test-CommandPresent "rustc" "Install Rust with rustup: https://rustup.rs/"

$GhCommand = Get-Command "gh.exe" -ErrorAction SilentlyContinue
if (-not $GhCommand) {
    $GhCommand = Get-Command "gh.cmd" -ErrorAction SilentlyContinue
}

if ($GhCommand) {
    Write-Host "OK: GitHub CLI candidate $($GhCommand.Source)"
}
elseif ($RequireGitHubAuth) {
    $Missing.Add("GitHub CLI missing. Install the official GitHub CLI or use the GitHub Actions release workflow.")
}
else {
    Write-Host "WARN: GitHub CLI not found. Local release publishing will be unavailable."
}

try {
    $PythonOutput = & $Python --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        $PythonOutput | Out-Host
        Write-Host "OK: Python"
    }
    else {
        $Missing.Add("Python missing. Create .venv or install Python 3.11+.")
    }
}
catch {
    $Missing.Add("Python missing. Create .venv or install Python 3.11+.")
}

try {
    $PyInstallerOutput = & $Python -m PyInstaller --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        $PyInstallerOutput | Out-Host
        Write-Host "OK: PyInstaller"
    }
    else {
        $Missing.Add("PyInstaller missing. Run: $Python -m pip install -r requirements-build.txt")
    }
}
catch {
    $Missing.Add("PyInstaller missing. Run: $Python -m pip install -r requirements-build.txt")
}

$TauriCli = Join-Path $DesktopDir "node_modules\.bin\tauri.cmd"
if (Test-Path $TauriCli) {
    & $TauriCli --version | Out-Host
    Write-Host "OK: Tauri CLI"
}
elseif (Get-Command "tauri.cmd" -ErrorAction SilentlyContinue) {
    tauri.cmd --version | Out-Host
    Write-Host "OK: Tauri CLI"
}
else {
    $Missing.Add("Tauri CLI missing. Run: cd apps\desktop; npm.cmd install")
}

if ($RequireGitHubAuth) {
    try {
        & $GhCommand.Source auth status
        if ($LASTEXITCODE -eq 0) {
            Write-Host "OK: GitHub CLI auth"
        }
        else {
            $Missing.Add("GitHub CLI is not authenticated. Run: gh.cmd auth login")
        }
    }
    catch {
        $Missing.Add("GitHub CLI is not authenticated. Run: gh.cmd auth login")
    }
}

if ($Missing.Count -gt 0) {
    Write-Host ""
    Write-Host "Packaging toolchain is incomplete:"
    foreach ($Item in $Missing) {
        Write-Host "- $Item"
    }
    exit 1
}

Write-Host "Packaging toolchain is ready."
