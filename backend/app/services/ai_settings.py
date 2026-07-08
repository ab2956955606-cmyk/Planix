import os
import json
import re
from dataclasses import dataclass

from ..db import get_conn
from ..schemas import AiModelRoutingRule, AiModelRoutingUpdate, AiProvider, AiSavedProvider, AiSettingsOut, AiSettingsUpdate


SETTINGS_ID = "local-default"
SUPPORTED_PROVIDERS = {"mock", "deepseek", "kimi", "zhipu_glm", "openai", "custom"}
KEYED_PROVIDERS = {"deepseek", "kimi", "zhipu_glm", "openai", "custom"}
PROVIDER_ORDER = ["deepseek", "kimi", "zhipu_glm", "openai", "custom"]
ROUTABLE_TASK_TYPES = [
    "command_decision",
    "plan_generation",
    "task_refinement",
    "calendar_patch",
    "memory_query",
    "memory_write",
    "chat",
    "model_knowledge",
]
LEGACY_ROUTING_TASK_ALIASES = {
    "note_query": "memory_query",
    "note_write": "memory_write",
}
DEFAULT_BASE_URLS = {
    "mock": "https://api.deepseek.com",
    "deepseek": "https://api.deepseek.com",
    "kimi": "https://api.moonshot.ai/v1",
    "zhipu_glm": "https://open.bigmodel.cn/api/paas/v4",
    "openai": "https://api.openai.com/v1",
    "custom": "",
}
DEFAULT_MODELS = {
    "mock": "deepseek-v4-flash",
    "deepseek": "deepseek-v4-flash",
    "kimi": "kimi-k2.7-code",
    "zhipu_glm": "glm-4-flash",
    "openai": "gpt-4o-mini",
    "custom": "gpt-4o-mini",
}


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


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    base_url: str
    model: str
    api_key: str
    api_key_source: str
    updated_at: str

    @property
    def has_api_key(self) -> bool:
        return self.api_key_source == "user" and bool(self.api_key.strip())


@dataclass(frozen=True)
class PendingProviderConfig:
    provider: str
    base_url: str
    model: str
    api_key: str
    api_key_source: str
    should_validate: bool


@dataclass(frozen=True)
class ModelRoutingRuleConfig:
    task_type: str
    primary_provider: str
    fallback_providers: tuple[str, ...]
    local_fallback_enabled: bool
    updated_at: str = ""


class AiSettingsSaveValidationError(Exception):
    def __init__(
        self,
        *,
        message: str,
        error_type: str,
        provider: str,
        model: str,
        status_code: int = 0,
    ):
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.provider = provider
        self.model = model
        self.status_code = status_code

    def to_detail(self) -> dict[str, object]:
        return {
            "errorType": self.error_type,
            "provider": self.provider,
            "model": self.model,
            "message": self.message,
            "statusCode": self.status_code,
        }


def _env_provider() -> str:
    provider = os.getenv("AI_PROVIDER", "deepseek").strip() or "deepseek"
    return provider if provider in SUPPORTED_PROVIDERS else "custom"


def _default_base_url(provider: str) -> str:
    return DEFAULT_BASE_URLS.get(provider) or "https://api.deepseek.com"


def _default_model(provider: str) -> str:
    return DEFAULT_MODELS.get(provider, "deepseek-v4-flash")


def normalize_routing_task_type(task_type: str) -> str:
    return LEGACY_ROUTING_TASK_ALIASES.get(task_type, task_type)


def _env_base_url() -> str:
    provider = _env_provider()
    default = _default_base_url(provider)
    return os.getenv("AI_API_BASE", default).strip() or default


def _env_model() -> str:
    provider = _env_provider()
    default = _default_model(provider)
    return os.getenv("AI_MODEL", default).strip() or default


def _env_api_key() -> str:
    provider = _env_provider()
    provider_key = {
        "deepseek": "DEEPSEEK_API_KEY",
        "kimi": "MOONSHOT_API_KEY",
        "zhipu_glm": "ZHIPU_API_KEY",
        "openai": "OPENAI_API_KEY",
    }.get(provider)
    if provider_key:
        return (os.getenv(provider_key) or os.getenv("AI_API_KEY") or "").strip()
    return (os.getenv("AI_API_KEY") or "").strip()


def _row_to_provider_config(row) -> ProviderConfig | None:
    if not row:
        return None
    provider = row["provider"]
    return ProviderConfig(
        provider=provider,
        base_url=row["base_url"] or _default_base_url(provider),
        model=row["model"] or _default_model(provider),
        api_key=row["api_key_encrypted"] if row["api_key_source"] == "user" else "",
        api_key_source=row["api_key_source"],
        updated_at=row["updated_at"],
    )


def _config_for_provider(conn, provider: str) -> ProviderConfig | None:
    row = conn.execute("SELECT * FROM ai_provider_configs WHERE provider = ?", (provider,)).fetchone()
    return _row_to_provider_config(row)


def _saved_provider_rows(conn) -> list[AiSavedProvider]:
    rows = conn.execute("SELECT * FROM ai_provider_configs").fetchall()
    configs = [_row_to_provider_config(row) for row in rows]
    configs = [config for config in configs if config and config.provider in KEYED_PROVIDERS]
    order = {provider: index for index, provider in enumerate(PROVIDER_ORDER)}
    configs.sort(key=lambda item: order.get(item.provider, 999))
    return [
        AiSavedProvider(
            provider=config.provider,
            baseUrl=config.base_url,
            model=config.model,
            hasApiKey=config.has_api_key,
            updatedAt=config.updated_at,
        )
        for config in configs
    ]


def _routing_primary_for_active(active_provider: str) -> str:
    return active_provider if active_provider in KEYED_PROVIDERS else "deepseek"


def _default_routing_rule_configs(active_provider: str) -> list[ModelRoutingRuleConfig]:
    primary = _routing_primary_for_active(active_provider)
    fallback = ("deepseek",) if primary != "deepseek" else ()
    return [
        ModelRoutingRuleConfig(
            task_type=task_type,
            primary_provider=primary,
            fallback_providers=fallback,
            local_fallback_enabled=True,
        )
        for task_type in ROUTABLE_TASK_TYPES
    ]


def _routing_row_to_config(row) -> ModelRoutingRuleConfig | None:
    if not row:
        return None
    try:
        raw_fallbacks = json.loads(row["fallback_providers_json"] or "[]")
    except json.JSONDecodeError:
        raw_fallbacks = []
    fallbacks: list[str] = []
    if isinstance(raw_fallbacks, list):
        for provider in raw_fallbacks:
            if provider in KEYED_PROVIDERS and provider not in fallbacks:
                fallbacks.append(provider)
            if len(fallbacks) >= 2:
                break
    primary = row["primary_provider"] if row["primary_provider"] in KEYED_PROVIDERS else "deepseek"
    fallbacks = [provider for provider in fallbacks if provider != primary]
    task_type = normalize_routing_task_type(row["task_type"])
    return ModelRoutingRuleConfig(
        task_type=task_type,
        primary_provider=primary,
        fallback_providers=tuple(fallbacks),
        local_fallback_enabled=bool(row["local_fallback_enabled"]),
        updated_at=row["updated_at"],
    )


def _routing_config_to_public(rule: ModelRoutingRuleConfig) -> AiModelRoutingRule:
    return AiModelRoutingRule(
        taskType=rule.task_type,
        primaryProvider=rule.primary_provider,
        fallbackProviders=list(rule.fallback_providers),
        localFallbackEnabled=rule.local_fallback_enabled,
        updatedAt=rule.updated_at,
    )


def _ensure_default_routing_rules(conn) -> None:
    count = conn.execute("SELECT COUNT(*) AS count FROM ai_model_routing_rules").fetchone()["count"]
    if count:
        return
    settings_row = conn.execute("SELECT * FROM ai_settings WHERE id = ?", (SETTINGS_ID,)).fetchone()
    active_provider = settings_row["provider"] if settings_row else _env_provider()
    for rule in _default_routing_rule_configs(active_provider):
        conn.execute(
            """
            INSERT INTO ai_model_routing_rules(
              task_type, primary_provider, fallback_providers_json, local_fallback_enabled, updated_at
            )
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                rule.task_type,
                rule.primary_provider,
                json.dumps(list(rule.fallback_providers)),
                int(rule.local_fallback_enabled),
            ),
        )


def _routing_rule_rows(conn) -> list[AiModelRoutingRule]:
    _ensure_default_routing_rules(conn)
    rows = conn.execute("SELECT * FROM ai_model_routing_rules ORDER BY task_type").fetchall()
    by_task: dict[str, ModelRoutingRuleConfig] = {}
    for row in rows:
        config = _routing_row_to_config(row)
        if not config or config.task_type not in ROUTABLE_TASK_TYPES:
            continue
        is_legacy_alias = row["task_type"] in LEGACY_ROUTING_TASK_ALIASES
        if is_legacy_alias and config.task_type in by_task:
            continue
        by_task[config.task_type] = config
    settings_row = conn.execute("SELECT * FROM ai_settings WHERE id = ?", (SETTINGS_ID,)).fetchone()
    active_provider = settings_row["provider"] if settings_row else _env_provider()
    defaults = {rule.task_type: rule for rule in _default_routing_rule_configs(active_provider)}
    rules = [by_task.get(task_type) or defaults[task_type] for task_type in ROUTABLE_TASK_TYPES]
    return [_routing_config_to_public(rule) for rule in rules]


def _env_effective() -> EffectiveAiSettings:
    return EffectiveAiSettings(
        provider=_env_provider(),
        base_url=_env_base_url(),
        model=_env_model(),
        api_key=_env_api_key(),
        temperature=0.3,
        timeout_seconds=40,
        updated_at="",
    )


def _effective_from_rows(settings_row, config: ProviderConfig | None) -> EffectiveAiSettings:
    if not settings_row:
        return _env_effective()
    provider = settings_row["provider"] if settings_row["provider"] in SUPPORTED_PROVIDERS else "custom"
    base_url = settings_row["base_url"] or _default_base_url(provider)
    model = settings_row["model"] or _default_model(provider)
    api_key = ""
    if config:
        base_url = config.base_url
        model = config.model
        api_key = config.api_key if config.has_api_key else ""
    elif settings_row["api_key_source"] == "user":
        api_key = settings_row["api_key_encrypted"]
    return EffectiveAiSettings(
        provider=provider,
        base_url=base_url,
        model=model,
        api_key=api_key,
        temperature=float(settings_row["temperature"]),
        timeout_seconds=int(settings_row["timeout_seconds"]),
        updated_at=settings_row["updated_at"],
    )


def _to_public(
    settings: EffectiveAiSettings,
    saved_providers: list[AiSavedProvider],
    routing_rules: list[AiModelRoutingRule],
) -> AiSettingsOut:
    return AiSettingsOut(
        provider=settings.provider,
        baseUrl=settings.base_url,
        model=settings.model,
        hasApiKey=settings.has_api_key,
        temperature=settings.temperature,
        timeoutSeconds=settings.timeout_seconds,
        updatedAt=settings.updated_at,
        savedProviders=saved_providers,
        routingRules=routing_rules,
    )


def get_effective_ai_settings() -> EffectiveAiSettings:
    with get_conn() as conn:
        settings_row = conn.execute("SELECT * FROM ai_settings WHERE id = ?", (SETTINGS_ID,)).fetchone()
        provider = settings_row["provider"] if settings_row else _env_provider()
        config = _config_for_provider(conn, provider) if provider in KEYED_PROVIDERS else None
    return _effective_from_rows(settings_row, config)


def get_effective_ai_settings_for_provider(provider: str, active_settings: EffectiveAiSettings | None = None) -> EffectiveAiSettings:
    with get_conn() as conn:
        settings_row = conn.execute("SELECT * FROM ai_settings WHERE id = ?", (SETTINGS_ID,)).fetchone()
        active = active_settings or _effective_from_rows(
            settings_row,
            _config_for_provider(conn, settings_row["provider"]) if settings_row and settings_row["provider"] in KEYED_PROVIDERS else None,
        )
        if provider not in KEYED_PROVIDERS:
            return EffectiveAiSettings(
                provider=provider,
                base_url=_default_base_url(provider),
                model=_default_model(provider),
                api_key="",
                temperature=active.temperature,
                timeout_seconds=active.timeout_seconds,
                updated_at=active.updated_at,
            )
        config = _config_for_provider(conn, provider)
        return EffectiveAiSettings(
            provider=provider,
            base_url=config.base_url if config else _default_base_url(provider),
            model=config.model if config else _default_model(provider),
            api_key=config.api_key if config and config.has_api_key else "",
            temperature=active.temperature,
            timeout_seconds=active.timeout_seconds,
            updated_at=config.updated_at if config else active.updated_at,
        )


def get_model_routing_rule(task_type: str, active_provider: str) -> ModelRoutingRuleConfig:
    task_type = normalize_routing_task_type(task_type)
    if task_type not in ROUTABLE_TASK_TYPES:
        primary = _routing_primary_for_active(active_provider)
        return ModelRoutingRuleConfig(
            task_type=task_type,
            primary_provider=primary,
            fallback_providers=("deepseek",) if primary != "deepseek" else (),
            local_fallback_enabled=True,
        )
    with get_conn() as conn:
        _ensure_default_routing_rules(conn)
        row = conn.execute("SELECT * FROM ai_model_routing_rules WHERE task_type = ?", (task_type,)).fetchone()
        if not row:
            legacy_task = next((legacy for legacy, canonical in LEGACY_ROUTING_TASK_ALIASES.items() if canonical == task_type), "")
            if legacy_task:
                row = conn.execute("SELECT * FROM ai_model_routing_rules WHERE task_type = ?", (legacy_task,)).fetchone()
        config = _routing_row_to_config(row)
    if config:
        return config
    primary = _routing_primary_for_active(active_provider)
    return ModelRoutingRuleConfig(
        task_type=task_type,
        primary_provider=primary,
        fallback_providers=("deepseek",) if primary != "deepseek" else (),
        local_fallback_enabled=True,
    )


def get_public_ai_settings() -> AiSettingsOut:
    with get_conn() as conn:
        settings_row = conn.execute("SELECT * FROM ai_settings WHERE id = ?", (SETTINGS_ID,)).fetchone()
        provider = settings_row["provider"] if settings_row else _env_provider()
        config = _config_for_provider(conn, provider) if provider in KEYED_PROVIDERS else None
        settings = _effective_from_rows(settings_row, config)
        saved_providers = _saved_provider_rows(conn)
        routing_rules = _routing_rule_rows(conn)
    return _to_public(settings, saved_providers, routing_rules)


def _redact_sensitive_error_text(value: str, api_key: str) -> str:
    text = value or ""
    if api_key:
        text = text.replace(api_key, "[redacted]")
    return re.sub(r"Bearer\s+[^,\s]+", "Bearer [redacted]", text, flags=re.IGNORECASE)


def _candidate_provider_config(conn, payload: AiSettingsUpdate) -> PendingProviderConfig:
    provider = payload.provider
    base_url = payload.base_url.strip().rstrip("/") or _default_base_url(provider)
    model = payload.model.strip() or _default_model(provider)
    existing = _config_for_provider(conn, provider)
    if payload.api_key is None:
        api_key = existing.api_key if existing and existing.has_api_key else ""
        api_key_source = "user" if api_key else ""
        should_validate = bool(
            api_key
            and existing
            and (base_url != existing.base_url or model != existing.model)
        )
    else:
        api_key = payload.api_key.strip()
        api_key_source = "user" if api_key else ""
        should_validate = bool(api_key)
    return PendingProviderConfig(
        provider=provider,
        base_url=base_url,
        model=model,
        api_key=api_key,
        api_key_source=api_key_source,
        should_validate=should_validate,
    )


def _validate_provider_config(candidate: PendingProviderConfig, *, temperature: float, timeout_seconds: int) -> None:
    if not candidate.should_validate:
        return
    from .model_provider import ModelCallRequest, ModelRouter

    settings = EffectiveAiSettings(
        provider=candidate.provider,
        base_url=candidate.base_url,
        model=candidate.model,
        api_key=candidate.api_key,
        temperature=temperature,
        timeout_seconds=timeout_seconds,
        updated_at="",
    )
    result, error = ModelRouter(settings, routing_enabled=False).complete(
        ModelCallRequest(
            task_type="settings_test",
            feature="settings_save_validation",
            system="You are a concise health-check assistant. Reply with OK.",
            user="Reply OK.",
            max_tokens=16,
            temperature=None if candidate.provider == "kimi" else 0,
            timeout_seconds=timeout_seconds,
            max_token_cap=16,
        )
    )
    if error:
        raise AiSettingsSaveValidationError(
            message=_redact_sensitive_error_text(error.message, candidate.api_key),
            error_type=error.error_type,
            provider=candidate.provider,
            model=candidate.model,
            status_code=error.status_code,
        )
    if not result or result.mode != "llm":
        raise AiSettingsSaveValidationError(
            message="Model validation failed before saving settings.",
            error_type="unknown",
            provider=candidate.provider,
            model=candidate.model,
        )


def _upsert_provider_config(conn, candidate: PendingProviderConfig) -> tuple[str, str]:
    conn.execute(
        """
        INSERT INTO ai_provider_configs(
          provider, base_url, model, api_key_encrypted, api_key_source, updated_at
        )
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(provider)
        DO UPDATE SET
          base_url = excluded.base_url,
          model = excluded.model,
          api_key_encrypted = excluded.api_key_encrypted,
          api_key_source = excluded.api_key_source,
          updated_at = CURRENT_TIMESTAMP
        """,
        (candidate.provider, candidate.base_url, candidate.model, candidate.api_key, candidate.api_key_source),
    )
    return candidate.api_key, candidate.api_key_source


def save_ai_settings(payload: AiSettingsUpdate) -> AiSettingsOut:
    with get_conn() as conn:
        if payload.provider == "mock":
            base_url = payload.base_url.strip().rstrip("/") or _default_base_url(payload.provider)
            model = payload.model.strip() or _default_model(payload.provider)
            api_key = ""
            api_key_source = ""
        else:
            candidate = _candidate_provider_config(conn, payload)
            if candidate.should_validate:
                _validate_provider_config(
                    candidate,
                    temperature=payload.temperature,
                    timeout_seconds=payload.timeout_seconds,
                )
            api_key, api_key_source = _upsert_provider_config(conn, candidate)
            base_url = candidate.base_url
            model = candidate.model

        conn.execute(
            """
            INSERT INTO ai_settings(
              id, provider, base_url, model, api_key_encrypted, api_key_source,
              temperature, timeout_seconds, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id)
            DO UPDATE SET
              provider = excluded.provider,
              base_url = excluded.base_url,
              model = excluded.model,
              api_key_encrypted = excluded.api_key_encrypted,
              api_key_source = excluded.api_key_source,
              temperature = excluded.temperature,
              timeout_seconds = excluded.timeout_seconds,
              updated_at = CURRENT_TIMESTAMP
            """,
            (
                SETTINGS_ID,
                payload.provider,
                base_url,
                model,
                api_key,
                api_key_source,
                payload.temperature,
                payload.timeout_seconds,
            ),
        )
    return get_public_ai_settings()


def save_model_routing_rules(payload: AiModelRoutingUpdate) -> AiSettingsOut:
    incoming = {normalize_routing_task_type(rule.task_type): rule for rule in payload.routing_rules}
    unknown_tasks = set(incoming) - set(ROUTABLE_TASK_TYPES)
    if unknown_tasks:
        raise ValueError(f"Unsupported routing task type: {sorted(unknown_tasks)[0]}")
    with get_conn() as conn:
        settings_row = conn.execute("SELECT * FROM ai_settings WHERE id = ?", (SETTINGS_ID,)).fetchone()
        active_provider = settings_row["provider"] if settings_row else _env_provider()
        defaults = {rule.task_type: rule for rule in _default_routing_rule_configs(active_provider)}
        for legacy_task in LEGACY_ROUTING_TASK_ALIASES:
            conn.execute("DELETE FROM ai_model_routing_rules WHERE task_type = ?", (legacy_task,))
        for task_type in ROUTABLE_TASK_TYPES:
            rule = incoming.get(task_type)
            if rule:
                primary = rule.primary_provider
                fallbacks = [provider for provider in rule.fallback_providers if provider != primary]
                local_fallback_enabled = rule.local_fallback_enabled
            else:
                default = defaults[task_type]
                primary = default.primary_provider
                fallbacks = list(default.fallback_providers)
                local_fallback_enabled = default.local_fallback_enabled
            conn.execute(
                """
                INSERT INTO ai_model_routing_rules(
                  task_type, primary_provider, fallback_providers_json, local_fallback_enabled, updated_at
                )
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(task_type)
                DO UPDATE SET
                  primary_provider = excluded.primary_provider,
                  fallback_providers_json = excluded.fallback_providers_json,
                  local_fallback_enabled = excluded.local_fallback_enabled,
                  updated_at = CURRENT_TIMESTAMP
                """,
                (
                    task_type,
                    primary,
                    json.dumps(fallbacks[:2]),
                    int(local_fallback_enabled),
                ),
            )
    return get_public_ai_settings()


def delete_provider_api_key(provider: AiProvider | str) -> AiSettingsOut:
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Unsupported provider: {provider}")
    with get_conn() as conn:
        if provider in KEYED_PROVIDERS:
            existing = _config_for_provider(conn, provider)
            if existing:
                conn.execute(
                    """
                    UPDATE ai_provider_configs
                    SET api_key_encrypted = '', api_key_source = '', updated_at = CURRENT_TIMESTAMP
                    WHERE provider = ?
                    """,
                    (provider,),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO ai_provider_configs(
                      provider, base_url, model, api_key_encrypted, api_key_source, updated_at
                    )
                    VALUES (?, ?, ?, '', '', CURRENT_TIMESTAMP)
                    """,
                    (provider, _default_base_url(provider), _default_model(provider)),
                )
        settings_row = conn.execute("SELECT * FROM ai_settings WHERE id = ?", (SETTINGS_ID,)).fetchone()
        if settings_row and settings_row["provider"] == provider:
            conn.execute(
                """
                UPDATE ai_settings
                SET api_key_encrypted = '', api_key_source = '', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (SETTINGS_ID,),
            )
    return get_public_ai_settings()
