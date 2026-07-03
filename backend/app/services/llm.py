from dataclasses import dataclass
import os
from uuid import uuid4

import httpx

from ..db import get_conn
from .ai_settings import EffectiveAiSettings, get_effective_ai_settings


@dataclass(frozen=True)
class LlmResult:
    content: str
    provider: str
    model: str


@dataclass(frozen=True)
class LlmError:
    message: str
    error_type: str  # auth_error | insufficient_balance | bad_model | bad_base_url | timeout | network_error | server_error | unknown
    status_code: int = 0
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "message": self.message,
            "error_type": self.error_type,
            "status_code": self.status_code,
            "detail": self.detail,
        }


def _chat_completions_url(base_url: str, provider: str) -> str:
    """Build the chat completions URL from base URL and provider.

    DeepSeek:   https://api.deepseek.com        → /chat/completions
    OpenAI:     https://api.openai.com/v1        → /chat/completions
    OpenAI:     https://api.openai.com            → /v1/chat/completions
    Custom:     whatever the user sets            → try /v1 first, avoid double-append
    """
    cleaned = base_url.rstrip("/")
    # DeepSeek uses /chat/completions directly (no /v1 prefix)
    if provider == "deepseek":
        if cleaned.endswith("/v1/chat/completions"):
            cleaned = cleaned.removesuffix("/v1/chat/completions")
        elif cleaned.endswith("/chat/completions"):
            return cleaned
        elif cleaned.endswith("/v1"):
            cleaned = cleaned.removesuffix("/v1")
        return f"{cleaned}/chat/completions"
    # Already includes the full path — use as-is
    if cleaned.endswith("/chat/completions"):
        return cleaned
    # OpenAI-compatible default: append /v1/chat/completions
    if cleaned.endswith("/v1"):
        return f"{cleaned}/chat/completions"
    return f"{cleaned}/v1/chat/completions"


def _classify_http_error(status_code: int, body: str) -> LlmError:
    body_lower = body.lower() if body else ""
    if status_code == 401:
        return LlmError("API Key 无效或已过期", "auth_error", status_code, detail=body[:200])
    if status_code == 402:
        return LlmError("账户余额不足", "insufficient_balance", status_code, detail=body[:200])
    if status_code in (400, 404, 422):
        if "model" in body_lower:
            return LlmError("模型名不存在或不支持", "bad_model", status_code, detail=body[:200])
        return LlmError("请求参数错误，请检查 Base URL 和模型名", "bad_request", status_code, detail=body[:200])
    if status_code == 429:
        msg = body[:200] or "请求过于频繁，请稍后重试"
        return LlmError(msg, "rate_limited", status_code, detail=body[:200])
    if status_code >= 500:
        return LlmError("模型服务端错误，请稍后重试", "server_error", status_code, detail=body[:200])
    return LlmError(f"请求失败 (HTTP {status_code})", "unknown", status_code, detail=body[:200])


def _needs_reasoning_budget(settings: EffectiveAiSettings) -> bool:
    model = settings.model.lower()
    return settings.provider == "deepseek" and ("v4" in model or "reasoner" in model)


def _effective_max_tokens(settings: EffectiveAiSettings, max_tokens: int) -> int:
    token_limit = max(1, min(max_tokens, 4000))
    if _needs_reasoning_budget(settings):
        token_limit = max(token_limit, 512)
    return token_limit


def _message_content(message: dict) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts).strip()
    return ""


def record_ai_run(
    feature: str,
    settings: EffectiveAiSettings,
    input_summary: str,
    output_summary: str = "",
    success: bool = True,
    error: str = "",
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO ai_runs(
              id, feature, provider, model, input_summary, output_summary, success, error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid4()),
                feature,
                settings.provider,
                settings.model,
                input_summary[:4000],
                output_summary[:4000],
                int(success),
                error[:1000],
            ),
        )


class LlmClient:
    def __init__(self):
        self.settings = get_effective_ai_settings()

    def real_llm_allowed(self) -> bool:
        return os.getenv("USE_REAL_LLM", "").strip() == "1"

    def is_enabled(self) -> bool:
        return (
            self.settings.provider != "mock"
            and self.settings.has_api_key
            and self.real_llm_allowed()
        )

    def complete(
        self,
        feature: str,
        system: str,
        user: str,
        *,
        max_tokens: int = 800,
        temperature: float | None = None,
    ) -> tuple[LlmResult | None, LlmError | None]:
        """Returns (result, error). On success error is None; on failure result is None."""
        if not self.is_enabled():
            record_ai_run(feature, self.settings, user, success=True, output_summary="mock fallback")
            return (None, None)

        payload = {
            "model": self.settings.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.settings.temperature if temperature is None else temperature,
            "max_tokens": _effective_max_tokens(self.settings, max_tokens),
            "stream": False,
        }
        try:
            with httpx.Client(timeout=self.settings.timeout_seconds) as client:
                response = client.post(
                    _chat_completions_url(self.settings.base_url, self.settings.provider),
                    headers={"Authorization": f"Bearer {self.settings.api_key}",
                              "Accept-Encoding": "gzip, deflate"},
                    json=payload,
                )
                if response.status_code != 200:
                    body = response.text
                    llm_err = _classify_http_error(response.status_code, body)
                    record_ai_run(feature, self.settings, user, success=False, error=llm_err.message)
                    return (None, llm_err)

                data = response.json()
                choice = data["choices"][0]
                message = choice["message"]
                content = _message_content(message)
                if not content:
                    finish_reason = choice.get("finish_reason", "")
                    reasoning_len = len(str(message.get("reasoning_content") or ""))
                    llm_err = LlmError(
                        "模型返回空内容，请增加输出长度或换用非推理模型",
                        "empty_content",
                        0,
                        detail=f"finish_reason={finish_reason}; reasoning_tokens={reasoning_len}",
                    )
                    record_ai_run(feature, self.settings, user, success=False, error=llm_err.message)
                    return (None, llm_err)
        except httpx.TimeoutException:
            llm_err = LlmError("模型服务请求超时，请检查网络或增大超时时间", "timeout", 0)
            record_ai_run(feature, self.settings, user, success=False, error=llm_err.message)
            return (None, llm_err)
        except httpx.ConnectError:
            llm_err = LlmError("Base URL 无法连接，请检查地址是否正确", "bad_base_url", 0)
            record_ai_run(feature, self.settings, user, success=False, error=llm_err.message)
            return (None, llm_err)
        except httpx.RemoteProtocolError:
            llm_err = LlmError("模型服务协议错误，请检查 Base URL", "network_error", 0)
            record_ai_run(feature, self.settings, user, success=False, error=llm_err.message)
            return (None, llm_err)
        except (KeyError, IndexError, ValueError) as exc:
            llm_err = LlmError(f"模型返回格式异常: {exc}", "parse_error", 0)
            record_ai_run(feature, self.settings, user, success=False, error=llm_err.message)
            return (None, llm_err)
        except Exception as exc:
            llm_err = LlmError(f"请求异常: {exc}", "unknown", 0)
            record_ai_run(feature, self.settings, user, success=False, error=str(exc))
            return (None, llm_err)

        record_ai_run(feature, self.settings, user, output_summary=content, success=True)
        return (LlmResult(content=content, provider=self.settings.provider, model=self.settings.model), None)
