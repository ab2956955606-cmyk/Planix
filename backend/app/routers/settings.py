import logging
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, HTTPException

from ..schemas import AiSettingsOut, AiSettingsTestOut, AiSettingsTestPayload, AiSettingsUpdate
from ..services.ai_settings import get_public_ai_settings, save_ai_settings
from ..services.llm import LlmClient

logger = logging.getLogger("mynotes.api.settings")
router = APIRouter(prefix="/api/ai", tags=["ai-settings"])


def _sanitize_base_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        host = parsed.hostname or ""
        if parsed.port:
            host = f"{host}:{parsed.port}"
        return urlunsplit((parsed.scheme, host, parsed.path.rstrip("/"), "", ""))
    except Exception:
        return "<invalid-url>"


def _mask_key(value: str | None) -> str:
    key = (value or "").strip()
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}****{key[-4:]}"


@router.get("/settings", response_model=AiSettingsOut)
def read_ai_settings() -> AiSettingsOut:
    settings = get_public_ai_settings()
    logger.info(
        "GET /api/ai/settings -> provider=%s model=%s base_url=%s api_key_present=%s",
        settings.provider,
        settings.model,
        _sanitize_base_url(settings.base_url),
        settings.has_api_key,
    )
    return settings


@router.put("/settings", response_model=AiSettingsOut)
def update_ai_settings(payload: AiSettingsUpdate) -> AiSettingsOut:
    has_key = bool(payload.api_key and payload.api_key.strip())
    logger.info(
        "PUT /api/ai/settings provider=%s base_url=%s model=%s api_key_present=%s api_key_masked=%s",
        payload.provider,
        _sanitize_base_url(payload.base_url),
        payload.model,
        has_key,
        _mask_key(payload.api_key),
    )
    try:
        result = save_ai_settings(payload)
        logger.info("AI settings saved successfully")
        return result
    except Exception as exc:
        logger.error("AI settings save failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="后端保存设置失败") from exc


@router.post("/test", response_model=AiSettingsTestOut)
def test_ai_settings(payload: AiSettingsTestPayload) -> AiSettingsTestOut:
    client = LlmClient()
    if not client.is_enabled():
        if client.settings.provider == "mock":
            return AiSettingsTestOut(
                ok=True,
                mode="mock",
                message="当前是 Mock 模式，不需要 API Key。配置真实 Key 即可调用模型。",
                provider=client.settings.provider,
                model=client.settings.model,
            )
        if client.settings.has_api_key and not client.real_llm_allowed():
            return AiSettingsTestOut(
                ok=True,
                mode="mock",
                message="设置已保存。当前未开启真实模型调用（USE_REAL_LLM=1），本次使用安全 mock，不消耗 API。",
                provider=client.settings.provider,
                model=client.settings.model,
            )
        return AiSettingsTestOut(
            ok=False,
            mode="error",
            message="API Key 未保存，请在设置中填入 API Key",
            provider=client.settings.provider,
            model=client.settings.model,
            error_type="no_key",
        )

    result, err = client.complete(
        "settings_test",
        "You are a concise health-check assistant. Reply in one short sentence.",
        payload.prompt,
        max_tokens=32,
        temperature=0.1,
    )
    if result:
        return AiSettingsTestOut(
            ok=True,
            mode="llm",
            message=result.content,
            provider=result.provider,
            model=result.model,
        )
    return AiSettingsTestOut(
        ok=False,
        mode="error",
        message=err.message if err else "模型调用失败，请检查设置",
        provider=client.settings.provider,
        model=client.settings.model,
        error_type=err.error_type if err else "unknown",
        status_code=err.status_code if err else 0,
        detail=err.detail if err else "",
    )
