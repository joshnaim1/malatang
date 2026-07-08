"""OpenAI-compatible LLM clients + per-call token logging.

Two backends (SOW section 4):
  - vLLM on MI300X   -> Creator fix generation (self-hosted Qwen2.5-Coder-7B)
  - Fireworks API    -> reflection / playbook rewriting

Both are OpenAI-compatible, so we use the ``openai`` async SDK with a
``base_url`` override. Every call's token counts are appended to
``results/llm_calls.jsonl``.

NOTE: SOW section 5 freezes ``results/metrics.jsonl`` as Person B's
per-iteration metrics file (read by ``harness/chart.py``). Per-call token
records use the same jsonl-under-``results/`` convention but land in a separate
``results/llm_calls.jsonl`` so they never corrupt that schema.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from openai import AsyncOpenAI

from creator import config

LLM_CALLS_LOG = config.RESULTS_DIR / "llm_calls.jsonl"


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


def creator_client() -> AsyncOpenAI:
    """Client pointed at the self-hosted vLLM endpoint on MI300X."""
    return AsyncOpenAI(
        base_url=config.vllm_base_url(),
        api_key=config.vllm_api_key(),
    )


def fireworks_client() -> AsyncOpenAI:
    """Client pointed at the Fireworks serverless API."""
    return AsyncOpenAI(
        base_url=config.fireworks_base_url(),
        api_key=config.fireworks_api_key(),
    )


def _log_call(
    *,
    backend: str,
    role: str,
    model: str,
    usage: Any,
    extra: dict[str, Any] | None = None,
) -> None:
    prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
    completion_tokens = getattr(usage, "completion_tokens", 0) or 0
    total_tokens = getattr(usage, "total_tokens", 0) or (
        prompt_tokens + completion_tokens
    )
    record = {
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "backend": backend,
        "role": role,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }
    if extra:
        record.update(extra)
    LLM_CALLS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with LLM_CALLS_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


async def chat(
    client: AsyncOpenAI,
    *,
    backend: str,
    role: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int | None = None,
    log_extra: dict[str, Any] | None = None,
) -> LLMResponse:
    """Single chat completion with token logging. ``role`` labels the pipeline
    stage (e.g. ``fix``, ``reflection``) for later analysis."""
    resp = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    usage = getattr(resp, "usage", None)
    _log_call(
        backend=backend,
        role=role,
        model=model,
        usage=usage,
        extra=log_extra,
    )
    text = resp.choices[0].message.content or ""
    return LLMResponse(
        text=text,
        model=model,
        prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
        completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
        total_tokens=getattr(usage, "total_tokens", 0) or 0,
    )
