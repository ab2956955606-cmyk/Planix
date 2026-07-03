# MyNotes AI v1.1.4

This release focuses on desktop runtime stability and safe DeepSeek settings.

## Highlights

- Fixed the installed MSI resource lookup for `resources/index.html` and `resources/binaries/mynotes-api.exe`.
- Added MyNotes API health identification with `status`, `app`, `pid`, and `version`.
- Added desktop preflight detection so repeated launches reuse an existing MyNotes API instead of starting a second sidecar on port `8000`.
- Improved desktop logs under `%APPDATA%\MyNotes AI\logs\desktop.log`, including resource paths, health responses, sidecar output, and port conflict hints.
- Standardized DeepSeek defaults to `https://api.deepseek.com` and `deepseek-v4-flash`.
- Kept real LLM calls disabled unless `USE_REAL_LLM=1` is explicitly set.
- Improved AI settings save/test errors without exposing API keys.
- Treated empty LLM message content as an error and raised token budgets for DeepSeek v4/reasoning-style smoke tests and planning calls.
- Ensured closing the Tauri window terminates the spawned `mynotes-api` Windows process tree.

## Assets

- `MyNotes-AI-v1.1.4-windows-x64.msi`
- `MyNotes-AI-v1.1.4-windows-x64.sha256`

## Notes

No GitHub Release is created by the build script unless `-CreateGitHubRelease` is explicitly passed. API keys are never committed, printed, or returned by public settings endpoints.
