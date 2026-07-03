# Planix v1.1.2

This release fixes the installed MSI startup path for the FastAPI sidecar.

## Highlights

- Fixed desktop startup to launch the installed `resources/binaries/planix-api.exe`.
- Kept Tauri `externalBin` packaging unchanged while matching the runtime path used by the installed MSI.
- Updated desktop logs to report the correct sidecar path candidate.
- Improved the installed-app smoke test so developers can pass a custom install directory such as `H:\planix`.

## Assets

- `Planix-v1.1.2-windows-x64.msi`
- `Planix-v1.1.2-windows-x64.sha256`

## Notes

If v1.1.1 logs show `sidecar start failure: 绯荤粺鎵句笉鍒版寚瀹氱殑璺緞銆?(os error 3)`, install this version instead.
