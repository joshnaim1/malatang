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
from harness.creator_backend import get_backend
from harness.judge import verify_mutation
from harness.runner import (
    METRICS_PATH,
    capture_failing_output,
    creator_error_mutation,
)
from harness.trajectory import holdout_dir, record_attempt, write_summary

HOLDOUT_RESULTS_PATH = REPO_ROOT / "results" / "holdout.jsonl"


def latest_training_metric() -> dict[str, Any] | None:
    if not METRICS_PATH.exists():
        return None
    rows = [
        json.loads(line)
        for line in METRICS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return rows[-1] if rows else None


def default_playbook_version() -> str:
    latest = latest_training_metric()
    if latest and latest.get("playbook_version"):
        return str(latest["playbook_version"])
    from creator.playbook import latest_version

    return latest_version()


def run_holdout(
    creator: str = "fake",
    playbook_version: str | None = None,
    model_checkpoint: str = "base",
) -> dict[str, Any]:
    bugs = load_holdout_bugs()
    attempts_per_bug = benchmark_attempts_per_bug()
    backend = get_backend(creator)
    requested_version = playbook_version or default_playbook_version()
    loaded_playbook_version = backend.prepare_iteration(requested_version)
    observe_failure = creator == "live"
    traj_dir = holdout_dir()
    bugs_passed = 0
    total_llm_calls = 0
    per_bug: list[dict[str, Any]] = []

    try:
        for bug in bugs:
            bug_id = bug["id"]
            bug_class = bug.get("class", "unknown")
            bug_patch = load_bug_patch(HOLDOUT_DIR, bug)
            failing_output = (
                capture_failing_output(bug_patch) if observe_failure else None
            )
            accepted = False

            for attempt in range(1, attempts_per_bug + 1):
                total_llm_calls += 1
                try:
                    mutation = backend.create_mutation(
                        bug,
                        iteration=0,
                        playbook_version=loaded_playbook_version,
                        attempt=attempt,
                        failing_output=failing_output,
                    )
                except Exception as exc:  # noqa: BLE001 - score as a rejected attempt
                    mutation = creator_error_mutation(
                        bug,
                        iteration=0,
                        playbook_version=loaded_playbook_version,
                        attempt=attempt,
                        model_label=getattr(backend, "name", "creator"),
                        reason=f"creator failed: {type(exc).__name__}",
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

            per_bug.append(
                {"bug_id": bug_id, "class": bug_class, "accepted": accepted}
            )
            if accepted:
                bugs_passed += 1
    finally:
        backend.close()

    bugs_total = len(bugs)
    pass_rate = round(bugs_passed / bugs_total, 4) if bugs_total else 0.0
    latest = latest_training_metric()
    record = {
        "eval": "holdout",
        "iteration": latest.get("iteration") if latest else None,
        "playbook_version": loaded_playbook_version,
        "model_checkpoint": model_checkpoint,
        "bugs_total": bugs_total,
        "bugs_passed": bugs_passed,
        "pass_rate": pass_rate,
        "attempts_per_bug": attempts_per_bug,
        "total_llm_calls": total_llm_calls,
        "per_bug": per_bug,
    }

    HOLDOUT_RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with HOLDOUT_RESULTS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")
    write_summary(traj_dir, record)
    return record


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Malatang hold-out evaluation")
    parser.add_argument(
        "--creator",
        choices=["fake", "mock", "live"],
        default="fake",
        help="Creator backend: fake stub, mock pipeline (no GPU), or live vLLM",
    )
    parser.add_argument(
        "--playbook-version",
        default=None,
        help="Playbook version to evaluate (default: latest training metric/playbook)",
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
        creator=args.creator,
        playbook_version=args.playbook_version,
        model_checkpoint=args.model_checkpoint,
    )
    print(json.dumps(result, indent=2))
    latest = latest_training_metric()
    if latest:
        delta = (result["pass_rate"] - latest["pass_rate"]) * 100
        print(
            f"Hold-out {result['pass_rate']:.1%} vs latest benchmark iteration "
            f"{latest['iteration']} {latest['pass_rate']:.1%} ({delta:+.1f} pp)"
        )


if __name__ == "__main__":
    main()
