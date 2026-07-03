from dataclasses import dataclass
import json
from typing import Iterator
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
    if status_code in (401, 403):
        return LlmError("API key is invalid or expired.", "auth_error", status_code, detail=body[:200])
    if status_code == 402 or any(term in body_lower for term in ("insufficient", "quota", "balance", "credit")):
        return LlmError("The model account has insufficient balance.", "insufficient_balance", status_code, detail=body[:200])
    if status_code in (400, 422):
        if any(term in body_lower for term in ("model", "does not exist", "not found")):
            return LlmError("The model name does not exist or is not supported.", "bad_model", status_code, detail=body[:200])
        return LlmError("The request is invalid. Check the Base URL and model name.", "unknown", status_code, detail=body[:200])
    if status_code == 404:
        if "model" in body_lower and any(term in body_lower for term in ("does not exist", "not found", "not supported")):
            return LlmError("The model name does not exist or is not supported.", "bad_model", status_code, detail=body[:200])
        return LlmError("The Base URL endpoint is unavailable. Check the API path.", "bad_base_url", status_code, detail=body[:200])
    if status_code == 429:
        return LlmError("The model account has insufficient balance or request quota.", "insufficient_balance", status_code, detail=body[:200])
    if status_code >= 500:
        return LlmError("The model service returned a server error. Try again later.", "unknown", status_code, detail=body[:200])
    return LlmError(f"Request failed (HTTP {status_code}).", "unknown", status_code, detail=body[:200])


def _needs_reasoning_budget(settings: EffectiveAiSettings) -> bool:
    model = settings.model.lower()
    return settings.provider == "deepseek" and ("v4" in model or "reasoner" in model)


def _effective_max_tokens(settings: EffectiveAiSettings, max_tokens: int, *, max_token_cap: int = 4000) -> int:
    token_limit = max(1, min(max_tokens, max_token_cap))
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

    def is_enabled(self) -> bool:
        return (
            self.settings.provider != "mock"
            and self.settings.has_api_key
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
        response_format_json: bool = False,
        max_token_cap: int = 4000,
    ) -> tuple[LlmResult | None, LlmError | None]:
        """Returns (result, error). On success error is None; on failure result is None."""
        if not self.is_enabled():
            record_ai_run(feature, self.settings, user, success=True, output_summary="local fallback")
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
            "max_tokens": _effective_max_tokens(self.settings, max_tokens, max_token_cap=max_token_cap),
            "stream": False,
        }
        if response_format_json:
            payload["response_format"] = {"type": "json_object"}
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
                    if response_format_json and response.status_code in (400, 422) and "response_format" in body.lower():
                        payload.pop("response_format", None)
                        response = client.post(
                            _chat_completions_url(self.settings.base_url, self.settings.provider),
                            headers={
                                "Authorization": f"Bearer {self.settings.api_key.strip()}",
                                "Accept-Encoding": "gzip, deflate",
                            },
                            json=payload,
                        )
                        if response.status_code == 200:
                            body = ""
                        else:
                            body = response.text
                    if response.status_code == 200:
                        pass
                    else:
                        llm_err = _classify_http_error(response.status_code, body)
                        record_ai_run(feature, self.settings, user, success=False, error=llm_err.message)
                        return (None, llm_err)

                data = response.json()
                choice = data["choices"][0]
                finish_reason = str(choice.get("finish_reason") or "")
                if finish_reason == "length":
                    llm_err = LlmError(
                        "The model output was truncated before completion.",
                        "model_output_truncated",
                        0,
                        detail="finish_reason=length",
                    )
                    record_ai_run(feature, self.settings, user, success=False, error="model output was truncated")
                    return (None, llm_err)
                message = choice["message"]
                content = _message_content(message)
                if not content:
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
        except (httpx.InvalidURL, httpx.UnsupportedProtocol):
            llm_err = LlmError("The Base URL is invalid. Check whether the address is correct.", "bad_base_url", 0)
            record_ai_run(feature, self.settings, user, success=False, error=llm_err.message)
            return (None, llm_err)
        except httpx.ConnectError:
            llm_err = LlmError("The model service cannot be reached. Check the network or service availability.", "network_error", 0)
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

    def stream_tokens(
        self,
        feature: str,
        system: str,
        user: str,
        *,
        max_tokens: int = 800,
        temperature: float | None = None,
        timeout_seconds: int | None = None,
    ) -> Iterator[str]:
        """Yield OpenAI-compatible streaming tokens.

        This method intentionally does not call complete() and split a full
        response afterward. If real streaming is unavailable, callers should
        fall back at the runtime level.
        """
        if not self.is_enabled():
            return

        api_key_error = validate_api_key_format(self.settings.api_key)
        if api_key_error:
            record_ai_run(feature, self.settings, user, success=False, error=api_key_error)
            raise RuntimeError(api_key_error)

        payload = {
            "model": self.settings.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.settings.temperature if temperature is None else temperature,
            "max_tokens": _effective_max_tokens(self.settings, max_tokens),
            "stream": True,
        }
        request_timeout = timeout_seconds if timeout_seconds is not None else self.settings.timeout_seconds
        output_parts: list[str] = []
        try:
            with httpx.Client(timeout=max(1, request_timeout), trust_env=False) as client:
                with client.stream(
                    "POST",
                    _chat_completions_url(self.settings.base_url, self.settings.provider),
                    headers={
                        "Authorization": f"Bearer {self.settings.api_key.strip()}",
                        "Accept-Encoding": "gzip, deflate",
                    },
                    json=payload,
                ) as response:
                    if response.status_code != 200:
                        body = response.read().decode("utf-8", errors="replace")
                        llm_err = _classify_http_error(response.status_code, body)
                        record_ai_run(feature, self.settings, user, success=False, error=llm_err.message)
                        raise RuntimeError(llm_err.message)

                    for line in response.iter_lines():
                        if not line:
                            continue
                        data = line.removeprefix("data:").strip()
                        if not data:
                            continue
                        if data == "[DONE]":
                            break
                        try:
                            payload_line = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        choice = (payload_line.get("choices") or [{}])[0]
                        delta = choice.get("delta") or {}
                        content = _message_content(delta)
                        if content:
                            output_parts.append(content)
                            yield content
        except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as exc:
            record_ai_run(feature, self.settings, user, success=False, error=str(exc))
            raise RuntimeError(str(exc)) from exc
        except Exception as exc:
            if not isinstance(exc, RuntimeError):
                record_ai_run(feature, self.settings, user, success=False, error=str(exc))
            raise

        record_ai_run(feature, self.settings, user, output_summary="".join(output_parts), success=True)
