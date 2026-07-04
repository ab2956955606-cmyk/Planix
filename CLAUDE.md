# CLAUDE.md - Planix

## Positioning

Planix is a `v1.1.4` AI application portfolio project. It presents a RIVA-style AI OS Shell on the frontend and connects the Dashboard Agent Trace to a real backend Runtime stream while keeping planning, review, RAG, evaluation, and desktop packaging capabilities behind a clean menu-based workspace.

The current focus is **Phase 3.5: Planning Intelligence + Grounded RAG**. The goal is to make Planix useful before the later Approval / WriteIntent phase: retrieve relevant materials, generate a strict structured plan, preview tasks, and render consistent output without automatically writing user data.

The project is fully named Planix across frontend, backend, desktop, sidecar, installer, database path, environment variables, and documentation.

## Documentation Maintenance

Every completed implementation must update `README.md`, `AGENTS.md`, and `CLAUDE.md` before final reporting. Record relevant behavior, API/database changes, phase boundaries, and verification notes, but never record secrets, local API keys, Authorization headers, or machine-specific credentials.

## Stack

- `apps/web`: React 18 + TypeScript + Vite
- `apps/web/src/shell`: Planix RIVA Shell, App Menu, Inspector, hash route
- `apps/web/src/pages`: Dashboard, Calendar, Notes, Goals, Settings
- `apps/web/src/components/agent/flow`: Agent Flow Trace observability UI
- `apps/web/src/store/agentFlowStore.ts`: Runtime event to Trace state mapping
- `apps/web/src/i18n`: `zh-CN` / `en-US` text system
- `apps/desktop`: Tauri v2 desktop shell
- `backend/app`: FastAPI backend
- SQLite: plans, month notes, planning goals, daily reviews, AI settings, local RAG documents, chunks, FTS5 index, AI run logs, agent runs, agent events
- AI client: DeepSeek-first OpenAI-compatible client with local structured fallback
- Planning: `StructuredGoalPlan` schema in `backend/app/schemas.py`, helper logic in `backend/app/services/structured_goal_plan.py`
- Runtime: `/api/runtime/run` streams NDJSON events from Planner, Memory, Tool Router, Stream Engine, and Runtime Orchestrator
- Maintenance: `/api/settings/ai-memory-cache/*` and related Settings maintenance endpoints clear AI memory/cache without touching formal user data
- RAG: SQLite FTS5/BM25, not Chroma/FAISS
- Sidecar: FastAPI packaged with PyInstaller as `planix-api.exe`

## Runtime Shape

Development:

```text
Vite dev server -> fetch NDJSON / JSON APIs -> FastAPI at 127.0.0.1:8000 -> SQLite
```

Desktop:

```text
Tauri window -> bundled resources/index.html -> proxy_api IPC for JSON APIs -> 127.0.0.1:8000 -> FastAPI sidecar -> SQLite user data dir
Tauri window -> stream_agent_runtime IPC for NDJSON Runtime -> FastAPI sidecar -> Runtime events -> Agent Trace
```

The frontend uses Tauri IPC for desktop API calls so WebView2 does not block local HTTP requests as mixed content. Runtime streaming uses a thin Rust pass-through bridge and keeps state in the frontend/backend only.

## Planning Contract

`GoalPlanOut` keeps legacy compatibility fields and adds `structuredPlan`.

`structuredPlan` fields:

- `goalTitle`
- `goalDescription`
- `durationDays`
- `milestones[].title`
- `milestones[].description`
- `milestones[].tasks[].title`
- `milestones[].tasks[].description`
- `milestones[].tasks[].estimatedMinutes`
- `milestones[].tasks[].dueDate`
- `milestones[].tasks[].priority`
- `reviewPlan.frequency`
- `reviewPlan.questions`

Rules:

- `priority` is only `low | medium | high`.
- `dueDate` is `string | null`.
- `estimatedMinutes` is a number.
- LLM output must be parsed, schema-validated, and repaired with local fallback defaults when incomplete.
- Goals planning prompts the model for `summary + structuredPlan` only. `phases` and `tasks` are derived by the backend for legacy compatibility.
- `PLANIX_GOAL_PLAN_MAX_TOKENS` controls the Goals planning token budget. It defaults to `4096` and clamps to `8000`.
- If an OpenAI-compatible response ends with `finish_reason="length"`, report `errorType="model_output_truncated"` and use the local structured fallback.
- A saved API key enables live model calls automatically unless the provider is `mock`.
- Planning fallback must expose safe diagnostics with `fallbackReason`, `errorType`, and host-only `baseUrlHost`; never expose API keys, headers, path/query secrets, or raw request payloads.
- `structuredPlan` is the fact source for Runtime preview and final output.
- `planning_goals` stores generated planning history/cache only; it is not a confirmed Goals/Tasks execution table.

## Naming Contract

- Product name: `Planix`
- Tauri main binary: `planix`
- Sidecar binary: `planix-api.exe`
- API health app: `planix-api`
- MSI artifact: `Planix-v1.1.4-windows-x64.msi`
- Environment namespace: `PLANIX_*`
- User database path: `%APPDATA%\Planix\planix.db`
- Local database path: `data/planix.db`
- Frontend storage prefix: `planix_*`

Do not use or restore old names, and do not add compatibility fallbacks for old environment variables.

## Main Files

- `apps/web/src/App.tsx`: global state, route switch, business callbacks
- `apps/web/src/shell/useAppRoute.ts`: hash route source of truth
- `apps/web/src/shell/RivaShell.tsx`: main shell composition
- `apps/web/src/shell/AppMenu.tsx`: collapsible top-left menu and language switch
- `apps/web/src/shell/InspectorPanel.tsx`: read-only Inspector snapshot UI
- `apps/web/src/pages/DashboardPage.tsx`: Agent workspace and Runtime-triggered Trace entry
- `apps/web/src/components/agent/flow/AgentFlowTrace.tsx`: Agent execution observability panel
- `apps/web/src/store/agentFlowStore.ts`: Runtime event consumer with demo fallback
- `apps/web/src/components/AIWorkspace.tsx`: Notes, Goals, and Settings feature sections
- `apps/web/src/components/CalendarPanel.tsx`: calendar, note UI, selected-day clearing, and full calendar plan clearing
- `apps/web/src/components/PlanList.tsx`: daily task UI
- `apps/web/src/lib/api.ts`: API and Tauri IPC proxy client
- `apps/desktop/src-tauri/src/main.rs`: Tauri startup, sidecar lifecycle, health preflight, IPC proxy
- `backend/app/main.py`: FastAPI app and CORS
- `backend/app/schemas.py`: API contracts
- `backend/app/services/structured_goal_plan.py`: structured planning normalization and markdown rendering
- `backend/app/routers/runtime.py`: NDJSON Runtime endpoint
- `backend/app/services/runtime.py`: Planner, Memory, Tool Router, Stream Engine, Runtime Orchestrator

## Frontend Constraints

- Do not add `react-router`; keep lightweight hash routing.
- `AppRoute` is the only active-page state.
- Language is `zh-CN | en-US`, persisted with the `planix_lang` key.
- All static UI text should use `t("namespace.key")`.
- Agent Trace is an observability layer driven by Runtime events, not a replacement for the Workspace.
- Runtime fallback must clearly show `当前使用本地规划模板生成，后端 Runtime 未连接`.
- Do not reintroduce old demo markers such as `plan_context_lookup`, `ui-mock`, or static UI mock wording.
- Runtime output should answer the user's goal directly, such as producing a readable Python learning plan for a Python learning prompt.
- Internal `reasoning` nodes must display as `Plan` / `执行计划`; do not expose hidden chain-of-thought.
- Goals should render `structuredPlan` when present and keep old task-apply behavior based on legacy `tasks`.
- Goals calendar writes should show immediate writing feedback, visible pressed/writing button styling, and final created/updated/failed counts.
- Dashboard Runtime proposals may be written to Calendar only after the user clicks `写入日历`; valid `llm` and `local_fallback` structuredPlan outputs are both writable, and Runtime execution itself must not auto-write Calendar data.
- Calendar full-plan clearing prefers `DELETE /api/plans/all`; when an older backend returns 404, the frontend may fall back to deleting known plans individually and should retain failed deletions in state.
- Settings model input is free text with built-in recommendations for `deepseek-v4-flash` and `deepseek-v4-pro` only.
- Do not change existing request payloads or response schemas unless explicitly required by the phase plan.

## Runtime Constraints

- `/api/runtime/run` is the Runtime entrypoint and returns `application/x-ndjson`.
- Planner decomposes work only; it must not execute tools or manage streaming.
- Tool Router selects only approved tools.
- Stream Engine turns Runtime state into events only.
- Runtime Orchestrator is the only coordinator.
- Tools are read-only or preview-only: `search_materials`, `get_today_plans`, `get_memory`, `propose_tasks`.
- Runtime builds one internal Context Pack from goal, explicit constraints, preference memory, history memory, today plans, materials, and output language.
- Preference memory is a separate context layer and has higher priority than history memory.
- `get_memory` returns `preferenceMemory` and `historyMemory`; do not add `get_preferences`.
- `payload.preferences` must merge field-by-field with saved preferences, not replace the full object.
- `propose_tasks` returns preview-only `structuredPlan`, tasks, sources, diagnostics, and `memoryContextSummary`.
- `propose_tasks` must not write to `plans`, Goals, Calendar, or Notes; automatic writes are reserved for a later confirmed phase.
- `structuredPlan` drives Runtime preview and final output rendering.
- Runtime must clean Context Pack history before retrieval and planning. `historyMemory.recentProgress` should be compressed to `{ title, summary, relevanceToGoal }` objects, `search_materials.input.query` should be short and goal-focused, and `memoryContextSummary` should never include full historical Markdown.
- Medium-relevance history can inform the memory summary, but should not enter material search unless it shares clear goal-domain keywords.
- Rust `stream_agent_runtime` must remain a thin pass-through bridge.
- If true LLM streaming is unavailable, do not split a completed LLM response into fake token chunks; use Runtime step events plus final output or local structured fallback.

## Settings Maintenance

Settings has a "Memory & Runtime Data" maintenance area backed by these endpoints:

- `GET /api/settings/ai-memory-cache/stats`
- `DELETE /api/settings/memory/preferences`
- `DELETE /api/settings/memory/history`
- `DELETE /api/settings/runtime/runs`
- `DELETE /api/settings/planning/history`
- `DELETE /api/settings/ai-memory-cache`

Rules:

- Clearing preference memory only removes Runtime preference memory and must not alter API Key, provider, model, or Base URL.
- Clearing history memory only clears `agent_runs.output_summary`; it does not delete `agent_runs` or `agent_events`.
- Clearing Runtime runs deletes `agent_events` before `agent_runs`.
- Clearing planning history deletes `planning_goals`, which is planning history/cache only.
- All maintenance actions must preserve formal `plans`, Calendar, Notes, documents, and AI settings.

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

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check-desktop-config.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\check-packaging-toolchain.ps1
```

Latest local MSI generation record: `release\Planix-v1.1.4-windows-x64.msi` was regenerated on 2026-07-04 with SHA256 `f0bfdfd0a5e7a3c8cba444c8ce7b8e57f22358192ed3096b42638a2255394766`. Release binaries remain ignored by Git and should be attached through release tooling rather than committed.

## Documentation Maintenance

`README.md`, `AGENTS.md`, and `CLAUDE.md` must be kept current whenever the project changes meaningfully. This includes phase status, frontend shell, i18n, API behavior, database behavior, AI strategy, packaging, release artifacts, screenshots, and portfolio positioning.
