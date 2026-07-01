# MyNotes AI v1.1.1

This release focuses on making the Windows MSI installable and usable for normal users without a developer toolchain.

## Highlights

- Fixed the desktop entry path so the packaged app loads `index.html` from the bundled frontend assets.
- Added strict release build checks for `apps/web/dist/index.html` and the Tauri sidecar executable.
- Added desktop startup logging to `%APPDATA%\MyNotes AI\logs\desktop.log`.
- Added Chinese user-facing error dialogs for frontend asset or sidecar startup failures.
- Added sidecar health polling against `http://127.0.0.1:8000/api/health`.
- Added WebView2 bootstrapper configuration for the Windows MSI.
- Added an installed-app smoke test script for developer acceptance.

## Assets

- `MyNotes-AI-v1.1.1-windows-x64.msi`
- `MyNotes-AI-v1.1.1-windows-x64.sha256`

## Notes

Normal users should download the MSI installer only. Do not use Source code.zip as the installer, and do not run `mynotes-api.exe` manually.
