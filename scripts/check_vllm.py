"""Build step 1: verify the self-hosted Creator endpoint is reachable.

Checks that ``VLLM_BASE_URL`` / ``VLLM_API_KEY`` / ``CREATOR_MODEL`` are set
(fails loudly otherwise, SOW section 10), lists the served models, and sends one
Qwen2.5-Coder-7B chat completion through the OpenAI-compatible SDK. Token counts
are logged to ``results/llm_calls.jsonl``.

Run this once the MI300X droplet's vLLM server is up:

    python -m scripts.check_vllm
"""

from __future__ import annotations

import asyncio
import sys

from creator import config, llm


async def main() -> int:
    base_url = config.vllm_base_url()
    model = config.creator_model()
    print(f"vLLM endpoint: {base_url}")
    print(f"Creator model: {model}")

    client = llm.creator_client()

    try:
        listed = await client.models.list()
        served = [m.id for m in listed.data]
        print(f"Served models: {served}")
        if model not in served:
            print(
                f"WARNING: {model!r} not in served models list; "
                "the completion below may 404."
            )
    except Exception as exc:  # noqa: BLE001 - surface any connectivity failure
        print(f"ERROR: could not reach {base_url} (models.list failed): {exc}")
        return 1

    try:
        resp = await llm.chat(
            client,
            backend="vllm",
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
        print(f"ERROR: chat completion failed: {exc}")
        return 1

    print(f"Model reply: {resp.text.strip()!r}")
    print(
        "Tokens — prompt: "
        f"{resp.prompt_tokens}, completion: {resp.completion_tokens}, "
        f"total: {resp.total_tokens}"
    )
    print(f"Logged to: {llm.LLM_CALLS_LOG}")
    print("OK: vLLM endpoint reachable and Qwen responded.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
