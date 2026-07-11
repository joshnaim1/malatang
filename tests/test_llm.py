from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest
from openai import APIConnectionError

from creator import config, llm


def test_fireworks_timeout_defaults_to_600(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FIREWORKS_TIMEOUT_S", raising=False)
    assert config.fireworks_timeout_s() == 600.0


def test_fireworks_client_uses_configured_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setenv("FIREWORKS_API_KEY", "fixture")
    monkeypatch.setenv("FIREWORKS_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("FIREWORKS_TIMEOUT_S", "321")
    monkeypatch.setattr(llm, "AsyncOpenAI", FakeAsyncOpenAI)

    llm.fireworks_client()

    assert captured["timeout"] == 321.0


def test_fireworks_chat_retries_connection_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    sleeps: list[int] = []

    class FakeCompletions:
        async def create(self, **_kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise APIConnectionError(request=httpx.Request("POST", "https://example.invalid"))
            usage = SimpleNamespace(
                prompt_tokens=4,
                completion_tokens=2,
                total_tokens=6,
            )
            message = SimpleNamespace(content="ok")
            return SimpleNamespace(
                usage=usage,
                choices=[SimpleNamespace(message=message)],
            )

    async def fake_sleep(delay: int) -> None:
        sleeps.append(delay)

    client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    monkeypatch.setattr(llm.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(llm, "_log_call", lambda **_kwargs: None)

    response = asyncio.run(
        llm.chat(
            client,
            backend="fireworks",
            role="reflection",
            model="fixture",
            messages=[{"role": "user", "content": "test"}],
            temperature=0,
        )
    )

    assert calls == 2
    assert sleeps == [1]
    assert response.text == "ok"
