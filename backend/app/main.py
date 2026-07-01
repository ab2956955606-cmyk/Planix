from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import agent, health, month_notes, planning, plans, preferences, rag, settings


def create_app() -> FastAPI:
    app = FastAPI(title="MyNotes AI API", version="2.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(plans.router)
    app.include_router(month_notes.router)
    app.include_router(planning.router)
    app.include_router(agent.router)
    app.include_router(rag.router)
    app.include_router(preferences.router)
    app.include_router(settings.router)
    return app


app = create_app()
