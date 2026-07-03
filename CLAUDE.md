# CLAUDE.md - MyNotes AI

## Positioning

MyNotes AI is a `v1.1.4` AI application portfolio project. It combines calendar planning, AI goal decomposition, daily review, RAG material Q&A, planner evaluation, and Windows desktop packaging.

It should be treated as a real AI full-stack product, not a static page.

## Stack

- `apps/web`: React 18 + TypeScript + Vite
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

- `apps/web/src/App.tsx`: main React composition
- `apps/web/src/components/AIWorkspace.tsx`: AI settings, goal planning, daily review, RAG material flow
- `apps/web/src/components/CalendarPanel.tsx`: calendar and month note UI
- `apps/web/src/components/PlanList.tsx`: daily task UI
- `apps/web/src/lib/api.ts`: API and Tauri IPC proxy client
- `apps/web/src/lib/i18n.ts`: Chinese/English UI text
- `apps/desktop/src-tauri/src/main.rs`: Tauri startup, sidecar lifecycle, health preflight, IPC proxy
- `backend/app/main.py`: FastAPI app and CORS
- `backend/app/schemas.py`: API contracts
- `backend/app/db.py`: SQLite schema
- `backend/app/services/llm.py`: OpenAI-compatible LLM client
- `backend/app/services/rag.py`: FTS5/BM25 RAG service
- `backend/app/services/planning.py`: goal plan, review, and replan apply logic

## Verify

Backend:

```powershell
python -m compileall backend
.\.venv\Scripts\python.exe -m pytest backend\tests
```

Frontend:

```powershell
cd apps\web
npm.cmd run lint
npx.cmd tsc -b
npm.cmd run test
npm.cmd run build
```

Desktop:

```powershell
.\scripts\check-desktop-config.ps1
.\scripts\check-packaging-toolchain.ps1
cd apps\desktop
cargo fmt
cargo check
npm.cmd run build
```

Release:

```powershell
.\scripts\build-release.ps1 -Version 1.1.4
.\scripts\smoke-test-installed.ps1
```

Note: in restricted sandbox environments, Vite/esbuild may fail to read `vite.config.ts` even when TypeScript and lint pass. Report that as an environment limitation, not as a code failure.

## AI And API Key Safety

- Default model: `deepseek-v4-flash`.
- Recommended DeepSeek base URL: `https://api.deepseek.com`.
- DeepSeek chat endpoint must resolve to `/chat/completions`, not `/v1/chat/completions`.
- `GET /api/ai/settings` returns `hasApiKey`, never the full key.
- Do not commit real keys, `.env`, logs, DB files, MSI temp output, or caches.
- Real DeepSeek testing belongs in `scripts/test-deepseek-real.ps1` and requires explicit local env vars.
- Unit tests and CI must remain mock/stable.

## Desktop Rules

- Bundled frontend resource: `apps/desktop/src-tauri/resources/index.html`.
- Bundled sidecar resource: `apps/desktop/src-tauri/resources/binaries/mynotes-api.exe`.
- Tauri preflights `http://127.0.0.1:8000/api/health`.
- A valid health response includes `status`, `app`, `pid`, and `version`.
- If MyNotes API is already running, skip spawning a new sidecar.
- If another app owns port `8000`, show/log a clear conflict.
- Only kill the sidecar process spawned by the current Tauri process.

## Documentation Maintenance

Always update `README.md`, `AGENTS.md`, and `CLAUDE.md` when changing:

- versions, release names, or phase status
- setup/build/test/release commands
- API endpoints or schema fields
- AI provider defaults, key handling, or env vars
- desktop sidecar behavior, resource paths, or packaging scripts
- database schema or storage paths
- screenshots, project pitch, or resume value

If none of these changed, mention that no documentation update was needed.

## Collaboration Rules

- Answer the user in Chinese.
- Keep implementation practical and portfolio-oriented.
- Prefer small focused changes and real verification.
- Do not create a GitHub Release unless explicitly asked.
