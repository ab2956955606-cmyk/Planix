import os
from dataclasses import dataclass

from ..db import get_conn
from ..schemas import AiSettingsOut, AiSettingsUpdate


SETTINGS_ID = "local-default"


@dataclass(frozen=True)
class EffectiveAiSettings:
    provider: str
    base_url: str
    model: str
    api_key: str
    temperature: float
    timeout_seconds: int
    updated_at: str

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key.strip())


def _env_provider() -> str:
    provider = os.getenv("AI_PROVIDER", "deepseek").strip() or "deepseek"
    return provider if provider in {"mock", "deepseek", "openai", "custom"} else "custom"


def _env_base_url() -> str:
    return os.getenv("AI_API_BASE", "https://api.deepseek.com").strip() or "https://api.deepseek.com"


def _env_model() -> str:
    return os.getenv("AI_MODEL", "deepseek-v4-flash").strip() or "deepseek-v4-flash"


def _env_api_key() -> str:
    return os.getenv("AI_API_KEY", "").strip()


def _row_to_effective(row) -> EffectiveAiSettings:
    if row:
        return EffectiveAiSettings(
            provider=row["provider"],
            base_url=row["base_url"],
            model=row["model"],
            api_key=row["api_key_encrypted"] or _env_api_key(),
            temperature=float(row["temperature"]),
            timeout_seconds=int(row["timeout_seconds"]),
            updated_at=row["updated_at"],
        )
    return EffectiveAiSettings(
        provider=_env_provider(),
        base_url=_env_base_url(),
        model=_env_model(),
        api_key=_env_api_key(),
        temperature=0.3,
        timeout_seconds=40,
        updated_at="",
    )


def _to_public(settings: EffectiveAiSettings) -> AiSettingsOut:
    return AiSettingsOut(
        provider=settings.provider,
        baseUrl=settings.base_url,
        model=settings.model,
        hasApiKey=settings.has_api_key,
        temperature=settings.temperature,
        timeoutSeconds=settings.timeout_seconds,
        updatedAt=settings.updated_at,
    )


def get_effective_ai_settings() -> EffectiveAiSettings:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM ai_settings WHERE id = ?", (SETTINGS_ID,)).fetchone()
    return _row_to_effective(row)


def get_public_ai_settings() -> AiSettingsOut:
    return _to_public(get_effective_ai_settings())


def save_ai_settings(payload: AiSettingsUpdate) -> AiSettingsOut:
    current = get_effective_ai_settings()
    api_key = current.api_key if payload.api_key is None else payload.api_key.strip()
    with get_conn() as conn:
        row = conn.execute(
            """
            INSERT INTO ai_settings(
              id, provider, base_url, model, api_key_encrypted,
              temperature, timeout_seconds, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id)
            DO UPDATE SET
              provider = excluded.provider,
              base_url = excluded.base_url,
              model = excluded.model,
              api_key_encrypted = excluded.api_key_encrypted,
              temperature = excluded.temperature,
              timeout_seconds = excluded.timeout_seconds,
              updated_at = CURRENT_TIMESTAMP
            RETURNING *
            """,
            (
                SETTINGS_ID,
                payload.provider,
                payload.base_url.strip().rstrip("/") or "https://api.deepseek.com",
                payload.model.strip() or "deepseek-v4-flash",
                api_key,
                payload.temperature,
                payload.timeout_seconds,
            ),
        ).fetchone()
    return _to_public(_row_to_effective(row))
