# AGENTS.md - MyNotes AI

## Project Identity

MyNotes AI is a portfolio-grade AI learning planner, daily review system, local knowledge base, and Windows desktop app. It is built to demonstrate practical AI application engineering for internship applications: full-stack product flow, local-first storage, LLM integration, RAG, evaluation, and desktop packaging.

Current version baseline: `1.1.4`.

## Current Architecture

- Frontend: React 18 + TypeScript + Vite in `apps/web`.
- Desktop shell: Tauri v2 in `apps/desktop`.
- Backend: FastAPI in `backend/app`.
- Database: SQLite, including FTS5/BM25 for local RAG.
- AI: DeepSeek-first OpenAI-compatible LLM client with mock fallback.
- Desktop runtime: Tauri window loads bundled web resources and starts a PyInstaller FastAPI sidecar.
- Desktop API access: the frontend routes API calls through the Tauri IPC command `proxy_api` to avoid WebView2 mixed-content blocking.
- Release artifact: Windows MSI, currently `release/MyNotes-AI-v1.1.4-windows-x64.msi`.

## Important Entry Points

- Web entry: `apps/web/index.html`
- Web app: `apps/web/src/App.tsx`
- Web API layer: `apps/web/src/lib/api.ts`
- Desktop Rust entry: `apps/desktop/src-tauri/src/main.rs`
- Desktop config: `apps/desktop/src-tauri/tauri.conf.json`
- Backend app: `backend/app/main.py`
- Backend schemas: `backend/app/schemas.py`
- SQLite setup: `backend/app/db.py`
- SQLite desktop path logic: `backend/app/desktop_paths.py`
- API routers: `backend/app/routers`
- Business services: `backend/app/services`
- Backend tests: `backend/tests`
- Packaging scripts: `scripts`
- Desktop packaging guide: `docs/desktop.md`

## Core User Flows

- Calendar planning: create, edit, complete, and delete daily tasks.
- Month notes: save monthly notes locally and through the backend.
- Goal planning: generate phases and today tasks from a long-term goal.
- Daily review: summarize completed/unfinished tasks and preview replanning.
- Daily review lookup: missing dates return an empty `mode='saved'` state, not HTTP 404.
- Replan apply: AI suggestions are previews until the user confirms.
- Knowledge base: paste or upload TXT/MD material into SQLite-backed RAG.
- RAG query: retrieve FTS5/BM25-ranked chunks with citations.
- Planner evaluation: deterministic six-dimension scoring without LLM calls.
- AI settings: save provider, base URL, model, key, temperature, and timeout safely. Blank API key input must clear the stored key instead of preserving stale cache.
- Desktop MSI: normal users run `mynotes.exe`; they do not manually run `mynotes-api.exe`.

## Commands

Backend:

```powershell
python -m compileall backend
.\.venv\Scripts\python.exe -m pytest backend\tests
uvicorn backend.app.main:app --reload
```

Web:

```powershell
cd apps\web
npm.cmd install
npm.cmd run lint
npx.cmd tsc -b
npm.cmd run test
npm.cmd run build
```

Desktop:

```powershell
.\scripts\check-packaging-toolchain.ps1
.\scripts\build-web.ps1
.\scripts\build-backend.ps1
cd apps\desktop
npm.cmd install
cargo fmt
cargo check
npm.cmd run build
```

Release:

```powershell
.\scripts\build-release.ps1 -Version 1.1.4
.\scripts\smoke-test-installed.ps1
.\scripts\verify-msi-user-path.ps1 -InstalledDir "H:\mynotes"
```

Manual real DeepSeek test, only when explicitly intended:

```powershell
$env:DEEPSEEK_API_KEY="your-key"
$env:USE_REAL_LLM="1"
.\scripts\test-deepseek-real.ps1
```

## Security Rules

- Never commit `.env`, real API keys, database files, logs, build caches, `node_modules`, `.venv`, or generated temporary artifacts.
- `GET /api/ai/settings` must never return a full API key.
- `hasApiKey` must come from a real user-saved key or an explicit environment key before local settings exist; legacy cached keys must not count as configured.
- Existing local AI settings rows with blank or legacy keys must not fall back to environment variables.
- Saving AI settings with a blank key intentionally clears the stored key.
- Logs may record provider, model, sanitized base URL, key presence, and masked key only.
- Do not print `Authorization` headers or full key values.
- Real LLM calls must never run in CI, unit tests, loops, or broad smoke tests.
- DeepSeek v4/reasoning-style models need a practical token budget; connection tests and planning calls should not use tiny `max_tokens` values.
- Empty LLM message content is a failure state, not a successful AI response. Fall back or report a clear error instead of showing a fake success.
- Keep mock fallback demoable without paid credentials.

## Desktop Runtime Rules

- Production frontend resources live under `apps/desktop/src-tauri/resources`.
- Desktop API calls must go through `proxy_api`; direct browser fetch is only for Vite dev mode.
- TXT/MD upload in desktop mode reads local text in the frontend and writes it through the JSON RAG API so WebView2 never has to fetch `http://127.0.0.1:8000` directly.
- Installed layout is expected to include:

```text
mynotes.exe
resources/
  index.html
  assets/
  binaries/
    mynotes-api.exe
```

- Tauri must check `/api/health` before starting the sidecar.
- If a MyNotes API is already running, reuse it and do not kill it on exit.
- If port `8000` is used by a non-MyNotes process, show a clear local error and log the conflict.
- When Tauri spawns the sidecar itself, closing or destroying the window must terminate the spawned `mynotes-api` process tree so no parent/child sidecar process remains.
- Desktop logs belong under `%APPDATA%\MyNotes AI\logs\desktop.log`.
- Desktop SQLite data belongs under `%APPDATA%\MyNotes AI\mynotes.db` unless `MYNOTES_DB_PATH` overrides it.

## Code Conventions

- Keep frontend features inside `apps/web/src/components`, `apps/web/src/lib`, `apps/web/src/utils`, or `apps/web/src/types.ts`.
- Do not restore the old root-level HTML/CSS/JS application.
- Keep API schemas in `backend/app/schemas.py`.
- Keep routers in `backend/app/routers`.
- Keep business logic in `backend/app/services`.
- Prefer typed request/response contracts over ad hoc JSON shapes.
- Keep changes focused; do not mix UI redesign, backend API changes, and packaging changes unless the task requires it.
- Preserve localStorage fallback for frontend-only demos.
- Preserve deterministic mock behavior for AI features.

## Documentation Auto-Update Rule

Whenever a change affects any of the following, update `AGENTS.md`, `CLAUDE.md`, and `README.md` in the same commit:

- version number or release artifact name
- project phase/status
- startup, build, test, or packaging commands
- frontend/backend/desktop architecture
- public API endpoints or request/response fields
- AI provider behavior, model defaults, key handling, or environment variables
- database tables or storage paths
- screenshots, demo flow, or resume positioning
- known limitations or manual acceptance steps

If a code change does not require doc updates, say that explicitly in the final report.

## User Preference

- Reply in Chinese.
- Prefer practical, clean, portfolio-quality engineering.
- Verify before reporting completion.
- Do not create GitHub Releases or upload Release Assets unless explicitly requested.
