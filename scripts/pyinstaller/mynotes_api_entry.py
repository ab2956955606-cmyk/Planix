import os
import tempfile
import traceback
from pathlib import Path

import uvicorn

from backend.app.main import app


def log_path() -> Path:
    explicit = os.getenv("MYNOTES_API_LOG")
    if explicit:
        return Path(explicit)
    return Path(tempfile.gettempdir()) / "mynotes-api.log"


def write_log(message: str) -> None:
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(message.rstrip() + "\n")


def main() -> None:
    os.environ.setdefault("MYNOTES_ENV", "desktop")
    if os.getenv("MYNOTES_ENV") == "desktop":
        os.environ.setdefault("USE_REAL_LLM", "1")
    port = int(os.getenv("MYNOTES_API_PORT", "8000"))
    write_log(f"Starting MyNotes API sidecar on 127.0.0.1:{port}")
    try:
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="info", log_config=None)
    except Exception:
        write_log(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
