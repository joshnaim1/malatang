"""Validate that seeded bug patches break build or tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from harness.config import REPO_ROOT
from harness.judge import verify_bug_state

TRAINING_MANIFEST = REPO_ROOT / "benchmark" / "manifest.json"
HOLDOUT_MANIFEST = REPO_ROOT / "benchmark" / "holdout" / "manifest.json"


def load_manifest(path: Path) -> list[dict[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["bugs"]


def load_bug_patch(bugs_dir: Path, bug: dict[str, str]) -> str:
    patch_path = bugs_dir / bug["patch"]
    text = patch_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    while lines and lines[0].startswith("#"):
        lines.pop(0)
    while lines and lines[0].strip() == "":
        lines.pop(0)
    return "\n".join(lines) + "\n"


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
    training = load_manifest(TRAINING_MANIFEST)
    holdout = load_manifest(HOLDOUT_MANIFEST)

    failures = validate_set(
        "training",
        REPO_ROOT / "benchmark" / "bugs",
        training,
    )
    failures.extend(
        validate_set(
            "holdout",
            REPO_ROOT / "benchmark" / "holdout",
            holdout,
        )
    )

    if failures:
        print(f"\nCalibration error: bugs still pass gate: {', '.join(failures)}")
        return 1

    print(
        f"\nAll {len(training)} training + {len(holdout)} hold-out bugs break build or tests."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
