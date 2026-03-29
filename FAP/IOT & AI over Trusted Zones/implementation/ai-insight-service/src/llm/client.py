"""Provider-agnostic chat client with retry logic."""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlparse

import requests

from src.config import LlmConfig


class LLMClientError(Exception):
    """Base class for LLM client failures."""


class LLMRateLimitError(LLMClientError):
    """Raised when upstream responds with 429 and retries are exhausted."""


class LLMUpstreamError(LLMClientError):
    """Raised when upstream keeps failing with 5xx/transport errors."""


class OpenAICompatibleClient:
    """Minimal provider-agnostic chat completion client."""

    def __init__(self, config: LlmConfig) -> None:
        self._config = config

    def _endpoint_url(self) -> str:
        if not self._config.chat_completions_url:
            raise LLMClientError("LLM chat_completions_url is required")
        parsed = urlparse(self._config.chat_completions_url)
        if self._config.require_https and parsed.scheme.lower() != "https":
            raise LLMClientError("LLM chat_completions_url must use https")
        return self._config.chat_completions_url

    def _build_headers(self) -> dict[str, str]:
        if not self._config.api_key:
            raise LLMClientError("LLM api_key is required")
        return {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }

    def create_chat_completion(
        self,
        *,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.2,
    ) -> tuple[str, dict[str, Any]]:
        """Send chat request and return model text + raw response JSON."""
        endpoint = self._endpoint_url()
        headers = self._build_headers()
        payload: dict[str, Any] = {
            "model": model or self._config.model,
            "messages": messages,
            "temperature": temperature,
        }

        attempt = 0
        max_attempts = self._config.max_retries + 1
        while attempt < max_attempts:
            attempt += 1
            try:
                response = requests.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=self._config.timeout_seconds,
                )
            except requests.RequestException as error:
                if attempt >= max_attempts:
                    raise LLMUpstreamError(
                        f"LLM request failed after {attempt} attempts"
                    ) from error
                self._sleep_for_retry(attempt)
                continue

            if response.status_code == 429:
                if attempt >= max_attempts:
                    raise LLMRateLimitError("LLM rate limit exceeded")
                self._sleep_for_retry(attempt)
                continue
            if 500 <= response.status_code <= 599:
                if attempt >= max_attempts:
                    raise LLMUpstreamError(
                        f"LLM upstream failed with {response.status_code}"
                    )
                self._sleep_for_retry(attempt)
                continue
            if response.status_code >= 400:
                raise LLMClientError(f"LLM request failed with status {response.status_code}")

            body = response.json()
            text = self._extract_content(body)
            return text, body

        raise LLMUpstreamError("LLM request failed")

    def _sleep_for_retry(self, attempt: int) -> None:
        delay = min(
            self._config.retry_max_delay_seconds,
            self._config.retry_base_delay_seconds * (2 ** max(0, attempt - 1)),
        )
        time.sleep(delay)

    @staticmethod
    def _extract_content(response_body: dict[str, Any]) -> str:
        choices = response_body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMClientError("LLM response missing choices")
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise LLMClientError("LLM response choices[0] is invalid")
        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise LLMClientError("LLM response missing message")
        content = message.get("content")
        if not isinstance(content, str):
            raise LLMClientError("LLM response missing message content")
        return content
