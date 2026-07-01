$ErrorActionPreference = "Stop"

& (Join-Path $PSScriptRoot "check-packaging-toolchain.ps1") @args
