# Planix

Planix is an AI planning workspace for goals, schedules, knowledge materials, daily reviews, and Windows desktop delivery. It combines a RIVA-style AI OS shell with a React frontend, FastAPI backend, SQLite persistence, local FTS5/BM25 retrieval, and a Tauri desktop package.

## 中文简介

Planix 面向学习、求职和长期目标管理场景。用户可以维护日历任务、保存资料、上传 TXT/MD 文件、使用本地资料库问答、生成目标规划、执行今日复盘、预览重排任务，并通过质量评估查看规划是否足够清晰、可执行和有作品集价值。

当前版本已完成前端品牌、后端标识、桌面 sidecar、环境变量、数据库路径和 MSI 产物的 Planix 统一命名。项目不再读取旧环境变量，也不做旧数据迁移。

## Architecture

| Layer | Stack |
| --- | --- |
| Web | React + TypeScript + Vite |
| Shell | RIVA-style AI OS UI with hash routing and i18n |
| Backend | FastAPI |
| Storage | SQLite |
| RAG | SQLite FTS5/BM25 |
| AI | DeepSeek-first OpenAI-compatible client with mock fallback |
| Desktop | Tauri v2 + `planix-api.exe` sidecar |
| Installer | `release/Planix-v1.1.4-windows-x64.msi` |

## Features

- Calendar and daily task management
- Goal planning with AI-generated phases and today tasks
- Daily review, suggestions, and replan preview
- Knowledge base with paste input and TXT/MD upload
- Local FTS5/BM25 retrieval with cited sources
- Planner quality evaluation across six dimensions
- Model settings with masked API key state
- RIVA dashboard with Dashboard / Calendar / Notes / Goals / Settings routes
- Chinese and English realtime switching
- Tauri desktop shell with FastAPI sidecar

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
```

AI keys are never committed. Use environment variables or the in-app settings screen:

```powershell
DEEPSEEK_API_KEY=your_key
AI_API_KEY=your_key
USE_REAL_LLM=1
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
npm.cmd run build
cd ..\..
powershell -ExecutionPolicy Bypass -File .\scripts\check-desktop-config.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\check-packaging-toolchain.ps1
```

After launching the desktop app:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\wait-api-health.ps1 -Url http://127.0.0.1:8000/api/health -TimeoutSeconds 30
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

Planix demonstrates a complete AI application path: frontend product shell, backend APIs, SQLite persistence, local retrieval, AI planning, review/replan loop, quality evaluation, desktop packaging, sidecar startup, health checks, and MSI release automation. It is designed as a strong AI application / full-stack / desktop portfolio project.

## Maintenance Rule

When architecture, version, APIs, environment variables, packaging, database paths, sidecar names, screenshots, or product positioning changes, update `README.md`, `AGENTS.md`, and `CLAUDE.md` in the same change set.
