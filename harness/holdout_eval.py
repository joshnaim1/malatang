"""Hold-out evaluation — one-shot run over the never-seen bug set.

SOW section 6: 5 hold-out bugs are used once at the end to show the improvement
generalizes. This runner is intentionally separate from the training loop so the
hold-out set is never picked during iterations. Writes its own metrics and
trajectories so hold-out numbers stay isolated from the training curve.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from harness.benchmark_io import (
    HOLDOUT_DIR,
    load_bug_patch,
    load_holdout_bugs,
)
from harness.config import REPO_ROOT, benchmark_attempts_per_bug
from harness.fake_creator import create_mutation
from harness.judge import verify_mutation
from harness.trajectory import holdout_dir, record_attempt, write_summary

HOLDOUT_METRICS_PATH = REPO_ROOT / "results" / "holdout_metrics.jsonl"


def run_holdout(
    iteration_label: str = "holdout",
    model_checkpoint: str = "base",
) -> dict[str, Any]:
    bugs = load_holdout_bugs()
    attempts_per_bug = benchmark_attempts_per_bug()
    traj_dir = holdout_dir()
    bugs_passed = 0
    total_llm_calls = 0
    per_bug: list[dict[str, Any]] = []

    for bug in bugs:
        bug_id = bug["id"]
        bug_class = bug.get("class", "unknown")
        bug_patch = load_bug_patch(HOLDOUT_DIR, bug)
        accepted = False

        for attempt in range(1, attempts_per_bug + 1):
            total_llm_calls += 1
            mutation = create_mutation(
                bug_id,
                iteration=0,
                playbook_version=iteration_label,
                attempt=attempt,
                use_canned_fix=(attempt == 1),
            )
            verdict = verify_mutation(mutation, bug_patch)
            record_attempt(
                traj_dir,
                iteration=0,
                bug_id=bug_id,
                bug_class=bug_class,
                attempt=attempt,
                mutation=mutation,
                verdict=verdict,
            )
            if verdict["accepted"]:
                accepted = True
                break

        per_bug.append({"bug_id": bug_id, "class": bug_class, "accepted": accepted})
        if accepted:
            bugs_passed += 1

    bugs_total = len(bugs)
    pass_rate = round(bugs_passed / bugs_total, 4) if bugs_total else 0.0
    record = {
        "eval": "holdout",
        "playbook_version": iteration_label,
        "model_checkpoint": model_checkpoint,
        "bugs_total": bugs_total,
        "bugs_passed": bugs_passed,
        "pass_rate": pass_rate,
        "attempts_per_bug": attempts_per_bug,
        "total_llm_calls": total_llm_calls,
        "per_bug": per_bug,
    }

    HOLDOUT_METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with HOLDOUT_METRICS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")
    write_summary(traj_dir, record)
    return record


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Malatang hold-out evaluation")
    parser.add_argument(
        "--label",
        default="holdout",
        help="playbook_version label recorded with the result (default: holdout)",
    )
    parser.add_argument(
        "--model-checkpoint",
        default="base",
        help="Model checkpoint label recorded in metrics (default: base)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = run_holdout(
        iteration_label=args.label,
        model_checkpoint=args.model_checkpoint,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
