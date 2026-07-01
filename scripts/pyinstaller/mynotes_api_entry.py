import os

import uvicorn


def main() -> None:
    os.environ.setdefault("MYNOTES_ENV", "desktop")
    port = int(os.getenv("MYNOTES_API_PORT", "8000"))
    uvicorn.run(
        "backend.app.main:app",
        host="127.0.0.1",
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
