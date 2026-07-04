# Planix

Planix is an AI planning workspace for goals, schedules, knowledge materials, daily reviews, grounded planning, Agent Runtime execution, and Windows desktop delivery. It combines a RIVA-style AI OS shell with a React frontend, FastAPI backend, SQLite persistence, FTS5/BM25 retrieval, NDJSON Runtime streaming, and a Tauri desktop package.

## Documentation Rule

After each implemented change, update `README.md`, `AGENTS.md`, and `CLAUDE.md` with the relevant behavior, boundary, or verification notes before considering the work complete.

## 中文简介

Planix 面向学习、求职和长期目标管理场景。用户可以维护日历任务、保存资料、上传 TXT/MD 文件、使用本地资料库问答、生成结构化目标规划、执行今日复盘、预览重排任务，并通过质量评估查看规划是否足够清晰、可执行和有作品集价值。

当前阶段为 **Phase 3.5：Planning Intelligence + Grounded RAG**。Planix 会先从本地资料库检索相关资料，再生成严格结构化的目标规划，并让 Runtime 的任务预览和最终输出使用同一份 `structuredPlan`。本阶段只做检索、规划、预览和展示，不会自动写入 Goals、Calendar 或 Notes。

## Architecture

| Layer | Stack |
| --- | --- |
| Web | React + TypeScript + Vite |
| Shell | RIVA-style AI OS UI with hash routing and i18n |
| Backend | FastAPI |
| Storage | SQLite |
| RAG | SQLite FTS5/BM25 |
| Planning | Structured goal plan schema + grounded sources |
| Runtime | Planner + Memory + Tool Router + Stream Engine + Runtime Orchestrator |
| Streaming | Web fetch NDJSON + Tauri `stream_agent_runtime` bridge |
| AI | DeepSeek-first OpenAI-compatible client with local structured fallback |
| Desktop | Tauri v2 + `planix-api.exe` sidecar |
| Installer | `release/Planix-v1.1.4-windows-x64.msi` |

## Features

- Calendar and daily task management
- Calendar note management with selected-day clearing and full calendar plan clearing
- Structured goal planning with phases, tasks, estimated time, priority, due date, and review plan
- Grounded RAG using local SQLite FTS5/BM25 sources
- Daily review, suggestions, and replan preview
- Knowledge base with paste input and TXT/MD upload
- Planner quality evaluation across six dimensions
- Model settings with masked API key state, free-text model IDs, and `deepseek-v4-flash` / `deepseek-v4-pro` recommendations
- RIVA dashboard with Dashboard / Calendar / Notes / Goals / Settings routes
- Agent Flow Trace connected to real Runtime NDJSON events
- Safe Runtime tools: read-only retrieval plus preview-only task proposals
- Runtime Context Pack cleanup: compressed history summaries, short material search queries, and deterministic memory summaries
- Settings maintenance tools for clearing AI preference memory, history summaries, Runtime records, and planning history/cache without deleting formal user data
- Runtime output answers the user's goal directly, for example returning a readable Python learning plan
- Runtime run and event persistence for future replay/debug
- Chinese and English realtime switching
- Tauri desktop shell with FastAPI sidecar

## Planning Intelligence

`/api/planning/goal-plan` keeps the old compatibility fields and adds `structuredPlan`:

```ts
type StructuredGoalPlan = {
  goalTitle: string;
  goalDescription: string;
  durationDays: number;
  milestones: Array<{
    title: string;
    description: string;
    tasks: Array<{
      title: string;
      description: string;
      estimatedMinutes: number;
      dueDate: string | null;
      priority: "low" | "medium" | "high";
    }>;
  }>;
  reviewPlan: {
    frequency: "daily" | "weekly";
    questions: string[];
  };
};
```

The backend treats `structuredPlan` as the source of truth. Goal planning asks the model only for `summary + structuredPlan`; legacy `phases` and `tasks` are derived from that structure so existing Calendar and plan-apply flows continue to work. LLM output is parsed, validated, and completed with a local structured fallback when fields are missing or invalid.

Fallback is transparent: `goal-plan` may include `fallbackReason`, `errorType`, `errorMessage`, and `baseUrlHost` so the frontend can distinguish Mock mode, missing keys, and live model failures without exposing API keys or full request URLs.

Goals planning uses `PLANIX_GOAL_PLAN_MAX_TOKENS` for its output budget. The default is `4096`, valid higher values can be set up to `8000`, and OpenAI-compatible `finish_reason="length"` is reported as `model_output_truncated` instead of being merged into generic invalid JSON errors.

`planning_goals` stores generated planning results and source snapshots only. It is a planning history/cache table, not a confirmed execution model and not a formal Goals/Tasks table.

## Grounded RAG

Planix stores pasted or uploaded materials in SQLite and indexes chunks with FTS5/BM25. RAG sources use a stable shape:

```ts
type RagSource = {
  documentId: string;
  title: string;
  chunk: string;
  score: number;
  chunkIndex: number;
};
```

The backend sorts results before returning them. The frontend displays `score` as a backend relevance value and does not reinterpret the ranking. When sources are found, planning and Runtime output include a "参考资料 / References" section.

## Runtime API

Planix Runtime turns one prompt into an observable execution stream:

```text
User input
  -> Planner
  -> Memory System
  -> Tool Router
  -> Stream Engine
  -> Agent Flow Trace
```

Runtime endpoint:

```http
POST /api/runtime/run
Content-Type: application/json
Accept: application/x-ndjson
```

Events are NDJSON objects such as `node`, `delta`, `tool`, `status`, `final`, and `error`. The desktop build uses the Tauri `stream_agent_runtime` IPC bridge to forward sidecar events to the frontend.

Runtime safety rules:

- Runtime builds one internal Context Pack from the current goal, explicit constraints, preference memory, history memory, today's plans, and local RAG materials.
- `get_memory` returns separate `preferenceMemory` and `historyMemory` layers. Preference memory controls planning style, daily time budget, output language, difficulty, career direction, and project preference.
- Runtime tool order is `get_memory -> get_today_plans -> search_materials -> propose_tasks`, while the NDJSON event protocol remains unchanged.
- Runtime cleans memory before retrieval and planning: `historyMemory.recentProgress` is exposed as short `{ title, summary, relevanceToGoal }` objects, `search_materials.input.query` is a short goal-focused query, and `memoryContextSummary` never includes full historical Markdown.
- `search_materials`, `get_today_plans`, and `get_memory` are read-only.
- `propose_tasks` returns structured previews only, including `mode`, `structuredPlan`, derived tasks, sources, diagnostics, and a deterministic `memoryContextSummary`.
- Runtime never auto-writes generated tasks to `plans`, Goals, Calendar, or Notes in this phase.
- `structuredPlan` is the fact source; final output is rendered from it so Trace, preview, and Output stay consistent.
- If true LLM token streaming is unavailable, Planix does not fake it by splitting a completed LLM response. It still streams Runtime step/tool/status events and uses local structured fallback output when needed.

## AI Memory And Cache Maintenance

Settings includes a "Memory & Runtime Data" maintenance area. It can clear AI preference memory, Runtime history summaries, Runtime run/event records, and planning history/cache. These actions are confirmation-gated and preserve formal user data.

Maintenance endpoints:

```http
GET    /api/settings/ai-memory-cache/stats
DELETE /api/settings/memory/preferences
DELETE /api/settings/memory/history
DELETE /api/settings/runtime/runs
DELETE /api/settings/planning/history
DELETE /api/settings/ai-memory-cache
```

Safety rules:

- Clearing preference memory only removes the Runtime preference key and never changes API Key, provider, model, or Base URL.
- Clearing history memory only clears `agent_runs.output_summary`; it does not delete raw Runtime runs or events.
- Clearing Runtime records deletes `agent_events` before `agent_runs`.
- Clearing planning history/cache deletes `planning_goals`, which is planning history/cache only.
- All maintenance actions preserve `plans`, Calendar, Notes, documents, and AI settings.

## Environment Variables

Planix uses the `PLANIX_*` namespace only:

```powershell
PLANIX_ENV=desktop
PLANIX_API_PORT=8000
PLANIX_DB_PATH=C:\path\to\planix.db
PLANIX_USE_USER_DATA=1
PLANIX_API_VERSION=1.1.4
PLANIX_API_LOG=C:\path\to\planix-api.log
PLANIX_TAURI_TARGET=x86_64-pc-windows-msvc
PLANIX_SKIP_SIDECAR=1
PLANIX_GOAL_PLAN_MAX_TOKENS=4096
```

AI keys are never committed. Use environment variables or the in-app settings screen. A saved key enables live model calls automatically unless the provider is `mock`.

```powershell
DEEPSEEK_API_KEY=your_key
AI_API_KEY=your_key
```

## Development

Frontend:

```powershell
cd apps\web
npm install
npm run dev
npm run lint
npm run test
npm run build
```

Backend:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
pytest backend\tests
```

Desktop checks:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check-desktop-config.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\check-packaging-toolchain.ps1
```

Build MSI:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-release.ps1 -Version 1.1.4
```

Expected release assets:

```text
release\Planix-v1.1.4-windows-x64.msi
release\Planix-v1.1.4-windows-x64.sha256
```

Installed layout:

```text
Planix\
  planix.exe
  resources\
    index.html
    assets\
    binaries\
      planix-api.exe
```

## Verification

Run the main checks:

```powershell
python -m compileall backend
.\.venv\Scripts\python.exe -m pytest backend\tests
cd apps\web
npx.cmd tsc -b
npm.cmd run lint
npm.cmd run test
npm.cmd run build
```

Expected health response:

```json
{
  "status": "ok",
  "app": "planix-api",
  "version": "1.1.4"
}
```

## Portfolio Summary

Planix demonstrates a complete AI application path: frontend product shell, backend APIs, SQLite persistence, local retrieval, structured AI planning, grounded RAG, review/replan loop, Runtime event streaming, safe tool routing, quality evaluation, desktop packaging, sidecar startup, health checks, and MSI release automation. It is designed as a strong AI application / full-stack / desktop portfolio project.

## Maintenance Rule

When architecture, version, APIs, environment variables, packaging, database paths, sidecar names, screenshots, or product positioning changes, update `README.md`, `AGENTS.md`, and `CLAUDE.md` in the same change set.
