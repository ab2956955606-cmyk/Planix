# AGENTS.md - Planix

## Project Identity

Planix is a portfolio-grade AI planning application for learning, job search, and long-term execution. It combines a RIVA-style AI OS frontend shell, calendar planning, structured goal decomposition, daily review, grounded local RAG, deterministic planner evaluation, a real Agent Runtime event stream, and Windows desktop packaging.

The project is fully renamed to Planix. Do not reintroduce former product, storage, sidecar, or environment-variable names.

Current baseline: `1.1.4`.

## Current Phase

Phase 3.5 is **Planning Intelligence + Grounded RAG**.

Allowed in this phase:

- Retrieve local materials with SQLite FTS5/BM25.
- Generate and validate `structuredPlan`.
- Save generated planning results to `planning_goals` as history/cache.
- Show structured previews in Goals and Runtime Trace.
- Render Runtime final output from the same `structuredPlan`.
- Clean Runtime Context Pack history before retrieval and planning.
- Provide Settings maintenance controls for AI memory/cache cleanup.

Forbidden in this phase:

- Auto-writing generated tasks to Calendar, Goals, Notes, or `plans`.
- Adding Approval / WriteIntent.
- Changing `/api/runtime/run` event protocol.
- Changing Tauri/MSI sidecar mechanics.

## Architecture

- Frontend: React 18 + TypeScript + Vite in `apps/web`.
- Frontend shell: hash-route Planix RIVA AI OS Shell in `apps/web/src/shell`.
- Frontend pages: `apps/web/src/pages`.
- i18n: `apps/web/src/i18n`, default `zh-CN`, supports `en-US`.
- Agent observability: `apps/web/src/components/agent/flow` renders Runtime events as the Dashboard trace.
- Agent flow state: `apps/web/src/store/agentFlowStore.ts`.
- Desktop shell: Tauri v2 in `apps/desktop`.
- Backend: FastAPI in `backend/app`.
- Database: SQLite with FTS5/BM25 for local RAG.
- AI: DeepSeek-first OpenAI-compatible LLM client with local structured fallback.
- Planning: `StructuredGoalPlan` is the source of truth for AI-generated plans.
- Runtime: `/api/runtime/run` returns NDJSON events from Planner, Memory, Tool Router, Stream Engine, and Runtime Orchestrator.
- Desktop runtime: Tauri window loads bundled web resources and starts the PyInstaller sidecar `planix-api.exe`.
- Desktop API access: normal JSON calls use Tauri IPC `proxy_api`; Runtime streaming uses `stream_agent_runtime`.

## Entry Points

- Web entry: `apps/web/index.html`
- Web app: `apps/web/src/App.tsx`
- Web API layer: `apps/web/src/lib/api.ts`
- Agent Trace: `apps/web/src/components/agent/flow/AgentFlowTrace.tsx`
- Agent Runtime store: `apps/web/src/store/agentFlowStore.ts`
- Shell: `apps/web/src/shell/RivaShell.tsx`
- Route hook: `apps/web/src/shell/useAppRoute.ts`
- i18n entry: `apps/web/src/i18n/index.ts`
- Desktop Rust entry: `apps/desktop/src-tauri/src/main.rs`
- Backend app: `backend/app/main.py`
- Backend schemas: `backend/app/schemas.py`
- Structured planning helper: `backend/app/services/structured_goal_plan.py`
- Runtime route: `backend/app/routers/runtime.py`
- Runtime service: `backend/app/services/runtime.py`
- Settings maintenance route: `backend/app/routers/maintenance.py`
- Settings maintenance service: `backend/app/services/maintenance.py`
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
- Dashboard Agent Trace consumes Runtime events first and falls back to local demo flow only when Runtime is unavailable.
- Runtime fallback must clearly show `当前使用本地规划模板生成，后端 Runtime 未连接` in the user-visible flow.
- Runtime success and fallback must not display old `plan_context_lookup`, `ui-mock`, or static UI mock wording.
- Runtime output should answer the user's prompt directly; for a Python learning prompt, return a concrete Python learning plan summary.
- Goals should display `structuredPlan` when present while keeping legacy task apply flows based on `tasks`.
- Goals calendar writes must show immediate writing feedback, a visible pressed/writing button state, and final created/updated/failed counts.
- Dashboard Runtime proposals may be written to Calendar only after the user clicks `写入日历`; valid `llm` and `local_fallback` structuredPlan outputs are both writable, and Runtime execution itself must not auto-write Calendar data.
- Calendar full-plan clearing should prefer `DELETE /api/plans/all`; if an older backend returns 404, the frontend may fall back to deleting known plans one by one and must keep any failed deletions visible.
- Settings model input is free text. The only built-in recommendations are `deepseek-v4-flash` and `deepseek-v4-pro`; do not restore legacy model display names.
- Keep Agent Trace visually secondary to the Workspace; it must not replace the prompt input or dominate the Dashboard.
- Internal `reasoning` nodes must display as `Plan` / `执行计划`; do not expose hidden chain-of-thought.
- Keep Calendar, Notes, Goals, and Settings functionality available through the menu.

## Backend Rules

- Keep AI features demoable without an API key.
- A saved key enables live model calls automatically unless the provider is `mock`.
- Never expose full API keys in read endpoints, logs, screenshots, or docs.
- Preserve source-grounded RAG behavior.
- LLM-generated planning output must be parsed, schema-validated, and completed with fallback defaults.
- Goal planning asks the model only for `summary + structuredPlan`; legacy `phases` and `tasks` are derived from `structuredPlan`.
- `PLANIX_GOAL_PLAN_MAX_TOKENS` controls Goals planning output budget. Default is `4096`; values above `8000` must clamp to `8000`.
- OpenAI-compatible `finish_reason="length"` must map to `errorType="model_output_truncated"` rather than generic invalid JSON.
- `GoalPlanOut` must keep `summary`, `phases`, `tasks`, and `sources` while adding `structuredPlan`.
- Planning fallback must be transparent with safe diagnostics: `fallbackReason`, `errorType`, and host-only `baseUrlHost`.
- `planning_goals` is planning result history/cache, not a confirmed execution table.
- Runtime tools are restricted to read-only or preview-only behavior in this phase.
- Runtime must build one internal Context Pack containing goal, explicit constraints, preference memory, history memory, today plans, materials, and output language.
- Preference memory is separate from history memory and has higher planning priority.
- `payload.preferences` must merge field-by-field with saved preferences; never overwrite the whole preference object when only one field is provided.
- Runtime must clean history before retrieval and planning. Expose `historyMemory.recentProgress` as short `{ title, summary, relevanceToGoal }` objects; do not pass full Markdown, full historical output, or full `structuredPlan` blobs to `search_materials` or Planning prompts.
- `search_materials.input.query` must stay short and goal-focused. For a swimming goal, it should contain swimming terms and preferences, not Python/AI internship/skiing long-form history.
- `memoryContextSummary` must be deterministic, short, and safe for display.
- `search_materials`, `get_today_plans`, and `get_memory` are read-only.
- `get_memory` returns `preferenceMemory` and `historyMemory`; do not add a separate `get_preferences` tool.
- `propose_tasks` may return structured task previews with `memoryContextSummary` but must not write to `plans`, Goals, Calendar, or Notes.
- `structuredPlan` is the fact source; Runtime final output should be rendered from it.
- `RuntimeOrchestrator` is the only component that coordinates Planner, Memory, Tool Router, and Stream Engine.
- Rust/Tauri streaming bridge must stay a thin pass-through; do not put Runtime state or business logic in Rust.
- Settings maintenance endpoints under `/api/settings/*` may clear AI memory/cache only. They must not delete formal `plans`, Calendar data, Notes/materials, documents, or AI settings.
- `DELETE /api/settings/memory/history` clears only Runtime summary memory (`agent_runs.output_summary`), while `DELETE /api/settings/runtime/runs` deletes `agent_events` and `agent_runs`.
- `DELETE /api/settings/planning/history` clears `planning_goals` only, which is planning history/cache.

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

Latest local MSI generation record: `release\Planix-v1.1.4-windows-x64.msi` was regenerated on 2026-07-04 with SHA256 `f0bfdfd0a5e7a3c8cba444c8ce7b8e57f22358192ed3096b42638a2255394766`. Release binaries remain ignored by Git and should be attached through release tooling rather than committed.

## Documentation Maintenance

Every completed implementation must update `README.md`, `AGENTS.md`, and `CLAUDE.md` before final reporting. Include relevant behavior, API/database changes, phase boundaries, and verification notes; do not record secrets, local API keys, or machine-specific credentials.

Update these three files whenever architecture, version, routes, UI shell, API behavior, database behavior, environment variables, AI strategy, packaging, release artifacts, screenshots, or portfolio positioning changes.

Current Calendar behavior includes a `Note` area on the Calendar panel, selected-day plan clearing, and full calendar plan clearing. Clearing plans deletes Calendar `plans` and their task refinements only; it must not delete notes/materials, Goals planning history, AI settings, documents, or API keys.
