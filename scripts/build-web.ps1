$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$WebDir = Join-Path $Root "apps\web"

if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw "npm.cmd was not found. Install Node.js 20+ before building the web app."
}

Push-Location $WebDir
try {
    if (Test-Path "package-lock.json") {
        npm.cmd ci
    }
    else {
        npm.cmd install
    }

    npm.cmd run build
}
finally {
    Pop-Location
}
