"""Build step 2: one bug end-to-end through the Creator + fake Judge.

    bug context -> Observer -> (RCA/Planner/Fix) -> mutation JSON
                -> fake Judge -> verdict JSON -> trajectory

Modes:
  --mock (default): use the local canned Creator; no GPU needed. Proves the
      contract plumbing and trajectory writing end-to-end.
  --live: run the real pipeline against the vLLM endpoint from .env (requires the
      MI300X droplet to be up; fails loudly on missing env vars).

Usage:
    python -m scripts.creator_e2e --bug-id syntax-001
    python -m scripts.creator_e2e --bug-id syntax-001 --live
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys

from creator import config, fake_judge, observer, playbook, trajectory_store
from creator.bug_context import build_bug_context
from creator.pipeline import build_mutation, run_attempt


async def _run_live(ctx, *, iteration, attempt, playbook_version, playbook_text):
    from creator import llm

    client = llm.creator_client()
    model = config.creator_model()
    model_label = model.split("/")[-1].lower()
    return await run_attempt(
        ctx,
        client=client,
        model=model,
        model_label=model_label,
        playbook_text=playbook_text,
        playbook_version=playbook_version,
        iteration=iteration,
        attempt=attempt,
        temperature=config.benchmark_temperature(),
    )


def _run_mock(ctx, *, iteration, attempt, playbook_version):
    from creator.mock_creator import generate_fix_mock

    obs = observer.observe(ctx)
    fix = generate_fix_mock(obs)
    return build_mutation(
        obs,
        fix,
        iteration=iteration,
        playbook_version=playbook_version,
        attempt=attempt,
        model_label="mock-creator",
    )


async def main() -> int:
    parser = argparse.ArgumentParser(description="Creator end-to-end vs fake Judge")
    parser.add_argument("--bug-id", default="syntax-001")
    parser.add_argument("--iteration", type=int, default=0)
    parser.add_argument("--attempt", type=int, default=1)
    parser.add_argument("--live", action="store_true", help="use real vLLM endpoint")
    parser.add_argument("--seed", type=int, default=None, help="fake Judge RNG seed")
    args = parser.parse_args()

    playbook_version = playbook.latest_version()
    playbook_text = playbook.load_playbook(playbook_version)
    print(f"Playbook: {playbook_version} ({len(playbook_text)} chars)")

    ctx = build_bug_context(args.bug_id)
    print(f"Bug: {ctx.bug_id} [{ctx.bug_class}] -> {ctx.file_path}")

    if args.live:
        print("Mode: LIVE (vLLM)")
        mutation = await _run_live(
            ctx,
            iteration=args.iteration,
            attempt=args.attempt,
            playbook_version=playbook_version,
            playbook_text=playbook_text,
        )
    else:
        print("Mode: MOCK (canned creator)")
        mutation = _run_mock(
            ctx,
            iteration=args.iteration,
            attempt=args.attempt,
            playbook_version=playbook_version,
        )

    print("\n--- mutation (contract-valid) ---")
    print(json.dumps(mutation, indent=2))

    rng = random.Random(args.seed) if args.seed is not None else None
    verdict = fake_judge.judge(mutation, rng=rng)
    print("\n--- verdict (fake Judge, contract-valid) ---")
    print(json.dumps(verdict, indent=2))

    path = trajectory_store.record_attempt(
        iteration=args.iteration,
        bug_id=ctx.bug_id,
        bug_class=ctx.bug_class,
        attempt=args.attempt,
        mutation=mutation,
        verdict=verdict,
    )
    print(f"\nTrajectory written: {path}")
    print(f"Accepted: {verdict['accepted']}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
