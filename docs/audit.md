# Planix Desktop Audit

This document records the current desktop-readiness baseline for Planix.

## Current Product Target

Planix is a Windows-installable AI planning workspace. A normal user should be able to install the NSIS Setup.exe, open `planix.exe`, load the bundled web UI, and use the FastAPI sidecar without installing Node.js, Python, Rust, npm, pip, or command-line tools. MSI remains available as a backup installer.

## Current Architecture

```text
apps/web                 React + TypeScript + Vite
backend/app              FastAPI application
backend/app/db.py        SQLite schema and connection layer
scripts/pyinstaller      PyInstaller sidecar entry/spec
apps/desktop             Tauri v2 desktop shell
release                  NSIS Setup.exe, MSI, and SHA256 release assets
```

## Runtime Contract

```text
Planix desktop window
  -> resources/index.html
  -> Tauri proxy_api IPC
  -> http://127.0.0.1:8000
  -> planix-api.exe
  -> SQLite
```

Desktop data defaults to:

```text
%APPDATA%\Planix\planix.db
```

Development data defaults to:

```text
data\planix.db
```

## Required Installer Layout

```text
Planix\
  planix.exe
  resources\
    index.html
    assets\
    binaries\
      planix-api.exe
```

## Verification Checklist

- `python -m compileall backend`
- `.\.venv\Scripts\python.exe -m pytest backend\tests`
- `cd apps\web && npx.cmd tsc -b`
- `cd apps\web && npm.cmd run lint`
- `cd apps\web && npm.cmd run build`
- `powershell -ExecutionPolicy Bypass -File .\scripts\check-desktop-config.ps1`
- `powershell -ExecutionPolicy Bypass -File .\scripts\check-packaging-toolchain.ps1`
- `powershell -ExecutionPolicy Bypass -File .\scripts\build-release.ps1 -Version 1.1.4`

## Known Risks

- The Windows installers are unsigned.
- The app does not yet include auto-update.
- The desktop sidecar uses port `8000`; a port conflict blocks local API startup.
- Live model calls require the user's own API key and `USE_REAL_LLM=1`.
