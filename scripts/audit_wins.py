"""Audit accepted trajectories for protected-file contamination.

The same unified-diff path parser used by the Judge gate is imported here so
the offline certification cannot drift from enforcement. Run this after syncing
the real notebook trajectories and before reflection or Level 2 fine-tuning:

    python -m scripts.audit_wins
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys
from typing import Any

from creator.config import TRAJECTORIES_DIR
from harness.judge import is_protected_path, parse_touched_paths


def _mutation(record: dict[str, Any]) -> dict[str, Any]:
    mutation = record.get("mutation", {})
    return mutation.get("mutation", mutation)


def audit_wins(root: Path = TRAJECTORIES_DIR) -> dict[str, dict[str, Any]]:
    """Return per-directory accepted-win audit summaries."""
    summaries: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"wins_checked": 0, "contaminated_count": 0, "offenders": []}
    )
    if not root.exists():
        return {}

    for path in sorted(root.rglob("*.json")):
        if path.name == "summary.json":
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        if not record.get("accepted"):
            continue
        label = path.parent.relative_to(root).as_posix() or "."
        summary = summaries[label]
        summary["wins_checked"] += 1
        mutation = _mutation(record)
        touched = parse_touched_paths(str(mutation.get("diff", "")))
        protected = sorted(file for file in touched if is_protected_path(file))
        if protected:
            summary["contaminated_count"] += 1
            summary["offenders"].append(
                {
                    "bug_id": record.get("bug_id", mutation.get("bug_id", "unknown")),
                    "paths": protected,
                }
            )
    return dict(summaries)


def print_report(summaries: dict[str, dict[str, Any]]) -> int:
    if not summaries:
        print("No accepted trajectory wins found to audit.")
        return 0

    contaminated_total = 0
    for label in sorted(summaries):
        summary = summaries[label]
        contaminated_total += summary["contaminated_count"]
        print(
            f"{label}: wins checked={summary['wins_checked']}, "
            f"contaminated={summary['contaminated_count']}"
        )
        for offender in summary["offenders"]:
            print(
                f"  - {offender['bug_id']}: {', '.join(offender['paths'])}"
            )
    if contaminated_total:
        print(
            f"FAIL: {contaminated_total} accepted win(s) touched protected files."
        )
        return 1
    print("PASS: all accepted wins touch only allowed source files.")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit accepted trajectories for protected-file contamination"
    )
    parser.add_argument(
        "--trajectories-dir",
        type=Path,
        default=TRAJECTORIES_DIR,
        help="Trajectory root (default: repository trajectories/)",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    return print_report(audit_wins(args.trajectories_dir))


if __name__ == "__main__":
    sys.exit(main())
