import sqlite3
from pathlib import Path
from uuid import uuid4

from .desktop_paths import resolve_database_path


def get_db_path() -> Path:
    return resolve_database_path()


def get_conn() -> sqlite3.Connection:
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS plans (
          id TEXT PRIMARY KEY,
          date TEXT NOT NULL,
          time TEXT NOT NULL DEFAULT '09:00',
          content TEXT NOT NULL,
          done INTEGER NOT NULL DEFAULT 0,
          result TEXT NOT NULL DEFAULT '',
          priority TEXT NOT NULL DEFAULT 'medium',
          estimated_minutes INTEGER NOT NULL DEFAULT 30,
          source TEXT NOT NULL DEFAULT 'manual',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_plans_date_time
          ON plans(date, time);

        CREATE TABLE IF NOT EXISTS month_notes (
          year INTEGER NOT NULL,
          month INTEGER NOT NULL,
          content TEXT NOT NULL DEFAULT '',
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY(year, month)
        );

        CREATE TABLE IF NOT EXISTS daily_reviews (
          id TEXT PRIMARY KEY,
          date TEXT NOT NULL UNIQUE,
          summary TEXT NOT NULL,
          suggestions TEXT NOT NULL DEFAULT '[]',
          done_count INTEGER NOT NULL DEFAULT 0,
          total_count INTEGER NOT NULL DEFAULT 0,
          suggestions_json TEXT NOT NULL DEFAULT '[]',
          replan_tasks_json TEXT NOT NULL DEFAULT '[]',
          target_date TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS planning_goals (
          id TEXT PRIMARY KEY,
          goal TEXT NOT NULL,
          deadline TEXT NOT NULL DEFAULT '',
          daily_hours REAL NOT NULL DEFAULT 2,
          materials TEXT NOT NULL DEFAULT '',
          preferences TEXT NOT NULL DEFAULT '',
          summary TEXT NOT NULL DEFAULT '',
          phases_json TEXT NOT NULL DEFAULT '[]',
          tasks_json TEXT NOT NULL DEFAULT '[]',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS ai_settings (
          id TEXT PRIMARY KEY,
          provider TEXT NOT NULL DEFAULT 'deepseek',
          base_url TEXT NOT NULL DEFAULT 'https://api.deepseek.com',
          model TEXT NOT NULL DEFAULT 'deepseek-v4-flash',
          api_key_encrypted TEXT NOT NULL DEFAULT '',
          temperature REAL NOT NULL DEFAULT 0.3,
          timeout_seconds INTEGER NOT NULL DEFAULT 40,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS user_preferences (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS documents (
          id TEXT PRIMARY KEY,
          title TEXT NOT NULL,
          source TEXT NOT NULL DEFAULT 'manual',
          source_type TEXT NOT NULL DEFAULT 'paste',
          summary TEXT NOT NULL DEFAULT '',
          content_hash TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS document_chunks (
          id TEXT PRIMARY KEY,
          document_id TEXT NOT NULL,
          chunk_index INTEGER NOT NULL,
          content TEXT NOT NULL,
          token_count INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id
          ON document_chunks(document_id);

        CREATE VIRTUAL TABLE IF NOT EXISTS document_chunks_fts
          USING fts5(
            chunk_id UNINDEXED,
            document_id UNINDEXED,
            title,
            content,
            tokenize = 'unicode61'
          );

        CREATE TABLE IF NOT EXISTS ai_runs (
          id TEXT PRIMARY KEY,
          feature TEXT NOT NULL,
          provider TEXT NOT NULL DEFAULT 'mock',
          model TEXT NOT NULL DEFAULT 'local-rule',
          input_summary TEXT NOT NULL DEFAULT '',
          output_summary TEXT NOT NULL DEFAULT '',
          success INTEGER NOT NULL DEFAULT 1,
          error TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    ensure_column(conn, "ai_settings", "temperature", "REAL NOT NULL DEFAULT 0.3")
    ensure_column(conn, "ai_settings", "timeout_seconds", "INTEGER NOT NULL DEFAULT 40")
    ensure_column(conn, "daily_reviews", "done_count", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(conn, "daily_reviews", "total_count", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(conn, "daily_reviews", "suggestions_json", "TEXT NOT NULL DEFAULT '[]'")
    ensure_column(conn, "daily_reviews", "replan_tasks_json", "TEXT NOT NULL DEFAULT '[]'")
    ensure_column(conn, "daily_reviews", "target_date", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "documents", "source_type", "TEXT NOT NULL DEFAULT 'paste'")
    ensure_column(conn, "documents", "summary", "TEXT NOT NULL DEFAULT ''")
    conn.execute(
        """
        INSERT INTO document_chunks_fts(chunk_id, document_id, title, content)
        SELECT c.id, c.document_id, d.title, c.content
        FROM document_chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE NOT EXISTS (
          SELECT 1 FROM document_chunks_fts f WHERE f.chunk_id = c.id
        )
        """
    )


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def row_to_dict(row: sqlite3.Row | None) -> dict[str, object] | None:
    return dict(row) if row else None


def save_event(kind: str, payload: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO ai_runs(id, feature, input_summary, output_summary)
            VALUES (?, ?, ?, ?)
            """,
            (str(uuid4()), kind, payload[:4000], payload[:4000]),
        )


def save_memory(user_id: str, preferences: str) -> None:
    key = f"preferences:{user_id}"
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO user_preferences(key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key)
            DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
            """,
            (key, preferences),
        )


def load_memory(user_id: str = "local-user") -> str:
    key = f"preferences:{user_id}"
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM user_preferences WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else ""


def save_chunk(title: str, chunk: str) -> None:
    with get_conn() as conn:
        doc = conn.execute("SELECT id FROM documents WHERE title = ? ORDER BY created_at DESC LIMIT 1", (title,)).fetchone()
        document_id = doc["id"] if doc else str(uuid4())
        if not doc:
            conn.execute(
                "INSERT INTO documents(id, title, source) VALUES (?, ?, ?)",
                (document_id, title, "manual"),
            )
        chunk_index = conn.execute(
            "SELECT COUNT(*) AS total FROM document_chunks WHERE document_id = ?",
            (document_id,),
        ).fetchone()["total"]
        conn.execute(
            """
            INSERT INTO document_chunks(id, document_id, chunk_index, content, token_count)
            VALUES (?, ?, ?, ?, ?)
            """,
            (chunk_id := str(uuid4()), document_id, chunk_index, chunk, len(chunk.split())),
        )
        conn.execute(
            """
            INSERT INTO document_chunks_fts(chunk_id, document_id, title, content)
            VALUES (?, ?, ?, ?)
            """,
            (chunk_id, document_id, title, chunk),
        )


def list_chunks(limit: int = 200) -> list[dict[str, str]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT documents.title, document_chunks.content AS chunk
            FROM document_chunks
            JOIN documents ON documents.id = document_chunks.document_id
            ORDER BY document_chunks.created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [{"title": row["title"], "chunk": row["chunk"]} for row in rows]
