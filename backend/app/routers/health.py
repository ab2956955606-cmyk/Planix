import os

from fastapi import APIRouter

router = APIRouter()

APP_VERSION = os.getenv("MYNOTES_API_VERSION", "1.1.4")


@router.get("/health")
@router.get("/api/health")
def health() -> dict[str, str | int]:
    return {
        "status": "ok",
        "app": "mynotes-api",
        "pid": os.getpid(),
        "version": APP_VERSION,
    }
