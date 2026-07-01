# CLAUDE.md - MyNotes AI

## Project Positioning

MyNotes AI is an AI learning planner, daily review, and personal knowledge assistant. It is intended to become a strong AI application / full-stack internship portfolio project, not just a static planner page.

Current stack:

- React + TypeScript + Vite frontend in `apps/web`
- FastAPI backend in `backend/app`
- SQLite primary data layer with FTS5/BM25 local RAG
- DeepSeek-first OpenAI-compatible LLM client with mock fallback and source citations

## Run

Frontend:

```bash
cd apps/web
npm install
npm run dev
```

Backend:

```bash
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```

Open:

```text
http://127.0.0.1:5173/index.html
```

## Verify

```bash
python -m compileall backend
pytest backend/tests
```

```bash
cd apps/web
npm run build
npm run test
npm run lint
```

## Development Rules

- Keep the Vite entry file as `apps/web/index.html`.
- Keep backend routes under `/api/*`, except `/health` for simple checks.
- Store core planning data in SQLite through FastAPI.
- Preserve localStorage fallback for frontend-only demos.
- Preserve mock fallback for AI features until the real provider is configured.
- Never return saved API keys from read endpoints.
- Update README whenever the project stage, startup flow, or resume value changes.
