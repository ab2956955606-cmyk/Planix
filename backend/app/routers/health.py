import os

from fastapi import APIRouter

router = APIRouter()

APP_VERSION = os.getenv("MYNOTES_API_VERSION", "2.1.0")


@router.get("/health")
@router.get("/api/health")
def health() -> dict[str, str | int]:
    return {
        "status": "ok",
        "app": "mynotes-api",
        "pid": os.getpid(),
        "version": APP_VERSION,
    }
