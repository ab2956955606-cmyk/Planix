import os
import sqlite3
from pathlib import Path


def resolve_db_path() -> Path:
    database_url = os.getenv("DATABASE_URL", "")
    if database_url.startswith("sqlite:///"):
        return Path(database_url.removeprefix("sqlite:///"))
    return Path("data/mynotes.db")


DB_PATH = resolve_db_path()


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS memories (
          user_id TEXT PRIMARY KEY,
          preferences TEXT NOT NULL,
          updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS rag_chunks (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          title TEXT NOT NULL,
          chunk TEXT NOT NULL,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          kind TEXT NOT NULL,
          payload TEXT NOT NULL,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    return conn


def save_event(kind: str, payload: str) -> None:
    with get_conn() as conn:
        conn.execute("INSERT INTO ai_events(kind, payload) VALUES (?, ?)", (kind, payload))


def save_memory(user_id: str, preferences: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO memories(user_id, preferences, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id)
            DO UPDATE SET preferences = excluded.preferences, updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, preferences),
        )


def load_memory(user_id: str = "local-user") -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT preferences FROM memories WHERE user_id = ?", (user_id,)).fetchone()
    return row["preferences"] if row else ""


def save_chunk(title: str, chunk: str) -> None:
    with get_conn() as conn:
        conn.execute("INSERT INTO rag_chunks(title, chunk) VALUES (?, ?)", (title, chunk))


def list_chunks(limit: int = 200) -> list[dict[str, str]]:
    with get_conn() as conn:
        rows = conn.execute("SELECT title, chunk FROM rag_chunks ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [{"title": row["title"], "chunk": row["chunk"]} for row in rows]
