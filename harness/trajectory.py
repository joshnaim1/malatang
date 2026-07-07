"""Trajectory store — persist every Judge attempt for the reflection loop.

SOW section 7 (Level 1, step 2): store every trajectory (bug, diff, verdict)
under ``trajectories/iterN/``. This is the Judge side's verified-win record; it
does not touch Creator/playbook/reflection code, which read from here later.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness.config import REPO_ROOT

TRAJECTORIES_ROOT = REPO_ROOT / "trajectories"


def iteration_dir(iteration: int) -> Path:
    return TRAJECTORIES_ROOT / f"iter{iteration}"


def holdout_dir() -> Path:
    return TRAJECTORIES_ROOT / "holdout"


def record_attempt(
    target_dir: Path,
    *,
    iteration: int,
    bug_id: str,
    bug_class: str,
    attempt: int,
    mutation: dict[str, Any],
    verdict: dict[str, Any],
) -> Path:
    """Write one attempt trajectory as JSON; returns the file path."""
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


def write_summary(target_dir: Path, summary: dict[str, Any]) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / "summary.json"
    path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return path
