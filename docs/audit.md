# MyNotes AI Desktop - Phase 0 Repository Audit

Date: 2026-06-30

## 0. Document Requirement Summary

The product target from `MyNotes AI Desktop Project (1).docx` is **MyNotes AI Desktop**: a Windows desktop AI learning planner that can be installed as `MyNotes-AI-Desktop-Setup-x64.exe` and used without Node.js, Python, SQLite, npm, pip, or command-line steps.

The final target stack is:

- Frontend: React + TypeScript + Vite
- Desktop: Tauri
- Backend: FastAPI
- Database: SQLite in the user data directory
- AI Provider: DeepSeek first, OpenAI-compatible fallback
- RAG: SQLite FTS5 / BM25 with answer sources
- Packaging: PyInstaller backend sidecar + Tauri installer
- Release: GitHub Actions Windows release workflow

The document explicitly requires a staged migration. **Current phase is only Phase 0: audit the real repository and plan migration. No large rewrite should happen in this phase.**

## 1. Current Repository State

Current Git state observed:

```text
branch: main
tracking: origin/main
status: clean before this audit file
head: e558958
```

Current root-level structure:

```text
MyNotes/
├── index.html
├── package.json
├── package-lock.json
├── vite.config.ts
├── tsconfig.json
├── tsconfig.app.json
├── tsconfig.node.json
├── eslint.config.js
├── requirements.txt
├── Dockerfile
├── README.md
├── AGENTS.md
├── CLAUDE.md
├── assets/
├── backend/
├── docs/
├── node_modules/
└── src/
```

Important observation: the repository is already in a partial React + FastAPI migration state. It is no longer the original pure HTML/CSS/JS project.

## 2. Current Technology Stack

### Frontend

- React 18
- TypeScript
- Vite
- lucide-react
- Custom CSS in `src/styles.css`
- Entry file: `index.html`

### Backend

- FastAPI
- Pydantic
- SQLite via Python `sqlite3`
- Simple service classes under `backend/app/services`

### AI / RAG

- Current AI behavior is mostly mock / rule-based.
- `backend/app/services/llm.py` has a basic OpenAI-compatible HTTP client using environment variables.
- No user-facing AI settings page exists.
- No DeepSeek-specific client exists.
- No SQLite FTS5 index exists.

### Packaging / Desktop

- No Tauri app exists.
- No `apps/desktop` exists.
- No PyInstaller config exists.
- No sidecar startup logic exists.
- No Windows installer output exists.

## 3. Current Directory Structure vs Target Structure

### Current

```text
src/
backend/
docs/
index.html
package.json
requirements.txt
```

### Target From Document

```text
apps/
  web/
  desktop/
backend/
  app/
    routers/
    services/
    models.py
    config.py
    errors.py
legacy/
scripts/
docs/
.github/workflows/
```

### Gap

- Current web app is at root `src/`, not `apps/web/src/`.
- No `apps/desktop` Tauri structure.
- No `legacy/` folder, although the document explicitly asks old code to be moved there instead of deleted.
- Backend is not split into routers.
- No `scripts/` build/release scripts.
- CI exists only as a basic build/compile workflow.

## 4. Current Features

Currently implemented in React:

- Calendar view
- Daily plan list
- Add plan
- Delete plan
- Toggle completion state
- Completion notes
- Month notes
- Chinese / English text dictionary
- localStorage persistence
- AI workspace panel with goal, deadline, daily hours, materials, preferences
- Mock AI plan/review/RAG/eval fallback

Currently implemented in FastAPI:

- `GET /api/health`
- `POST /api/agent/plan`
- `POST /api/agent/review`
- `GET /api/agent/tools`
- `POST /api/rag/ingest`
- `POST /api/rag/query`
- `POST /api/memory/preferences`
- `GET /api/memory/preferences`
- `POST /api/eval/planner`

## 5. Current Data Storage

### Frontend

Current primary user data is still stored in browser `localStorage`:

- `my_notes_data_v2`
- `my_notes_data` legacy migration fallback
- `my_notes_lang`
- `my_notes_preferences`
- `note_{year}_{month}`

### Backend

Current SQLite database path defaults to:

```text
data/mynotes.db
```

Current tables created by `backend/app/db.py`:

- `memories`
- `rag_chunks`
- `ai_events`

### Gap

The document requires SQLite as the main data store in the Windows user data directory, for example:

```text
C:\Users\<user>\AppData\Roaming\MyNotes AI\mynotes.db
```

Required tables that are missing:

- `plans`
- `month_notes`
- `daily_reviews`
- `ai_settings`
- `user_preferences`
- `documents`
- `document_chunks`
- `ai_runs`

The current backend database does not yet support the required offline desktop data model.

## 6. README Accuracy

Current README is partially accurate for the current web/FastAPI prototype:

- It correctly says the entry is `index.html`.
- It correctly says the full React app must run through Vite.
- It correctly lists the current AI prototype APIs.

But it is not yet accurate for the final document target:

- It does not describe Tauri desktop packaging as implemented, because Tauri is not implemented.
- It does not describe PyInstaller sidecar as implemented, because sidecar packaging is not implemented.
- It does not document Windows installer usage, because no installer exists.
- It describes RAG generally, but the current RAG is keyword overlap over stored chunks, not SQLite FTS5/BM25.
- It does not document DeepSeek settings behavior, because the AI settings page and DeepSeek client are missing.

Conclusion: README is acceptable as a prototype README, but not yet a final desktop release README.

## 7. Verification Results

Commands attempted during audit:

```bash
python -m compileall backend
```

Result:

```text
Passed Python syntax compilation.
```

Backend import check:

```text
ModuleNotFoundError: No module named 'fastapi'
```

Meaning: backend dependencies are not installed in the active Python environment, so runtime import was not verified.

Frontend checks:

```bash
tsc -b
vitest run
vite build
```

Observed issues:

```text
tsc: Cannot find name 'Worker' from Vite importGlob types.
vitest/vite: esbuild could not read config path due sandbox access restrictions.
```

Meaning:

- TypeScript config likely needs DOM worker libraries or adjusted Vite types.
- Vite/Vitest verification needs a normal local shell environment or fixed sandbox path access.
- CI may still pass on GitHub if environment is normal, but current local validation is not clean.

## 8. Main Technical Debt

1. **Architecture is halfway migrated.**  
   React + FastAPI exist, but not in the target `apps/web` + `apps/desktop` layout.

2. **Old backend services remain.**  
   `backend/app/services/agent.py` and `backend/app/services/llm.py` coexist with the newer `planner.py`. `agent.py` imports schema names that no longer exist in `schemas.py`, making it stale.

3. **Main data still lives in localStorage.**  
   The document requires SQLite as the main local-first store for desktop.

4. **No DeepSeek settings flow.**  
   There is no AI settings page, no persistent provider settings table, no API key management, and no user-facing connection test.

5. **No true DeepSeek client.**  
   Current `llm.py` is a minimal environment-variable client, not the required `deepseek_client.py` and `llm_client.py` design.

6. **RAG is not yet SQLite FTS5/BM25.**  
   Current RAG uses simple token overlap and does not return the required typed sources with document IDs, chunk indexes and scores.

7. **Backend API does not match required API contract.**  
   Required `/api/plans`, `/api/month-notes`, `/api/reviews`, `/api/settings/ai`, `/api/documents`, `/api/rag/query` contract is mostly missing.

8. **No router separation.**  
   All current API endpoints live in `backend/app/main.py`.

9. **No backend tests.**  
   No `backend/tests` or pytest coverage exists.

10. **No Tauri desktop app.**  
    No `src-tauri`, no desktop window, no sidecar process management.

11. **No PyInstaller sidecar.**  
    No `mynotes-api.exe`, no build scripts, no port strategy.

12. **No release workflow.**  
    CI exists, but no tag-based Windows release workflow uploads an installer.

13. **Legacy code was deleted instead of preserved.**  
    Document requires old version to be moved into `legacy/`. Current repo has no `legacy/`.

## 9. Rebuild Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Moving root `src/` into `apps/web` may break Vite paths | Frontend cannot run | Move with one commit and update package scripts immediately |
| Switching from localStorage to SQLite may lose user data | Existing browser users lose plans | Keep localStorage import/migration utility |
| DeepSeek key storage is sensitive | Key leakage risk | Store only locally, never log, document temporary plaintext risk, later migrate to Tauri Stronghold/system store |
| Introducing Tauri too early may block web development | Slows feature work | Keep web mode working before desktop mode |
| PyInstaller packaging can hide path bugs | Desktop app starts but API fails | Add `desktop_paths.py`, `/health` polling and smoke tests |
| RAG with FTS5 can fail if SQLite build lacks FTS5 | Query failure | Add startup check and fallback diagnostic |
| Current duplicate backend services can confuse future work | Wrong module gets edited | Remove stale `agent.py`/`llm.py` when Phase 2 starts |

## 10. Recommended Migration Route

### Phase 1: Modern Frontend Layout

Goal: move current frontend into `apps/web` without changing product behavior.

Minimum changes:

- Create `apps/web`.
- Move `src/`, `index.html`, `package.json`, `vite.config.ts`, `tsconfig*`, `eslint.config.js` into `apps/web`.
- Update scripts and README paths.
- Add `legacy/` and preserve old project history or a snapshot note.
- Keep calendar, plans, completion records, month notes and AI workspace working.

Acceptance:

```bash
cd apps/web
npm install
npm run build
npm run test
npm run lint
```

### Phase 2: FastAPI + SQLite Main Store

Goal: make SQLite the main store for core planner data.

Minimum changes:

- Add `backend/app/routers`.
- Add `backend/app/models.py`, `config.py`, `desktop_paths.py`, `errors.py`.
- Add tables: `plans`, `month_notes`, `daily_reviews`, `ai_settings`, `user_preferences`, `documents`, `document_chunks`, `ai_runs`.
- Implement `/api/plans` and `/api/month-notes`.
- Add pytest for health, plans and month notes.

### Phase 3: DeepSeek Settings + LLM Client

Goal: implement DeepSeek-first AI settings and connection testing.

Minimum changes:

- Add `deepseek_client.py`, `llm_client.py`, `prompt_templates.py`.
- Add `/api/settings/ai`, `/api/settings/ai/test`, `/api/settings/ai/key`.
- Add frontend `AiSettingsPage`.
- Ensure no frontend direct DeepSeek requests.

### Phase 4: AI Goal Breakdown + Daily Review

Goal: structured AI plan generation and daily review.

Minimum changes:

- Add JSON schema validation for AI output.
- Add editable generated plan preview before import.
- Save daily review to SQLite.
- Use evaluator before importing tasks.

### Phase 5: Real SQLite FTS5 RAG

Goal: replace token overlap with true FTS5/BM25 retrieval.

Minimum changes:

- Add `documents` and `document_chunks` APIs.
- Create FTS5 virtual table.
- Return `answer + sources` with document ID, title, chunk index, snippet and score.

### Phase 6-8: Desktop and Release

Only after web + backend API are stable:

- Add `apps/desktop` Tauri app.
- Add PyInstaller backend sidecar.
- Add scripts for backend build, desktop build and full release.
- Add Windows GitHub Actions release workflow.

## 11. First Minimum Viable Change for Phase 1

Do not start with Tauri.

Recommended first change:

1. Create `legacy/README.md` explaining the old pure frontend version and localStorage keys.
2. Create `apps/web`.
3. Move current web files into `apps/web`.
4. Update Vite entry from root `index.html` to `apps/web/index.html`.
5. Fix TypeScript config issue around Vite `Worker` types.
6. Verify build/test/lint from `apps/web`.

This keeps the project runnable while moving toward the target structure.

## 12. Phase 0 Conclusion

The repository is a useful prototype, but it is not yet the document's required **MyNotes AI Desktop** product.

It currently demonstrates:

- React + TypeScript frontend direction
- Basic planner UI
- FastAPI prototype endpoints
- Mock AI workflow
- Early RAG/memory/eval vocabulary

It does not yet satisfy:

- Desktop `.exe` installer
- Tauri sidecar
- PyInstaller backend
- DeepSeek settings page
- DeepSeek-first LLM client
- SQLite as main planner database
- SQLite FTS5 RAG with sources
- Required API contract
- Backend pytest coverage
- Windows release workflow

The next correct step is **Phase 1: modern frontend layout**, not another feature sprint.
