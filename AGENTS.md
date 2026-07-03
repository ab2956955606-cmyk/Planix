# AGENTS.md - Planix

## Project Identity

Planix is a portfolio-grade AI planning application for learning, job search, and long-term execution. It combines a RIVA-style AI OS frontend shell, calendar planning, goal decomposition, daily review, local RAG material Q&A, deterministic planner evaluation, and Windows desktop packaging.

The project is now fully renamed to Planix. Do not reintroduce former product, storage, sidecar, or environment-variable names.

Current baseline: `1.1.4`.

## Architecture

- Frontend: React 18 + TypeScript + Vite in `apps/web`.
- Frontend shell: hash-route Planix RIVA AI OS Shell in `apps/web/src/shell`.
- Frontend pages: `apps/web/src/pages`.
- i18n: `apps/web/src/i18n`, default `zh-CN`, supports `en-US`.
- Desktop shell: Tauri v2 in `apps/desktop`.
- Backend: FastAPI in `backend/app`.
- Database: SQLite with FTS5/BM25 for local RAG.
- AI: DeepSeek-first OpenAI-compatible LLM client with mock fallback.
- Desktop runtime: Tauri window loads bundled web resources and starts the PyInstaller sidecar `planix-api.exe`.
- Desktop API access: frontend routes desktop API calls through Tauri IPC command `proxy_api`.

## Entry Points

- Web entry: `apps/web/index.html`
- Web app: `apps/web/src/App.tsx`
- Web API layer: `apps/web/src/lib/api.ts`
- Shell: `apps/web/src/shell/RivaShell.tsx`
- Route hook: `apps/web/src/shell/useAppRoute.ts`
- i18n entry: `apps/web/src/i18n/index.ts`
- Desktop Rust entry: `apps/desktop/src-tauri/src/main.rs`
- Backend app: `backend/app/main.py`
- Backend schemas: `backend/app/schemas.py`
- SQLite setup: `backend/app/db.py`
- Backend tests: `backend/tests`
- Packaging scripts: `scripts`

## Naming Rules

- Product name: `Planix`
- Backend health app: `planix-api`
- Sidecar executable: `planix-api.exe`
- Desktop executable: `planix.exe`
- MSI artifact: `Planix-v1.1.4-windows-x64.msi`
- Environment namespace: `PLANIX_*`
- Desktop database: `%APPDATA%\Planix\planix.db`
- Development database: `data/planix.db`
- Frontend localStorage prefix: `planix_*`

There is no compatibility fallback for old names or old environment variables.

## Frontend Rules

- Do not introduce `react-router`; use the existing hash-route model.
- `AppRoute` must remain the single source of truth for active pages.
- `AppMenu` may store only UI expansion state, never active route state.
- All static frontend UI text must go through `t("namespace.key")`.
- Do not translate user input, AI output, or existing database content.
- Keep Agent UI scaffolding UI-only unless a later phase adds runtime.
- Do not render Agent trace, timeline, reasoning, or execution chain in this phase.
- Keep Calendar, Notes, Goals, and Settings functionality available through the menu.

## Backend Rules

- Do not change business API payloads, response schemas, or SQLite tables for frontend-only UI work.
- Keep AI features demoable without an API key.
- Never expose full API keys in read endpoints, logs, screenshots, or docs.
- Preserve mock fallback and source-grounded RAG behavior.

## Commands

Frontend:

```powershell
cd apps\web
npm install
npx.cmd tsc -b
npm.cmd run lint
npm.cmd run test
npm.cmd run build
```

Backend:

```powershell
python -m compileall backend
.\.venv\Scripts\python.exe -m pytest backend\tests
```

Desktop packaging:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check-packaging-toolchain.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\build-release.ps1 -Version 1.1.4
```

## Documentation Maintenance

Update `README.md`, `AGENTS.md`, and `CLAUDE.md` whenever architecture, version, routes, UI shell, API behavior, database behavior, environment variables, AI strategy, packaging, release artifacts, screenshots, or portfolio positioning changes.
