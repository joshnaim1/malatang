"""Verify the Fireworks endpoint used by the reflection step.

Checks that ``FIREWORKS_API_KEY`` / ``FIREWORKS_BASE_URL`` / ``FIREWORKS_MODEL``
are set (fails loudly otherwise, SOW section 10) and sends one chat completion
through the OpenAI-compatible SDK. Token counts are logged to
``results/llm_calls.jsonl``.

    python -m scripts.check_fireworks
"""

from __future__ import annotations

import asyncio
import sys

from creator import config, llm


async def main() -> int:
    base_url = config.fireworks_base_url()
    model = config.fireworks_model()
    print(f"Fireworks endpoint: {base_url}")
    print(f"Reflection model:   {model}")

    client = llm.fireworks_client()

    try:
        resp = await llm.chat(
            client,
            backend="fireworks",
            role="healthcheck",
            model=model,
            messages=[
                {"role": "system", "content": "You are a terse assistant."},
                {"role": "user", "content": "Reply with exactly: pong"},
            ],
            temperature=0.0,
            max_tokens=16,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: Fireworks call failed: {exc}")
        print(
            "Hint: confirm the API key is valid and FIREWORKS_MODEL is an exact "
            "serverless ID (accounts/fireworks/models/...), not the display name."
        )
        return 1

    print(f"Model reply: {resp.text.strip()!r}")
    print(
        "Tokens — prompt: "
        f"{resp.prompt_tokens}, completion: {resp.completion_tokens}, "
        f"total: {resp.total_tokens}"
    )
    print(f"Logged to: {llm.LLM_CALLS_LOG}")
    print("OK: Fireworks reachable and model responded.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
