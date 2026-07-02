import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import get_db_path
from .routers import agent, health, month_notes, planning, plans, preferences, rag, settings

APP_VERSION = "1.1.4"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("mynotes.api")


def create_app() -> FastAPI:
    app = FastAPI(title="MyNotes AI API", version=APP_VERSION)

    #
    # CORS: desktop Tauri webview origin (https://tauri.localhost / tauri://localhost)
    # and Vite dev-server origins. Binding to 127.0.0.1 means only local processes
    # can reach the API, so allowing all origins is safe — no external access.
    #
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "https://tauri.localhost",
            "tauri://localhost",
        ],
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

    logger.info("MyNotes AI API started version=%s db_path=%s", APP_VERSION, get_db_path())
    return app


app = create_app()
