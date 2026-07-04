import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import get_db_path
from .routers import agent, health, maintenance, materials, month_notes, planning, plans, preferences, rag, runtime, settings

APP_VERSION = "1.1.4"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("planix.api")


def create_app() -> FastAPI:
    app = FastAPI(title="Planix API", version=APP_VERSION)

    allowed_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://tauri.localhost",
        "https://tauri.localhost",
        "tauri://localhost",
    ]

    # Scope CORS to local Vite dev/preview and Tauri/WebView2 origins. Desktop
    # production requests normally go through the Rust IPC proxy, but keeping
    # these origins listed makes local diagnostics work without using "*".
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1):\d+$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(plans.router)
    app.include_router(month_notes.router)
    app.include_router(planning.router)
    app.include_router(agent.router)
    app.include_router(runtime.router)
    app.include_router(rag.router)
    app.include_router(materials.router)
    app.include_router(preferences.router)
    app.include_router(settings.router)
    app.include_router(maintenance.router)

    logger.info("Planix API started version=%s db_path=%s", APP_VERSION, get_db_path())
    return app


app = create_app()
