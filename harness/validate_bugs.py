"""Validate that seeded bug patches break build or tests."""

from __future__ import annotations

import json
import sys

from harness.judge import verify_bug_state
from harness.runner import load_bug_patch, load_manifest


def main() -> int:
    failures = []
    for bug in load_manifest():
        bug_id = bug["id"]
        patch = load_bug_patch(bug)
        gate = verify_bug_state(patch)
        broken = not gate.build_passed or not gate.tests_passed
        status = "BREAKS" if broken else "STILL PASSES"
        print(f"{bug_id}: {status}")
        if not broken:
            failures.append(bug_id)

    if failures:
        print(f"\nCalibration error: bugs still pass gate: {', '.join(failures)}")
        return 1
    print("\nAll seeded bugs break build or tests.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
