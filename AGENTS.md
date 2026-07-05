# AGENTS.md - Planix

## Project Identity

Planix is a portfolio-grade AI planning application for learning, job search, and long-term execution. It combines a RIVA-style AI OS frontend shell, calendar planning, structured goal decomposition, daily review, grounded local RAG, deterministic planner evaluation, a real Agent Runtime event stream, and Windows desktop packaging.

The project is fully renamed to Planix. Do not reintroduce former product, storage, sidecar, or environment-variable names.

Portfolio-facing documentation version: `v3.0.0`. This is a presentation label for README and related showcase docs; do not treat it as a package, Cargo, Tauri, backend health, or installer build version unless a separate release-version task explicitly says so.

## Current Phase

Phase 4 has started with **Command Agent / P Mode**. The current P Mode implementation is Phase 4.6: Collapsed Execution Chain + Draft Task Refinement. Auto/workbench planning requests may run the existing backend Runtime and save a hidden `calendar_plan` draft; users can expand, regenerate/modify, refine tasks, or write the current draft to Calendar through P Mode permission handling. P Mode also has a hidden right-side conversation drawer for new chat, history, and thread deletion.

Allowed in this phase:

- Retrieve local materials with SQLite FTS5/BM25.
- Generate and validate `structuredPlan`.
- Save generated planning results to `planning_goals` as history/cache.
- Show structured previews in Goals and Runtime Trace.
- Render Runtime final output from the same `structuredPlan`.
- Clean Runtime Context Pack history before retrieval and planning.
- Provide Settings maintenance controls for AI memory/cache cleanup.
- Keep P Mode Codex-like: outputs appear as inline conversation cards, not as a fixed workspace preview panel.
- Keep P Mode defaulting to `auto`: normal chat stays conversational, while clear planning requests may run Runtime and create hidden `calendar_plan` drafts.
- Keep P Mode context thread-local: recent user/assistant text from the current thread may inform chat and planning, but new chats must not inherit prior thread context.
- Let P Mode write Calendar plans only from the current hidden `calendar_plan` draft through `command_actions`, `command_approvals`, and PermissionGate.
- Let P Mode refine tasks in the current hidden `calendar_plan` draft through the existing planning refinement service. Refinement results stay in the command draft until the user writes the plan to Calendar.

Forbidden in this phase:

- Auto-writing generated tasks to Calendar from Runtime without an explicit P command.
- Writing Goals, Notes, Materials, Settings, or non-Calendar data from P Mode.
- Letting P Mode bypass `command_actions`, `command_approvals`, or PermissionGate for Calendar writes.
- Turning P Workspace into a foreground layout panel or persistent Calendar/Goals/Materials/Notes draft area.
- Changing `/api/runtime/run` event protocol.
- Changing Tauri Windows installer sidecar mechanics.

## Architecture

- Frontend: React 18 + TypeScript + Vite in `apps/web`.
- Frontend shell: hash-route Planix RIVA AI OS Shell in `apps/web/src/shell`.
- Frontend pages: `apps/web/src/pages`.
- i18n: `apps/web/src/i18n`, default `zh-CN`, supports `en-US`.
- Agent observability: `apps/web/src/components/agent/flow` renders Runtime events as the Dashboard trace.
- Agent flow state: `apps/web/src/store/agentFlowStore.ts`.
- Command Agent UI: `apps/web/src/pages/CommandPage.tsx` and `apps/web/src/components/command`.
- Command Agent state: `apps/web/src/stores/commandAgentStore.ts`.
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
- Command route: `backend/app/routers/command.py`
- Command service: `backend/app/services/command_agent.py`
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
- Intended portfolio installer artifact: `Planix-v3.0.0-windows-x64-setup.exe`
- Intended backup MSI artifact: `Planix-v3.0.0-windows-x64.msi`
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
- Command/P Mode must stay Codex-like and minimal: `CommandPage` contains the Agent thread and bottom composer only. Do not add a fixed `PWorkspacePanel` or persistent draft panels.
- The top-left Planix `P` brand mark and the menu P entry both route to Command/P Mode; collapsed menu states must still show a visible P letter and should never leave only a colored background.
- When no explicit hash route exists, the frontend should default to `#/command`. The P composer should use normal bottom anchoring while feeling spacious: start around two text rows, begin text from the left edge, grow with input, and scroll internally only after about five rows.
- Keep the P page visually loose: empty state content should sit slightly above center, the thread should have breathing room, and no fixed workspace or draft panel should be introduced.
- P Workspace is an internal draft/audit concept, not a foreground layout. Phase 4.4 may write hidden `calendar_plan` drafts and Calendar write actions only.
- The right-side P conversation drawer is allowed for thread history and deletion only. It must not become a fixed workspace preview or persistent draft panel.
- Command mode is a single `auto | chat | workbench` value. Do not represent it with separate boolean flags.
- Auto mode is the P default. Normal chat stays text-only; `planning_request` runs backend Runtime and creates a compact hidden draft summary.
- Auto/workbench planning should include current-thread context in the backend Runtime input so follow-up phrases like "帮我做个规划" can inherit the current topic. Do not include messages from other threads.
- After a valid planning draft is created, P Mode should show the summary and the full plan inline by default.
- Chat mode is a safety lock: it must not run Dashboard Runtime, create drafts, write Calendar data, or execute any instruction.
- Workbench mode is a forced planning entry state and may run backend Runtime to create a hidden `calendar_plan` draft.
- Command permission state is `low | medium | high`; low asks before writes/deletes, medium auto-runs ordinary writes but asks before deletes, high auto-runs ordinary writes/deletes while dangerous actions still require confirmation.
- P Mode Calendar writes must come from the current hidden `calendar_plan` draft, use `command-draft:` source keys, never overwrite manual plans, and never overwrite `completion/result/done`.
- P Mode Calendar writes may carry `refinedTask` values from `command_drafts.payload_json.refinements` into `plans.refined_task_json`; this must never be mixed into `completion/result/done`.
- P Mode Calendar write failures, including approval execution failures, must show the Calendar-specific write error and must not fall back to draft-save failure wording.
- Command table startup migrations must preserve old local SQLite data and add `command_actions.draft_id`, `command_actions.error_message`, and `command_approvals.decision` without destructive rebuilds.
- P Mode Runtime execution cards should be grouped as one collapsible inline execution chain after output completes. The collapsed row should use a lightweight center arrow toggle, not a heavy gray trace panel. Do not reintroduce a fixed Trace panel in P Mode.
- P Mode execution chain groups should blend into the page background instead of using a gray block.
- Calendar month view should load all plans for the visible month so dates with plans are highlighted before the user clicks them.
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
- Phase 4.6 command endpoints expose `POST /api/command/chat`, `POST /api/command/approve`, `GET /api/command/threads`, `GET /api/command/thread/{thread_id}`, and `DELETE /api/command/thread/{thread_id}`. They store `command_threads`, `command_messages`, hidden `command_drafts`, Calendar write `command_actions`, and `command_approvals`.
- `refine_current_plan` is a command intent handled through `/api/command/chat`. It updates the current `command_drafts.payload_json.refinements`, emits inline refinement result cards, and does not write Calendar unless the user separately commands a Calendar write.
- Do not register `/api/command/drafts` or use `command_outputs` until a later phase explicitly enables them.
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
powershell -ExecutionPolicy Bypass -File .\scripts\build-release.ps1 -Version 3.0.0
```

Portfolio release naming uses `release\Planix-v3.0.0-windows-x64-setup.exe` as the primary Setup.exe and `release\Planix-v3.0.0-windows-x64.msi` as the backup MSI. Each installer should have its own `.sha256` checksum. Release binaries remain ignored by Git and should be attached through release tooling rather than committed.

## Documentation Maintenance

Every completed implementation must update `README.md`, `AGENTS.md`, and `CLAUDE.md` before final reporting. Include relevant behavior, API/database changes, phase boundaries, and verification notes; do not record secrets, local API keys, or machine-specific credentials.

Update these three files whenever architecture, version, routes, UI shell, API behavior, database behavior, environment variables, AI strategy, packaging, release artifacts, screenshots, or portfolio positioning changes.

`README.md` is the portfolio-facing project homepage. Keep internal maintenance rules, implementation notes, and historical development logs in `AGENTS.md`, `CLAUDE.md`, or `docs/`, not at the top of `README.md`.

The portfolio-facing documentation version is `v3.0.0`. Do not confuse this with `package.json`, `tauri.conf.json`, `Cargo.toml`, backend health responses, or installer build versions unless a separate release-version bump task is explicitly requested.

Current Calendar behavior includes a compact month layout, a `Note` area on the Calendar panel, selected-day plan clearing, and full calendar plan clearing. The two clearing buttons should remain visible above the date grid. Clearing plans deletes Calendar `plans` and their task refinements only; it must not delete notes/materials, Goals planning history, AI settings, documents, or API keys.
