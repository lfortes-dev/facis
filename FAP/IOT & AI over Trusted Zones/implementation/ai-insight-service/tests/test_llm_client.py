"""Tests for provider-agnostic retry client."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.config import LlmConfig
from src.llm.client import LLMRateLimitError, OpenAICompatibleClient


def _response(status_code: int, body: dict) -> SimpleNamespace:
    return SimpleNamespace(status_code=status_code, json=lambda: body)


def test_client_extracts_message_content(monkeypatch) -> None:
    client = OpenAICompatibleClient(
        LlmConfig(
            api_key="secret",
            chat_completions_url="https://example.ai/openai/deployments/gpt-4o/chat/completions?api-version=2025-01-01-preview",
            model="llama-2-7b-chat",
        )
    )
    monkeypatch.setattr(
        "src.llm.client.requests.post",
        lambda *args, **kwargs: _response(
            200,
            {
                "model": "llama-2-7b-chat",
                "choices": [
                    {
                        "message": {
                            "content": '{"summary":"ok","key_findings":[],"recommendations":[]}'
                        }
                    }
                ],
            },
        ),
    )
    text, raw = client.create_chat_completion(messages=[{"role": "user", "content": "test"}])
    assert '"summary":"ok"' in text
    assert raw["model"] == "llama-2-7b-chat"


def test_client_retries_on_429_then_raises(monkeypatch) -> None:
    client = OpenAICompatibleClient(
        LlmConfig(
            api_key="secret",
            chat_completions_url="https://example.ai/openai/deployments/gpt-4o/chat/completions?api-version=2025-01-01-preview",
            max_retries=1,
        )
    )
    monkeypatch.setattr("src.llm.client.time.sleep", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "src.llm.client.requests.post",
        lambda *args, **kwargs: _response(429, {"error": "too many requests"}),
    )
    with pytest.raises(LLMRateLimitError):
        client.create_chat_completion(messages=[{"role": "user", "content": "test"}])


def test_client_uses_configured_chat_completions_url(monkeypatch) -> None:
    called: dict[str, str] = {}
    client = OpenAICompatibleClient(
        LlmConfig(
            api_key="secret",
            chat_completions_url="https://example.ai/openai/deployments/gpt-4o/chat/completions?api-version=2025-01-01-preview",
            model="gpt-4.1-mini",
        )
    )

    def _fake_post(url, *args, **kwargs):
        called["url"] = url
        return _response(
            200,
            {
                "model": "gpt-4.1-mini",
                "choices": [
                    {
                        "message": {
                            "content": '{"summary":"ok","key_findings":[],"recommendations":[]}'
                        }
                    }
                ],
            },
        )

    monkeypatch.setattr("src.llm.client.requests.post", _fake_post)
    client.create_chat_completion(messages=[{"role": "user", "content": "ping"}])
    assert (
        called["url"]
        == "https://example.ai/openai/deployments/gpt-4o/chat/completions?api-version=2025-01-01-preview"
    )
