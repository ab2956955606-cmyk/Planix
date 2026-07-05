# Planix v1.1.4

This is a historical release note. The current portfolio documentation presents Planix as `v3.0.0`.

This release focuses on desktop runtime stability and safe DeepSeek settings.

## Highlights

- Fixed the installed MSI resource lookup for `resources/index.html` and `resources/binaries/planix-api.exe`.
- Added Planix API health identification with `status`, `app`, `pid`, and `version`.
- Added desktop preflight detection so repeated launches reuse an existing Planix API instead of starting a second sidecar on port `8000`.
- Improved desktop logs under `%APPDATA%\Planix\logs\desktop.log`, including resource paths, health responses, sidecar output, and port conflict hints.
- Standardized DeepSeek defaults to `https://api.deepseek.com` and `deepseek-v4-flash`.
- Kept real LLM calls disabled unless `USE_REAL_LLM=1` is explicitly set.
- Improved AI settings save/test errors without exposing API keys.
- Treated empty LLM message content as an error and raised token budgets for DeepSeek v4/reasoning-style smoke tests and planning calls.
- Ensured closing the Tauri window terminates the spawned `planix-api` Windows process tree.

## Assets

- `Planix-v1.1.4-windows-x64-setup.exe`
- `Planix-v1.1.4-windows-x64-setup.exe.sha256`
- `Planix-v1.1.4-windows-x64.msi`
- `Planix-v1.1.4-windows-x64.msi.sha256`

## Notes

Normal users should download the Setup.exe installer. The MSI remains available as a backup or enterprise installer. `.sha256` files are checksums, not installers. No GitHub Release is created by the build script unless `-CreateGitHubRelease` is explicitly passed. API keys are never committed, printed, or returned by public settings endpoints.
