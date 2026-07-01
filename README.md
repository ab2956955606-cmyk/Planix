<p align="center">
  <br>
  <strong>MyNotes AI</strong>
  <br>
  <span>AI learning planner, daily review, and local knowledge-base assistant.</span>
  <br><br>
  <img alt="React" src="https://img.shields.io/badge/React-TypeScript-0a84ff">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-SQLite-30d158">
  <img alt="RAG" src="https://img.shields.io/badge/RAG-FTS5%20%2B%20BM25-ff9f0a">
  <img alt="LLM" src="https://img.shields.io/badge/LLM-DeepSeek%20Compatible-6e6e73">
</p>

![MyNotes AI Chinese Demo](assets/mynotes-demo.png)
![MyNotes AI English Demo](assets/mynotes-demo-en.png)

## 中文介绍

**MyNotes AI** 是一个面向学习、求职和长期目标管理的 AI 规划系统。它不只是一个日历页面，而是把“目标输入、资料沉淀、AI 规划、日程执行、日报复盘、重排预览”连成一个可演示的闭环。

当前版本已经升级到强作品集方向：前端使用 React + TypeScript + Vite，后端使用 FastAPI，数据层使用 SQLite；AI 能力支持 DeepSeek / OpenAI-compatible 调用，同时保留 mock fallback，确保没有 API key 也能完整演示。Phase 5 新增本地资料库：用户可以粘贴 JD、课程笔记、面经或项目资料，系统会自动切片并写入 SQLite FTS5 索引，通过 BM25 检索返回引用来源，让资料问答和目标规划更接近真实 RAG 应用。

## English

**MyNotes AI** is an AI planning and review system for learning, job search, and long-term goal management. It connects goal planning, knowledge grounding, calendar execution, daily review, and replan preview into a portfolio-ready AI application.

The project uses React + TypeScript + Vite on the frontend, FastAPI on the backend, and SQLite as the local data layer. It supports DeepSeek/OpenAI-compatible LLM calls with deterministic mock fallback, so the full workflow remains demoable without an API key. Phase 5 adds a local knowledge base powered by SQLite FTS5/BM25, returning source citations for material Q&A and goal planning.

## Current Stage

| Stage | Status | Result |
| --- | --- | --- |
| Phase 0 | Done | Project audit in `docs/audit.md` |
| Phase 1 | Done | React + TypeScript + Vite frontend in `apps/web` |
| Phase 2 | Done | FastAPI routers, SQLite schema, plans API, month-notes API, tests |
| Phase 3 | Done | AI settings, DeepSeek-first OpenAI-compatible client, model test endpoint |
| Phase 4 | Done | Persistent goal planning, daily reviews, replan preview, apply-to-calendar flow |
| Phase 5 | Done | SQLite FTS5/BM25 RAG, document library, source citations |
| Phase 6 | Next | File upload, stronger evaluation set, desktop packaging roadmap |

## Features

| Module | What it does |
| --- | --- |
| Calendar planning | Manage daily tasks with time, status, completion notes, AI/manual source |
| Daily review loop | Generate persisted daily reviews and preview tomorrow's replanning |
| Replan apply | AI suggestions never mutate data until the user confirms |
| Knowledge base | Save pasted JD, notes, interview materials, or project context |
| FTS5/BM25 RAG | Chunk local materials, search with SQLite FTS5, rank with BM25 |
| Source citations | Return document title, chunk, score, and chunk index for every answer |
| Goal grounding | Goal planning can retrieve relevant knowledge-base chunks before generation |
| Model settings | Configure provider, base URL, model, API key, temperature, and timeout |
| Mock fallback | All AI workflows remain demoable without a paid API key |
| Evaluation | Score planning quality with simple test cases and criteria |

## Tech Stack

| Layer | Stack |
| --- | --- |
| Frontend | React 18, TypeScript, Vite, lucide-react |
| Backend | Python, FastAPI, Pydantic, httpx |
| Database | SQLite, FTS5 virtual table, BM25 ranking |
| AI workflow | Planner Agent, Planning Loop, RAG, Memory, Eval, DeepSeek/OpenAI-compatible client |
| Quality | Pytest, Vitest, ESLint, TypeScript build |

## Architecture

```mermaid
flowchart LR
  U["User"] --> FE["React + TypeScript UI"]
  FE --> API["FastAPI /api"]
  FE --> LS["localStorage fallback"]
  API --> PLAN["Plans + Month Notes"]
  API --> LOOP["Planning Loop"]
  API --> RAG["RAG Service"]
  API --> SET["AI Settings"]
  PLAN --> DB["SQLite"]
  LOOP --> DB
  SET --> DB
  RAG --> DOC["documents + document_chunks"]
  DOC --> FTS["document_chunks_fts"]
  LOOP --> RAG
  RAG --> LLM["OpenAI-compatible LLM Client"]
  LOOP --> LLM
  LLM --> PROVIDER["DeepSeek / OpenAI / Custom"]
```

More details: [docs/architecture.md](docs/architecture.md)

## Run Locally

Start the backend:

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```

Start the frontend:

```bash
cd apps/web
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173/MyNotes.html
```

## AI Configuration

Configure the model inside the AI workspace:

```text
Provider: DeepSeek
Base URL: https://api.deepseek.com
Model: deepseek-chat
API Key: your key
```

API keys are accepted by the backend but never returned by `GET /api/ai/settings`. Without a key, the backend returns stable mock results.

Environment variables are also supported:

```bash
AI_PROVIDER=deepseek
AI_API_KEY=
AI_API_BASE=https://api.deepseek.com
AI_MODEL=deepseek-chat
DATABASE_URL=sqlite:///./data/mynotes.db
```

## RAG Workflow

1. Paste a JD, course note, interview note, or project brief into the knowledge base.
2. `POST /api/rag/documents` saves metadata into `documents` and chunks into `document_chunks`.
3. Each chunk is inserted into `document_chunks_fts`.
4. `POST /api/rag/query` searches with FTS5, ranks with `bm25()`, and returns `answer`, `sources`, and `keywords`.
5. `POST /api/planning/goal-plan` also retrieves matching sources and shows them as planning references.

## Verify

Backend:

```bash
python -m compileall backend
.\.venv\Scripts\python.exe -m pytest backend/tests
```

Frontend:

```bash
cd apps/web
npx.cmd tsc -b
npm.cmd run lint
npm.cmd run test
npm.cmd run build
```

## API

| Endpoint | Purpose |
| --- | --- |
| `GET /api/health` | Health check |
| `GET /api/plans?date=YYYY-MM-DD` | List plans for one day |
| `POST /api/plans` | Create a plan |
| `PATCH /api/plans/{id}` | Update a plan |
| `DELETE /api/plans/{id}` | Delete a plan |
| `GET /api/month-notes?year=YYYY&month=M` | Read a monthly note |
| `PUT /api/month-notes` | Save a monthly note |
| `GET /api/ai/settings` | Read public model settings without exposing the key |
| `PUT /api/ai/settings` | Save provider, model, base URL, key, temperature, and timeout |
| `POST /api/ai/test` | Test the configured model or mock fallback |
| `POST /api/planning/goal-plan` | Generate and persist a goal plan with optional RAG sources |
| `POST /api/planning/daily-review` | Generate and persist a daily review plus replan preview |
| `GET /api/planning/daily-review?date=YYYY-MM-DD` | Read a saved daily review |
| `POST /api/planning/replan/apply` | Apply preview tasks to the calendar |
| `POST /api/rag/documents` | Save pasted material and build FTS chunks |
| `GET /api/rag/documents` | List knowledge-base documents |
| `DELETE /api/rag/documents/{id}` | Delete a document and its chunks |
| `POST /api/rag/ingest` | Legacy ingest endpoint, still supported |
| `POST /api/rag/query` | Query the local knowledge base and return citations |
| `POST /api/agent/plan` | Generate staged planning output |
| `POST /api/agent/review` | Generate daily review suggestions |
| `POST /api/memory/preferences` | Save preferences |
| `POST /api/eval/planner` | Evaluate planner quality |

## Resume Pitch

独立开发 **MyNotes AI** 学习规划系统，基于 React + TypeScript + Vite 构建前端，使用 FastAPI + SQLite 实现本地数据层，支持日程管理、目标拆解、日报复盘、重排预览、资料库问答、偏好记忆、模型配置和规划质量评估；实现 DeepSeek-first 的 OpenAI-compatible LLM client，并保留 mock fallback，保证无 API key 时也可完整演示；基于 SQLite FTS5/BM25 构建本地 RAG 检索能力，对粘贴资料进行切片、索引、Top-K 召回和引用来源展示，并将检索结果接入目标规划流程。

## License

MIT
