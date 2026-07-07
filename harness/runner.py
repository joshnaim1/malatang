"""Benchmark Runner — orchestrates fake Creator and real Judge.

Loops the frozen training bug set through the mock Creator into the real Judge,
records every attempt as a trajectory, and writes per-iteration metrics matching
the SOW section 5 contract. Supports multiple iterations (plumbing for the
playbook loop); the pass rate only rises once a real, self-improving Creator is
wired in — the harness never fakes the curve.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from harness.benchmark_io import (
    TRAINING_DIR,
    load_bug_patch,
    load_training_bugs,
)
from harness.config import REPO_ROOT, benchmark_attempts_per_bug
from harness.fake_creator import create_mutation
from harness.judge import verify_mutation
from harness.trajectory import iteration_dir, record_attempt, write_summary

METRICS_PATH = REPO_ROOT / "results" / "metrics.jsonl"


def append_metrics(record: dict[str, Any]) -> None:
    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with METRICS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def run_iteration(
    iteration: int = 0,
    playbook_version: str = "v0",
    model_checkpoint: str = "base",
) -> dict[str, Any]:
    bugs = load_training_bugs()
    attempts_per_bug = benchmark_attempts_per_bug()
    traj_dir = iteration_dir(iteration)
    bugs_passed = 0
    total_llm_calls = 0

    for bug in bugs:
        bug_id = bug["id"]
        bug_class = bug.get("class", "unknown")
        bug_patch = load_bug_patch(TRAINING_DIR, bug)
        accepted = False

        for attempt in range(1, attempts_per_bug + 1):
            total_llm_calls += 1
            mutation = create_mutation(
                bug_id,
                iteration=iteration,
                playbook_version=playbook_version,
                attempt=attempt,
                use_canned_fix=(attempt == 1),
            )
            verdict = verify_mutation(mutation, bug_patch)
            record_attempt(
                traj_dir,
                iteration=iteration,
                bug_id=bug_id,
                bug_class=bug_class,
                attempt=attempt,
                mutation=mutation,
                verdict=verdict,
            )
            if verdict["accepted"]:
                accepted = True
                break

        if accepted:
            bugs_passed += 1

    bugs_total = len(bugs)
    pass_rate = round(bugs_passed / bugs_total, 4) if bugs_total else 0.0
    record = {
        "iteration": iteration,
        "playbook_version": playbook_version,
        "model_checkpoint": model_checkpoint,
        "bugs_total": bugs_total,
        "bugs_passed": bugs_passed,
        "pass_rate": pass_rate,
        "attempts_per_bug": attempts_per_bug,
        "total_llm_calls": total_llm_calls,
        "gpu_hours_consumed": 0.0,
    }
    append_metrics(record)
    write_summary(iteration_dir(iteration), record)
    return record


def run_benchmark(
    iterations: int = 1,
    start_iteration: int = 0,
    model_checkpoint: str = "base",
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for offset in range(iterations):
        iteration = start_iteration + offset
        result = run_iteration(
            iteration=iteration,
            playbook_version=f"v{iteration}",
            model_checkpoint=model_checkpoint,
        )
        print(json.dumps(result, indent=2))
        results.append(result)
    return results


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Malatang benchmark runner")
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="Number of iterations to run (default: 1)",
    )
    parser.add_argument(
        "--start-iteration",
        type=int,
        default=0,
        help="Iteration index to start from (default: 0)",
    )
    parser.add_argument(
        "--model-checkpoint",
        default="base",
        help="Model checkpoint label recorded in metrics (default: base)",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Truncate results/metrics.jsonl before running",
    )
    parser.add_argument(
        "--no-chart",
        action="store_true",
        help="Skip chart generation after the run",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.fresh and METRICS_PATH.exists():
        METRICS_PATH.unlink()

    run_benchmark(
        iterations=args.iterations,
        start_iteration=args.start_iteration,
        model_checkpoint=args.model_checkpoint,
    )

    if not args.no_chart:
        from harness.chart import generate_chart

        chart_path = generate_chart()
        print(f"Wrote chart to {chart_path}")


if __name__ == "__main__":
    main()
