# Planix

**Current documentation version: v3.0.0**

Planix is a desktop AI planning workspace that turns broad goals into structured, reviewable, and calendar-ready task plans. It combines a React + Tauri desktop shell, FastAPI backend, SQLite persistence, local RAG retrieval, structured LLM planning, observable Agent Runtime streaming, and a Codex-like Command Mode for planning, refining, and writing tasks safely.

Planix is designed as a portfolio-grade AI application project, not a simple prompt demo. Its core focus is structured planning, grounded context retrieval, transparent fallback behavior, runtime traceability, and safe user-confirmed calendar writes.

Planix 是一个面向学习、求职和长期目标管理的桌面 AI 规划工作台。它可以把用户的宽泛目标转化为结构化计划，并结合本地资料库检索、Agent Runtime 执行流、P Mode 命令式对话、任务细化和安全写入日历，形成一个完整的 AI 应用闭环。

## Demo

Planix provides a desktop AI planning workspace with structured goal planning, RAG-grounded context retrieval, observable Agent Runtime traces, and calendar-ready task proposals.

<!-- TODO: Add a real local screenshot after running the app. Recommended path: assets/planix-dashboard-cn.png -->

## What Planix Does

- Turns broad goals into structured weekly or daily plans.
- Retrieves relevant local notes and materials through RAG before planning.
- Produces a `structuredPlan` instead of only free-form text.
- Shows Agent Runtime execution traces so the planning process is observable.
- Lets users review, refine, and write approved tasks to the calendar.
- Provides a desktop app experience through Tauri and a bundled Python backend sidecar.

## Why It Is More Than a Demo

Planix is designed around structured AI application engineering rather than a single prompt call.

- The model output is constrained into `structuredPlan` for reliable downstream use.
- RAG retrieval grounds planning in local notes and documents.
- Runtime events are streamed as NDJSON and rendered as an Agent Flow Trace.
- Calendar writes are user-reviewed instead of automatic blind execution.
- P Mode adds a command-oriented workflow for refining plans and controlling actions.
- The desktop app packages a Tauri shell with a PyInstaller backend sidecar.

## Architecture

Planix is built as a local-first desktop AI application.

```text
React + TypeScript UI
        ↓
Tauri Desktop Shell
        ↓
FastAPI Backend Sidecar
        ↓
SQLite / FTS5 / Local Files
        ↓
RAG + Planning Service + Agent Runtime
        ↓
NDJSON Stream → Agent Flow Trace UI
```

Core layers:

- Frontend Shell: dashboard, calendar, notes, goals, materials, settings, and P Mode.
- Runtime Core: planner, memory lookup, tool routing, structured proposal generation, and stream events.
- RAG Layer: local material search with SQLite FTS / BM25-style retrieval.
- Persistence Layer: SQLite for plans, notes, materials, settings, runtime records, and command threads.
- Desktop Packaging: Tauri installer with a PyInstaller onedir backend sidecar.

## Core Features

### Planning Intelligence

- Goal-to-plan generation.
- `structuredPlan` output as the planning source of truth.
- Task, milestone, and calendar-ready proposal generation.
- Transparent fallback behavior when model output is unavailable or invalid.

### Grounded RAG

- Local notes and materials retrieval.
- SQLite FTS / BM25-style search.
- Retrieved context shown in runtime output.
- Source-aware planning flow.

### Agent Runtime

- Observable runtime execution chain.
- NDJSON streaming.
- Agent Flow Trace UI.
- Runtime events such as memory lookup, material search, proposal generation, and summary.

### P Mode / Command Agent

- Codex-like command conversation surface.
- Auto / forced chat / forced workbench modes.
- Thread-local context for follow-up planning requests.
- Hidden planning drafts with inline summaries, details, refinements, approvals, and calendar write results.

### Desktop Packaging

- Tauri desktop shell.
- Python FastAPI backend sidecar.
- Windows installer packaging.
- MSI retained as a backup / enterprise-friendly installer format.

## Tech Stack

- Frontend: React, TypeScript, Vite.
- Desktop: Tauri.
- Backend: Python, FastAPI.
- Storage: SQLite, local files.
- Retrieval: SQLite FTS / BM25-style local search.
- Runtime: NDJSON streaming, Agent Flow Trace.
- AI Provider: DeepSeek-compatible OpenAI-style API with local fallback.
- Packaging: PyInstaller sidecar, Tauri Windows installer.

## Run Locally

### Backend

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```

### Frontend

```powershell
cd apps\web
npm install
npm run dev
```

### Desktop

```powershell
.\scripts\dev-desktop.ps1
cd apps\desktop
npm install
npm run dev
```

## Verification

Backend checks:

```powershell
python -m compileall backend
.\.venv\Scripts\python.exe -m pytest backend\tests
```

Frontend checks:

```powershell
cd apps\web
npx.cmd tsc -b
npm.cmd run lint
npm.cmd run test
npm.cmd run build
```

Desktop packaging checks:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check-desktop-config.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\check-packaging-toolchain.ps1
```

Backend health check:

```powershell
curl http://127.0.0.1:8000/api/health
```

## Download

The portfolio documentation refers to the current public presentation as `v3.0.0`.

Intended Windows installer naming:

- Recommended installer: `Planix-v3.0.0-windows-x64-setup.exe`
- Backup / enterprise installer: `Planix-v3.0.0-windows-x64.msi`
- Checksum files: `Planix-v3.0.0-windows-x64-setup.exe.sha256` and `Planix-v3.0.0-windows-x64.msi.sha256`

`.sha256` files are checksum files for verifying downloads. They are not installers and should not be double-clicked to install Planix.

## Roadmap

Completed:

- Planning Intelligence + `structuredPlan` generation.
- Grounded RAG over local notes and materials.
- Observable Agent Runtime with NDJSON streaming.
- P Mode / Command Agent workflow.
- Calendar-ready proposal review flow.
- Tauri desktop packaging prototype.

In progress:

- Windows installer polish.
- Runtime replay and debug view.
- More refined portfolio demo screenshots.
- Safer and clearer action approval UX.

Next:

- Multi-plan workspace.
- Better evaluation and regression tests for planning quality.
- More tool integrations.
- Improved onboarding and sample data.

## Portfolio Summary

Planix demonstrates a complete AI application path: frontend product shell, backend APIs, SQLite persistence, local retrieval, structured AI planning, grounded RAG, review and replan loops, Runtime event streaming, safe tool routing, quality evaluation, desktop packaging, sidecar startup, health checks, and installer release automation.
