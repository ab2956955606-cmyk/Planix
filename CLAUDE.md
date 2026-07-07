# CLAUDE.md - Planix

## Positioning

Planix is an AI application portfolio project. The portfolio-facing documentation version is `v3.0.0`, and it presents a RIVA-style AI OS Shell on the frontend connected to a real backend Runtime stream while keeping planning, review, RAG, evaluation, and desktop packaging capabilities behind a clean menu-based workspace.

The current focus has moved into **Phase 4: Command Agent / P Mode** while preserving the completed Phase 3 planning/RAG, Dashboard Runtime, and Calendar write behavior. The active P Mode slice is Phase 4.6: Collapsed Execution Chain + Draft Task Refinement, with a minimal conversation thread, bottom composer, hidden calendar drafts, inline draft detail/regeneration, inline task refinement, permission-gated Calendar writing, and a hidden right-side conversation drawer.

The project is fully named Planix across frontend, backend, desktop, sidecar, installer, database path, environment variables, and documentation.

## Documentation Maintenance

Every completed implementation must update `README.md`, `AGENTS.md`, and `CLAUDE.md` before final reporting. Record relevant behavior, API/database changes, phase boundaries, and verification notes, but never record secrets, local API keys, Authorization headers, or machine-specific credentials.

`README.md` is the portfolio-facing project homepage. Keep internal maintenance rules, implementation notes, and historical development logs in `AGENTS.md`, `CLAUDE.md`, or `docs/`, not at the top of `README.md`.

The portfolio-facing documentation version is `v3.0.0`. Do not confuse this with `package.json`, `tauri.conf.json`, `Cargo.toml`, backend health responses, or installer build versions unless a separate release-version bump task is explicitly requested.

## Stack

- `apps/web`: React 18 + TypeScript + Vite
- `apps/web/src/shell`: Planix RIVA Shell, App Menu, Inspector, hash route
- `apps/web/src/pages`: Dashboard, Calendar, Notes, Goals, Settings
- `apps/web/src/pages/CommandPage.tsx`: minimal P Mode route
- `apps/web/src/components/command`: command composer, permission popover, workbench toggle, and inline thread rendering
- `apps/web/src/stores/commandAgentStore.ts`: P Mode frontend state for `auto | chat | workbench`, permission selection, thread history drawer, command streaming, runtime mini cards, draft cards, approval cards, and Calendar write result cards
- `apps/web/src/components/agent/flow`: Agent Flow Trace observability UI
- `apps/web/src/store/agentFlowStore.ts`: Runtime event to Trace state mapping
- `apps/web/src/i18n`: `zh-CN` / `en-US` text system
- `apps/desktop`: Tauri v2 desktop shell
- `backend/app`: FastAPI backend
- `backend/app/routers/command.py`: Phase 4.5 command chat, approval, thread list, thread replay, and thread deletion endpoints
- `backend/app/services/command_agent.py`: command threads, messages, deterministic intent routing, thread-local context, Runtime handoff, hidden calendar draft creation, automatic inline plan detail, draft regeneration, draft task refinement, Calendar write actions, approval handling, LLM chat, and safe fallback text
- SQLite: plans, month notes, planning goals, daily reviews, AI settings, local RAG documents, chunks, FTS5 index, AI run logs, agent runs, agent events
- AI client: DeepSeek-first OpenAI-compatible client with local structured fallback
- Planning: `StructuredGoalPlan` schema in `backend/app/schemas.py`, helper logic in `backend/app/services/structured_goal_plan.py`, and quality gate logic in `backend/app/services/planning_quality.py`
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

Optional quality and source fields:

- `planHorizon`: detected raw text, duration days, horizon type, start/end date, expected milestones, expected minimum tasks, and expected covered weeks
- `qualityReport`: validator status, score, task/milestone/week coverage counts, date span, and issue list
- `qualityStatus`: `passed | repaired | local_fallback`
- `sourceType`: `local_context | model_knowledge | local_fallback | insufficient_context`
- `localRelevance`: `high | medium | low`

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
- Shared Planning Service must detect plan horizon, build a density policy, validate `structuredPlan`, attempt at most one model repair, and then use local fallback if quality still fails.
- Horizon detection precedence is explicit duration in the goal text, then valid deadline, then long-term keywords defaulting to 30 days, otherwise 14 days.
- Static tiny generation limits should not be reintroduced. 90-day plans should have at least 24 tasks and cover at least 10 distinct weeks.
- Local fallback should spread due dates across the full horizon, cap estimated minutes by daily availability, and pass the same quality gate when possible.
- Local retrieved sources become `local_context` only when core or strong expanded keyword evidence exists; weak generic keywords alone keep local relevance low.
- Phase 3.10 task refinement is context-aware. `RefineTaskRequest` may include optional compact `planContext`, and `RefinedTask` may include optional `timeBlocks`, `learningResources`, `budgetExplanation`, and `planFitCheck`.
- Refinement must not pass huge full plans into the model. Build compact context from plan title/summary, duration, quality status, daily budget, current milestone/task, previous/next task, same-milestone task titles, and top source summaries.
- Refinement time blocks must be backend-normalized so every block is <= 30 minutes. 120-minute tasks should become four 30-minute blocks or equivalent <=30-minute blocks.
- Resource URLs in refined tasks must be official/authoritative allowlisted domains only; non-allowlisted URLs become search keywords.
- Refined task output must stay in the task domain implied by compact context. For example, a skiing balance task must not become a yoga-pose plan; obvious domain drift should trigger same-domain local fallback.
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
- Intended portfolio installer artifact: `Planix-v3.0.0-windows-x64-setup.exe`
- Intended backup MSI artifact: `Planix-v3.0.0-windows-x64.msi`
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
- `apps/web/src/pages/CommandPage.tsx`: Codex-like P Mode command surface
- `apps/web/src/components/command`: AgentThread, CommandComposer, PermissionPopover, WorkbenchToggle
- `apps/web/src/stores/commandAgentStore.ts`: command thread UI state, permission state, workbench trigger, and inline write approval flow
- `apps/web/src/components/agent/flow/AgentFlowTrace.tsx`: Agent execution observability panel
- `apps/web/src/store/agentFlowStore.ts`: Runtime event consumer with demo fallback
- `apps/web/src/components/AIWorkspace.tsx`: Notes, Goals, and Settings feature sections
- `apps/web/src/components/CalendarPanel.tsx`: compact calendar, note UI, visible selected-day clearing, and full calendar plan clearing
- `apps/web/src/components/PlanList.tsx`: daily task UI
- `apps/web/src/lib/api.ts`: API and Tauri IPC proxy client
- `apps/desktop/src-tauri/src/main.rs`: Tauri startup, sidecar lifecycle, health preflight, IPC proxy
- `backend/app/main.py`: FastAPI app and CORS
- `backend/app/schemas.py`: API contracts
- `backend/app/services/structured_goal_plan.py`: structured planning normalization and markdown rendering
- `backend/app/services/planning_quality.py`: horizon detection, density policy, quality validation, and source grounding assessment
- `backend/app/routers/runtime.py`: NDJSON Runtime endpoint
- `backend/app/services/runtime.py`: Planner, Memory, Tool Router, Stream Engine, Runtime Orchestrator
- `backend/app/routers/command.py`: P Mode command endpoints
- `backend/app/services/command_agent.py`: command persistence and NDJSON chat fallback
- `backend/app/services/permission_gate.py`: low / medium / high approval matrix

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
- Goals and Calendar task refinement should pass real task `estimatedMinutes`; Calendar refinement must not hardcode 60 minutes when the task has its own estimate.
- Calendar refinement for AI tasks should use `command-draft:*` source keys to recover the original compact draft context when available; do not rely only on a generic Calendar title if the source draft can be read.
- AI Calendar writes should preserve the generated task description in `plans.result`, plus source key, priority, and estimated minutes. Existing AI rows may only receive a description when their result is empty.
- Refined task UI should display optional time blocks, learning resources, budget explanation, and plan-fit checks while keeping old refined task payloads renderable.
- Dashboard Runtime proposals may be written to Calendar only after the user clicks `写入日历`; valid `llm` and `local_fallback` structuredPlan outputs are both writable, and Runtime execution itself must not auto-write Calendar data.
- Dashboard Runtime proposal cards may show concise quality label, horizon duration, task count, and coverage range, but should not show raw validator JSON or full quality score.
- Command/P Mode is a minimal Codex-like route. `CommandPage` may contain only the conversation thread and bottom composer; do not add fixed `PWorkspacePanel`, Calendar draft panes, Goal draft panes, Materials draft panes, or Notes draft panes.
- The top-left Planix `P` brand mark and the menu P entry both route to Command/P Mode; collapsed menu states must still show a visible P letter and should never leave only a colored background.
- When no explicit hash route exists, the frontend should default to `#/command`. The P composer should use normal bottom anchoring, start around two text rows, let text begin from the left edge of the composer, grow with input, and scroll internally only after about five rows.
- Keep the P page visually loose: empty state content should sit slightly above center, the thread should have breathing room, and no fixed workspace or draft panel should be introduced.
- P Mode may expose a hidden right-side conversation drawer for new chat, history, and deleting command threads. The drawer must remain a conversation manager, not a workspace preview or persistent draft panel.
- P Workspace is an internal draft/audit concept, not a page layout. Phase 4.4 may write hidden `calendar_plan` drafts and permission-gated Calendar write actions only.
- Command mode is a single `auto | chat | workbench` value. Default `auto` keeps normal chat conversational, while clear planning requests run backend Runtime and return compact summary cards.
- Chat and Runtime planning may use recent text messages from the current command thread as context. New chats must start clean and must not inherit context from previous threads.
- After a valid Runtime planning draft is created, show both the compact summary and the full plan as inline cards by default.
- P Mode Runtime execution events should render as one collapsible inline execution chain after completion. The thread should use a lightweight center arrow toggle for collapse/expand, may show execution details on click, and must not introduce a fixed Trace or Workspace panel.
- P Mode execution chain groups should blend into the page background instead of using a gray block.
- P Mode task refinement commands such as `细化任务`, `细化计划`, or `refine all tasks` refine the current hidden `calendar_plan` draft. Store results in `command_drafts.payload_json.refinements` and render them inline; do not write Calendar from refinement alone.
- P Mode `refine all tasks` should avoid unbounded LLM calls; first version caps a batch at 5 tasks and prioritizes the current/first milestone.
- Forced chat mode is discussion-only and must not run Dashboard Runtime, create drafts, write Calendar data, or execute any instruction.
- Forced workbench mode is a planning entry state that may run backend Runtime and create a hidden `calendar_plan` draft.
- Command permission state is `low | medium | high`; low confirms writes/deletes, medium confirms deletes/dangerous actions, and high confirms dangerous actions only.
- P Mode Calendar writes must start from the current hidden `calendar_plan` draft, use `command-draft:` source keys, never overwrite manual plans, and never overwrite `completion/result/done`.
- In a command thread with a current `calendar_plan` draft, phrases like `写入计划`, `保存计划`, `保存`, and `确认写入` should route to Calendar writing through PermissionGate instead of starting a new Runtime planning run.
- P Mode Calendar writes should include matching refined task payloads from the draft in `plans.refined_task_json`, while preserving `completion/result/done`.
- P Mode Calendar write failures from `/api/command/chat` or `/api/command/approve` should use the Calendar-specific write error. They must not be reported as draft-save failures.
- Command table startup migrations must preserve old local SQLite data and add `command_actions.draft_id`, `command_actions.error_message`, and `command_approvals.decision` without destructive rebuilds.
- Calendar month view should load all plans for the visible month so dates with plans are highlighted before the user clicks them.
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
- `propose_tasks` returns preview-only `structuredPlan`, tasks, sources, diagnostics, `memoryContextSummary`, `planHorizon`, `qualityReport`, `qualityStatus`, `sourceType`, and `localRelevance`.
- `propose_tasks` must not write to `plans`, Goals, Calendar, or Notes; automatic writes are reserved for a later confirmed phase.
- `structuredPlan` drives Runtime preview and final output rendering.
- If Runtime lacks sufficient local material evidence, final output should begin with `本地资料不足，下面是通用建议，不代表资料库事实.`
- Runtime must clean Context Pack history before retrieval and planning. `historyMemory.recentProgress` should be compressed to `{ title, summary, relevanceToGoal }` objects, `search_materials.input.query` should be short and goal-focused, and `memoryContextSummary` should never include full historical Markdown.
- Medium-relevance history can inform the memory summary, but should not enter material search unless it shares clear goal-domain keywords.
- Rust `stream_agent_runtime` must remain a thin pass-through bridge.
- If true LLM streaming is unavailable, do not split a completed LLM response into fake token chunks; use Runtime step events plus final output or local structured fallback.
- `/api/command/chat` streams Phase 4.6 command NDJSON events (`thread`, `assistant_delta`, `runtime_started`, `runtime_event`, `draft_created`, `summary`, `plan_detail`, `refinement_started`, `refined_tasks_result`, `calendar_plan_preview`, `approval_required`, `calendar_write_result`, `execution_result`, `done`, `error`) for P Mode.
- `/api/command/approve` approves or rejects pending Calendar write actions. `/api/command/threads` lists command thread summaries, `/api/command/thread/{thread_id}` replays saved messages and may return the current hidden draft, and `DELETE /api/command/thread/{thread_id}` deletes command-thread data without deleting Calendar plans.
- Phase 4.4 stores `command_threads`, `command_messages`, hidden `command_drafts`, Calendar write `command_actions`, and `command_approvals`. Do not register `/api/command/drafts` or use `command_outputs` until a later phase explicitly enables them.

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

Portfolio release naming uses `release\Planix-v3.0.0-windows-x64-setup.exe` as the primary Setup.exe and `release\Planix-v3.0.0-windows-x64.msi` as the backup MSI. Each installer should have its own `.sha256` checksum. Release binaries remain ignored by Git and should be attached through release tooling rather than committed.

## Documentation Maintenance

`README.md`, `AGENTS.md`, and `CLAUDE.md` must be kept current whenever the project changes meaningfully. This includes phase status, frontend shell, i18n, API behavior, database behavior, AI strategy, packaging, release artifacts, screenshots, and portfolio positioning.
