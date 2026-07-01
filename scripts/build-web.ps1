$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$WebDir = Join-Path $Root "apps\web"
$IndexPath = Join-Path $WebDir "index.html"
$DistIndexPath = Join-Path $WebDir "dist\index.html"

if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw "npm.cmd was not found. Install Node.js 20+ before building the web app."
}

if (-not (Test-Path $IndexPath)) {
    throw "Missing frontend entry: $IndexPath"
}

Push-Location $WebDir
try {
    if (Test-Path "node_modules") {
        npm.cmd install
        if ($LASTEXITCODE -ne 0) {
            throw "npm install failed for apps/web."
        }
    }
    elseif (Test-Path "package-lock.json") {
        npm.cmd ci
        if ($LASTEXITCODE -ne 0) {
            throw "npm ci failed for apps/web."
        }
    }
    else {
        npm.cmd install
        if ($LASTEXITCODE -ne 0) {
            throw "npm install failed for apps/web."
        }
    }

    npm.cmd run build
    if ($LASTEXITCODE -ne 0) {
        throw "npm run build failed for apps/web."
    }

    if (-not (Test-Path $DistIndexPath)) {
        throw "Frontend build is incomplete. Missing required asset: $DistIndexPath"
    }

    Write-Host "Frontend index asset verified: $DistIndexPath"
}
finally {
    Pop-Location
}
