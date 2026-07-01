# MyNotes AI Desktop

This folder is the Phase 7 desktop shell scaffold.

It is intentionally not a completed installer build. The current environment is expected to miss Rust/Cargo, Tauri CLI, and PyInstaller, so Phase 7 only prepares the project structure that Phase 8 can build from.

## Development

```powershell
.\scripts\dev-desktop.ps1
cd apps\desktop
npm install
npm run dev
```

The desktop dev window loads:

```text
http://127.0.0.1:5173/MyNotes.html
```

## Release Strategy

1. `scripts/build-web.ps1` builds `apps/web/dist`.
2. `scripts/build-backend.ps1` packages the FastAPI backend as `mynotes-api`.
3. Tauri bundles the web dist and launches the backend through the `mynotes-api` sidecar.
4. The sidecar receives `MYNOTES_ENV=desktop` and stores SQLite data in the user data directory unless `MYNOTES_DB_PATH` is set.
