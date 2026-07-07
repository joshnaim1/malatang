"""Validate that seeded bug patches break build or tests."""

from __future__ import annotations

import sys
from pathlib import Path

from harness.benchmark_io import (
    HOLDOUT_DIR,
    TRAINING_DIR,
    load_bug_patch,
    load_holdout_bugs,
    load_training_bugs,
)
from harness.judge import verify_bug_state


def validate_set(label: str, bugs_dir: Path, bugs: list[dict[str, str]]) -> list[str]:
    failures: list[str] = []
    for bug in bugs:
        bug_id = bug["id"]
        patch = load_bug_patch(bugs_dir, bug)
        gate = verify_bug_state(patch)
        broken = not gate.build_passed or not gate.tests_passed
        status = "BREAKS" if broken else "STILL PASSES"
        print(f"[{label}] {bug_id}: {status}")
        if not broken:
            failures.append(bug_id)
    return failures


def main() -> int:
    training = load_training_bugs()
    holdout = load_holdout_bugs()

    failures = validate_set("training", TRAINING_DIR, training)
    failures.extend(validate_set("holdout", HOLDOUT_DIR, holdout))

    if failures:
        print(f"\nCalibration error: bugs still pass gate: {', '.join(failures)}")
        return 1

    print(
        f"\nAll {len(training)} training + {len(holdout)} hold-out bugs break build or tests."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
