from __future__ import annotations

import json

import httpx

from lumi.config import LLMConfig
from lumi.llm.base import LLMAuthError, LLMError, LLMRateLimitError, LLMResponse, TokenUsage
from lumi.messages import Message, ToolCall, to_api_format


def _extract_error_message(body: str) -> str | None:
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict):
        return None

    error = data.get("error")
    if isinstance(error, dict) and error.get("message"):
        return str(error["message"])
    if isinstance(error, str):
        return error
    if data.get("message"):
        return str(data["message"])
    return None


def _raise_api_error(status_code: int, body: str) -> None:
    message = _extract_error_message(body) or f"API error {status_code}"
    if status_code == 401:
        raise LLMAuthError(message, status_code=status_code, body=body)
    if status_code == 429:
        raise LLMRateLimitError(message, status_code=status_code, body=body)
    raise LLMError(message, status_code=status_code, body=body)


class OpenAIProvider:
    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self._client = httpx.Client(timeout=config.timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> OpenAIProvider:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        url = f"{self.config.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            **self.config.extra_headers,
        }
        body: dict = {
            "model": self.config.model,
            "messages": to_api_format(messages),
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if tools:
            body["tools"] = tools

        try:
            response = self._client.post(url, headers=headers, json=body)
        except httpx.TimeoutException as e:
            raise LLMError(f"request timed out after {self.config.timeout}s") from e
        except httpx.HTTPError as e:
            raise LLMError(f"HTTP error: {e}") from e

        if response.status_code >= 400:
            _raise_api_error(response.status_code, response.text)

        try:
            data = response.json()
        except json.JSONDecodeError as e:
            raise LLMError(
                "invalid JSON response",
                status_code=response.status_code,
                body=response.text,
            ) from e

        return self._parse_response(data)

    def _parse_response(self, data: dict) -> LLMResponse:
        raw_body = json.dumps(data, ensure_ascii=False)

        try:
            choices = data["choices"]
            if not choices:
                raise KeyError("empty choices")
            message = choices[0]["message"]
        except (KeyError, IndexError, TypeError) as e:
            raise LLMError(f"invalid API response: {e}", body=raw_body) from e

        tool_calls: list[ToolCall] = []
        for tc in message.get("tool_calls") or []:
            try:
                fn = tc["function"]
                raw_args = fn.get("arguments") or "{}"
            except (KeyError, TypeError) as e:
                raise LLMError(f"invalid tool call in response: {e}", body=raw_body) from e

            try:
                arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecodeError:
                arguments = {"_raw": raw_args}

            tool_calls.append(
                ToolCall(id=tc["id"], name=fn["name"], arguments=arguments)
            )

        usage = None
        if "usage" in data:
            u = data["usage"]
            usage = TokenUsage(
                prompt_tokens=u.get("prompt_tokens", 0),
                completion_tokens=u.get("completion_tokens", 0),
                total_tokens=u.get("total_tokens", 0),
            )

        return LLMResponse(
            content=message.get("content"),
            tool_calls=tool_calls,
            usage=usage,
            raw=data,
        )
