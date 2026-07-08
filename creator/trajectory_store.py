"""Creator-side trajectory writer.

Mirrors the record shape written by Person B's ``harness/trajectory.py`` so the
reflection step (SOW section 7, Level 1 step 3) can read wins/failures from
``trajectories/iterN/`` regardless of which side produced them. This module is
the Creator's own writer (used when running the Creator in isolation against the
fake Judge); it does not import or modify Person B's harness code.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from creator.config import TRAJECTORIES_DIR


def iteration_dir(iteration: int) -> Path:
    return TRAJECTORIES_DIR / f"iter{iteration}"


def record_attempt(
    *,
    iteration: int,
    bug_id: str,
    bug_class: str,
    attempt: int,
    mutation: dict[str, Any],
    verdict: dict[str, Any],
) -> Path:
    target_dir = iteration_dir(iteration)
    target_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "iteration": iteration,
        "bug_id": bug_id,
        "bug_class": bug_class,
        "attempt": attempt,
        "accepted": verdict["accepted"],
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "mutation": mutation,
        "verdict": verdict,
    }
    path = target_dir / f"{bug_id}_attempt{attempt}.json"
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return path
