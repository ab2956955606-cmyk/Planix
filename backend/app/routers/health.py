import os

from fastapi import APIRouter

router = APIRouter()

APP_VERSION = os.getenv("PLANIX_API_VERSION", "1.1.4")


@router.get("/health")
@router.get("/api/health")
def health() -> dict[str, str | int]:
    return {
        "status": "ok",
        "app": "planix-api",
        "pid": os.getpid(),
        "version": APP_VERSION,
    }
