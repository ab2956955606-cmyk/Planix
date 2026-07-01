# AGENTS.md - MyNotes AI

## Project Overview

MyNotes AI is an AI learning planner and daily review system. The long-term target is a polished Windows desktop application that demonstrates AI application engineering for internship applications.

The project is being rebuilt in stages:

- Frontend: React + TypeScript + Vite in `apps/web`
- Backend: FastAPI in `backend/app`
- Database: SQLite as the primary backend data store, including FTS5/BM25 for local RAG
- AI: DeepSeek-first OpenAI-compatible client with mock fallback and source-grounded RAG
- Desktop roadmap: Tauri shell + PyInstaller sidecar + GitHub Release

## Current Entry Points

- Frontend entry: `apps/web/MyNotes.html`
- Frontend app: `apps/web/src/App.tsx`
- Backend app: `backend/app/main.py`
- API routers: `backend/app/routers`
- Backend services: `backend/app/services`
- SQLite layer: `backend/app/db.py`
- Tests: `backend/tests`

## Commands

Frontend:

```bash
cd apps/web
npm install
npm run dev
npm run build
npm run test
npm run lint
```

Backend:

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
pytest backend/tests
```

## Code Conventions

- Keep frontend features inside `apps/web/src/components`, `apps/web/src/lib`, or `apps/web/src/utils`.
- Do not restore the old root-level HTML/CSS/JS structure.
- Keep API schema definitions in `backend/app/schemas.py`.
- Keep route definitions in `backend/app/routers`.
- Keep business logic in `backend/app/services`.
- Keep AI features demoable without an API key.
- Do not expose API keys in read endpoints or logs.
- Do not commit `.env`, `.venv`, `node_modules`, `dist`, `data`, cache files, or generated build output.

## User Preference

- Reply in Chinese.
- Favor clean, practical, portfolio-quality engineering.
- Keep changes staged by project phase and verify before reporting completion.
