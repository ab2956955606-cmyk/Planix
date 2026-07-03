# CLAUDE.md - Planix

## Positioning

Planix is a `v1.1.4` AI application portfolio project. It presents a RIVA-style AI OS Shell on the frontend and keeps the existing planning, review, RAG, evaluation, and desktop packaging capabilities behind a clean menu-based workspace.

Planix is a frontend display brand. Do not rename backend service names, API contracts, database paths, localStorage keys, sidecar names, MSI artifact names, or Tauri identifiers unless a future phase explicitly requires it.

## Stack

- `apps/web`: React 18 + TypeScript + Vite
- `apps/web/src/shell`: Planix RIVA Shell, App Menu, Inspector, hash route
- `apps/web/src/pages`: Dashboard, Calendar, Notes, Goals, Settings
- `apps/web/src/i18n`: `zh-CN` / `en-US` text system
- `apps/desktop`: Tauri v2 desktop shell
- `backend/app`: FastAPI backend
- SQLite: plans, month notes, planning goals, daily reviews, AI settings, local RAG documents, chunks, FTS5 index, AI run logs
- AI client: DeepSeek-first OpenAI-compatible client
- RAG: SQLite FTS5/BM25, not Chroma/FAISS
- Sidecar: FastAPI packaged with PyInstaller as `mynotes-api.exe`

## Runtime Shape

Development:

```text
Vite dev server -> FastAPI at 127.0.0.1:8000 -> SQLite
```

Desktop:

```text
Tauri window -> bundled resources/index.html -> proxy_api IPC -> 127.0.0.1:8000 -> FastAPI sidecar -> SQLite user data dir
```

The frontend uses Tauri IPC for desktop API calls so WebView2 does not block local HTTP requests as mixed content.

## Main Files

- `apps/web/src/App.tsx`: global state, route switch, business callbacks
- `apps/web/src/shell/useAppRoute.ts`: hash route source of truth
- `apps/web/src/shell/RivaShell.tsx`: main shell composition
- `apps/web/src/shell/AppMenu.tsx`: collapsible top-left menu and language switch
- `apps/web/src/shell/InspectorPanel.tsx`: read-only Inspector snapshot UI
- `apps/web/src/pages/DashboardPage.tsx`: UI-only Agent workspace scaffold
- `apps/web/src/components/AIWorkspace.tsx`: Notes, Goals, and Settings feature sections
- `apps/web/src/components/CalendarPanel.tsx`: calendar and month note UI
- `apps/web/src/components/PlanList.tsx`: daily task UI
- `apps/web/src/lib/api.ts`: API and Tauri IPC proxy client
- `apps/desktop/src-tauri/src/main.rs`: Tauri startup, sidecar lifecycle, health preflight, IPC proxy
- `backend/app/main.py`: FastAPI app and CORS
- `backend/app/schemas.py`: API contracts

## Frontend Constraints

- Do not add `react-router`; keep lightweight hash routing.
- `AppRoute` is the only active-page state.
- Language is `zh-CN | en-US`, persisted with the existing `my_notes_lang` key.
- All static UI text should use `t("namespace.key")`.
- Keep Agent UI as a shell-level scaffold only.
- Do not show trace, timeline, reasoning, or execution chain UI in the current phase.
- Do not change existing request payloads or response schemas.

## Verification Commands

```powershell
cd apps\web
npx.cmd tsc -b
npm.cmd run lint
npm.cmd run test
npm.cmd run build
```

```powershell
python -m compileall backend
.\.venv\Scripts\python.exe -m pytest backend\tests
```

## Documentation Maintenance

`README.md`, `AGENTS.md`, and `CLAUDE.md` must be kept current whenever the project changes meaningfully. This includes phase status, frontend shell, i18n, API behavior, database behavior, AI strategy, packaging, release artifacts, screenshots, and portfolio positioning.
