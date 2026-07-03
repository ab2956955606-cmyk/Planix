from dataclasses import dataclass
import os
from uuid import uuid4

import httpx

from ..api_key import INVALID_API_KEY_MESSAGE, validate_api_key_format
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
    error_type: str
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

    DeepSeek: https://api.deepseek.com -> /chat/completions
    OpenAI: https://api.openai.com/v1 -> /chat/completions
    OpenAI: https://api.openai.com -> /v1/chat/completions
    Custom: whatever the user sets -> try /v1 first, avoid double-append
    """
    cleaned = base_url.rstrip("/")
    # DeepSeek uses /chat/completions directly, without a /v1 prefix.
    if provider == "deepseek":
        if cleaned.endswith("/v1/chat/completions"):
            cleaned = cleaned.removesuffix("/v1/chat/completions")
        elif cleaned.endswith("/chat/completions"):
            return cleaned
        elif cleaned.endswith("/v1"):
            cleaned = cleaned.removesuffix("/v1")
        return f"{cleaned}/chat/completions"
    # Already includes the full path, so use as-is.
    if cleaned.endswith("/chat/completions"):
        return cleaned
    # OpenAI-compatible default: append /v1/chat/completions.
    if cleaned.endswith("/v1"):
        return f"{cleaned}/chat/completions"
    return f"{cleaned}/v1/chat/completions"


def _classify_http_error(status_code: int, body: str) -> LlmError:
    body_lower = body.lower() if body else ""
    if status_code == 401:
        return LlmError("API key is invalid or expired.", "auth_error", status_code, detail=body[:200])
    if status_code == 402:
        return LlmError("The model account has insufficient balance.", "insufficient_balance", status_code, detail=body[:200])
    if status_code in (400, 404, 422):
        if "model" in body_lower:
            return LlmError("The model name does not exist or is not supported.", "bad_model", status_code, detail=body[:200])
        return LlmError("The request is invalid. Check the Base URL and model name.", "bad_request", status_code, detail=body[:200])
    if status_code == 429:
        msg = body[:200] or "Too many requests. Try again later."
        return LlmError(msg, "rate_limited", status_code, detail=body[:200])
    if status_code >= 500:
        return LlmError("The model service returned a server error. Try again later.", "server_error", status_code, detail=body[:200])
    return LlmError(f"Request failed (HTTP {status_code}).", "unknown", status_code, detail=body[:200])


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
        timeout_seconds: int | None = None,
    ) -> tuple[LlmResult | None, LlmError | None]:
        """Returns (result, error). On success error is None; on failure result is None."""
        if not self.is_enabled():
            record_ai_run(feature, self.settings, user, success=True, output_summary="mock fallback")
            return (None, None)

        api_key_error = validate_api_key_format(self.settings.api_key)
        if api_key_error:
            llm_err = LlmError(api_key_error, "invalid_key_format", 0)
            record_ai_run(feature, self.settings, user, success=False, error=llm_err.message)
            return (None, llm_err)

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
        request_timeout = timeout_seconds if timeout_seconds is not None else self.settings.timeout_seconds
        try:
            with httpx.Client(timeout=max(1, request_timeout), trust_env=False) as client:
                response = client.post(
                    _chat_completions_url(self.settings.base_url, self.settings.provider),
                    headers={
                        "Authorization": f"Bearer {self.settings.api_key.strip()}",
                        "Accept-Encoding": "gzip, deflate",
                    },
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
                        "The model returned empty content. Increase max tokens or use a non-reasoning model.",
                        "empty_content",
                        0,
                        detail=f"finish_reason={finish_reason}; reasoning_tokens={reasoning_len}",
                    )
                    record_ai_run(feature, self.settings, user, success=False, error=llm_err.message)
                    return (None, llm_err)
        except httpx.TimeoutException:
            llm_err = LlmError("The model request timed out. Check the network or increase timeout.", "timeout", 0)
            record_ai_run(feature, self.settings, user, success=False, error=llm_err.message)
            return (None, llm_err)
        except httpx.ConnectError:
            llm_err = LlmError("The Base URL cannot be reached. Check whether the address is correct.", "bad_base_url", 0)
            record_ai_run(feature, self.settings, user, success=False, error=llm_err.message)
            return (None, llm_err)
        except httpx.RemoteProtocolError:
            llm_err = LlmError("The model service returned a protocol error. Check the Base URL.", "network_error", 0)
            record_ai_run(feature, self.settings, user, success=False, error=llm_err.message)
            return (None, llm_err)
        except UnicodeEncodeError:
            llm_err = LlmError(INVALID_API_KEY_MESSAGE, "invalid_key_format", 0)
            record_ai_run(feature, self.settings, user, success=False, error=llm_err.message)
            return (None, llm_err)
        except (KeyError, IndexError, ValueError) as exc:
            llm_err = LlmError(f"The model response format is invalid: {exc}", "parse_error", 0)
            record_ai_run(feature, self.settings, user, success=False, error=llm_err.message)
            return (None, llm_err)
        except Exception as exc:
            llm_err = LlmError(f"Request failed: {exc}", "unknown", 0)
            record_ai_run(feature, self.settings, user, success=False, error=str(exc))
            return (None, llm_err)

        record_ai_run(feature, self.settings, user, output_summary=content, success=True)
        return (LlmResult(content=content, provider=self.settings.provider, model=self.settings.model), None)
