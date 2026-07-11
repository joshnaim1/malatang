"""Creator pipeline v0: bug context -> contract-shaped mutation JSON.

Wires the owned stages together (SOW section 13):

    Observer -> RCA -> Planner -> Fix  ->  mutation (contracts/mutation.schema.json)

The mutation is validated against the frozen contract before it leaves the
Creator, so a malformed payload fails here rather than at the Judge boundary.
"""

from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

from creator import contracts, observer
from creator.bug_context import BugContext
from creator.diff_utils import normalize_fix_diff
from creator.fix import FixResult, generate_fix


def build_mutation(
    obs: observer.Observation,
    fix: FixResult,
    *,
    iteration: int,
    playbook_version: str,
    attempt: int,
    model_label: str,
    trigger: str = "benchmark",
) -> dict[str, Any]:
    """Assemble and validate a mutation payload from a fix result."""
    payload = {
        "mutation": {
            "iteration": iteration,
            "playbook_version": playbook_version,
            "bug_id": obs.bug_id,
            "attempt": attempt,
            "type": "code",
            "trigger": trigger,
            "file": obs.file_path,
            "diff": normalize_fix_diff(obs.file_path, fix.diff, buggy_source=obs.buggy_source),
            "reasoning": fix.reasoning,
            "model": model_label,
        }
    }
    return contracts.validate_mutation(payload)


async def run_attempt(
    ctx: BugContext,
    *,
    client: AsyncOpenAI,
    model: str,
    model_label: str,
    playbook_text: str,
    playbook_version: str,
    iteration: int,
    attempt: int,
    temperature: float,
) -> dict[str, Any]:
    """Run one Creator attempt against a live vLLM client and return a validated
    mutation payload."""
    obs = observer.observe(ctx)
    fix = await generate_fix(
        client,
        model=model,
        obs=obs,
        playbook_text=playbook_text,
        temperature=temperature,
        attempt=attempt,
    )
    return build_mutation(
        obs,
        fix,
        iteration=iteration,
        playbook_version=playbook_version,
        attempt=attempt,
        model_label=model_label,
    )
