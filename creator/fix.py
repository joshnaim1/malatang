"""Fix-generation stage: the Creator's core LLM call.

Assembles the system prompt (playbook injected, SOW section 7 step 4) plus the
Observer/RCA/Planner context, asks the self-hosted Qwen2.5-Coder model for a
structured response, and parses out the unified diff. Returns a ``FixResult``
that the pipeline turns into a contract-shaped mutation.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from openai import AsyncOpenAI

from creator import llm
from creator.observer import Observation
from creator.planner import PLANNER_INSTRUCTION
from creator.rca import RCA_INSTRUCTION, rca_context

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_FIRST_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


@dataclass(frozen=True)
class FixResult:
    root_cause: str
    plan: str
    reasoning: str
    diff: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


def _system_prompt(playbook_text: str) -> str:
    return (
        "You are the Creator: a precise bug-fixing agent. You repair a single "
        "seeded defect in one file with the smallest correct change.\n\n"
        "Respond with a STRICT JSON object and nothing else, with keys:\n"
        '  "root_cause": string,\n'
        '  "plan": string,\n'
        '  "reasoning": string (one line, <= 120 chars),\n'
        '  "diff": string (a valid unified diff that `git apply -p1` accepts, '
        "with a/ and b/ path prefixes and @@ hunk headers; use \\n for "
        "line breaks inside this JSON string).\n\n"
        "The `-` and `+` lines must change the broken line — not unrelated "
        "context. Example hunk for a one-character JSX fix:\n"
        "  --- a/src/App.jsx\n"
        "  +++ b/src/App.jsx\n"
        "  @@ -28,3 +28,3 @@\n"
        "       </ul>\n"
        "   -    </main\n"
        "   +    </main>\n"
        "     );\n\n"
        "Do not wrap the JSON in prose. Do not include markdown fences.\n\n"
        "=== STRATEGY PLAYBOOK (follow it) ===\n"
        f"{playbook_text.strip()}\n"
        "=== END PLAYBOOK ==="
    )


def _user_prompt(obs: Observation) -> str:
    return (
        f"{rca_context(obs)}\n\n"
        f"{RCA_INSTRUCTION}\n{PLANNER_INSTRUCTION}\n\n"
        f"File `{obs.file_path}` (current, buggy) contents:\n"
        "-------- BEGIN FILE --------\n"
        f"{obs.buggy_source}"
        "-------- END FILE --------\n\n"
        "Produce the JSON response now."
    )


def _extract_json(text: str) -> dict:
    fenced = _JSON_FENCE_RE.search(text)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        obj = _FIRST_OBJECT_RE.search(text)
        candidate = obj.group(0) if obj else text
    # Models often put literal newlines inside the "diff" string; strict=False
    # accepts that common pattern instead of aborting the benchmark.
    return json.loads(candidate, strict=False)


async def generate_fix(
    client: AsyncOpenAI,
    *,
    model: str,
    obs: Observation,
    playbook_text: str,
    temperature: float,
    attempt: int,
    max_tokens: int = 1024,
) -> FixResult:
    resp = await llm.chat(
        client,
        backend="vllm",
        role="fix",
        model=model,
        messages=[
            {"role": "system", "content": _system_prompt(playbook_text)},
            {"role": "user", "content": _user_prompt(obs)},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        log_extra={"bug_id": obs.bug_id, "attempt": attempt},
    )
    parsed = _extract_json(resp.text)
    return FixResult(
        root_cause=str(parsed.get("root_cause", "")).strip(),
        plan=str(parsed.get("plan", "")).strip(),
        reasoning=str(parsed.get("reasoning", "")).strip() or "fix attempt",
        diff=str(parsed.get("diff", "")),
        prompt_tokens=resp.prompt_tokens,
        completion_tokens=resp.completion_tokens,
        total_tokens=resp.total_tokens,
    )
