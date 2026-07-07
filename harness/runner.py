"""Benchmark Runner v0 — orchestrates fake Creator and real Judge."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from harness.config import REPO_ROOT, benchmark_attempts_per_bug
from harness.fake_creator import create_mutation
from harness.judge import verify_mutation

BUGS_DIR = REPO_ROOT / "benchmark" / "bugs"
MANIFEST_PATH = REPO_ROOT / "benchmark" / "manifest.json"
METRICS_PATH = REPO_ROOT / "results" / "metrics.jsonl"


def load_manifest() -> list[dict[str, str]]:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return data["bugs"]


def load_bug_patch(bug: dict[str, str]) -> str:
    patch_path = BUGS_DIR / bug["patch"]
    text = patch_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    while lines and lines[0].startswith("#"):
        lines.pop(0)
    while lines and lines[0].strip() == "":
        lines.pop(0)
    return "\n".join(lines) + "\n"


def append_metrics(record: dict[str, Any]) -> None:
    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with METRICS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def run_iteration(
    iteration: int = 0,
    playbook_version: str = "v0",
    model_checkpoint: str = "base",
) -> dict[str, Any]:
    bugs = load_manifest()
    attempts_per_bug = benchmark_attempts_per_bug()
    bugs_passed = 0
    total_llm_calls = 0

    for bug in bugs:
        bug_id = bug["id"]
        bug_patch = load_bug_patch(bug)
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
    return record


def main() -> None:
    result = run_iteration()
    print(json.dumps(result, indent=2))
    from harness.chart import generate_chart

    chart_path = generate_chart()
    print(f"Wrote chart to {chart_path}")


if __name__ == "__main__":
    main()
