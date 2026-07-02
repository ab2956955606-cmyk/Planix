# MyNotes AI Desktop

This folder contains the Tauri desktop shell and Phase 8 Windows release pipeline.

The app bundles the Vite web build and launches the FastAPI backend as a Tauri sidecar named `mynotes-api`.

## Development

```powershell
.\scripts\dev-desktop.ps1
cd apps\desktop
npm install
npm run dev
```

The desktop dev window loads:

```text
http://127.0.0.1:5173
```

## Release Strategy

1. `scripts/build-web.ps1` builds `apps/web/dist` and syncs it into `apps/desktop/src-tauri/resources`.
2. `scripts/build-backend.ps1` packages the FastAPI backend as `mynotes-api`.
3. Tauri bundles the web dist and launches the backend through the `mynotes-api` sidecar.
4. The sidecar receives `MYNOTES_ENV=desktop` and stores SQLite data in the user data directory unless `MYNOTES_DB_PATH` is set.

## Release Build

```powershell
.\scripts\check-packaging-toolchain.ps1
.\scripts\build-release.ps1 -Version 1.1.4
```

Outputs:

```text
release/MyNotes-AI-v1.1.4-windows-x64.msi
release/MyNotes-AI-v1.1.4-windows-x64.sha256
```

