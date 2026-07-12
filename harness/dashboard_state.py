"""Read benchmark pipeline state for the live demo dashboard."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness.config import REPO_ROOT
from harness.dashboard_runner import get_run_status, suggested_start_iteration

METRICS_PATH = REPO_ROOT / "results" / "metrics.jsonl"
HOLDOUT_PATH = REPO_ROOT / "results" / "holdout.jsonl"
CHART_PATH = REPO_ROOT / "results" / "pass_rate.png"
TRAINING_BUGS_TOTAL = 25


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(json.loads(stripped))
    return rows


def _parse_attempt_path(path: Path) -> tuple[str, int] | None:
    stem = path.stem
    if "_attempt" not in stem:
        return None
    bug_id, _, attempt_raw = stem.partition("_attempt")
    try:
        return bug_id, int(attempt_raw)
    except ValueError:
        return None


def _read_attempt_record(path: Path, repo_root: Path) -> dict[str, Any] | None:
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    verdict = record.get("verdict") or {}
    try:
        rel_path = str(path.relative_to(repo_root)).replace("\\", "/")
    except ValueError:
        rel_path = str(path)
    return {
        "bug_id": record.get("bug_id"),
        "bug_class": record.get("bug_class"),
        "attempt": record.get("attempt"),
        "accepted": bool(record.get("accepted")),
        "build_passed": verdict.get("build_passed"),
        "tests_passed": verdict.get("tests_passed"),
        "notes": verdict.get("notes"),
        "recorded_at": record.get("recorded_at"),
        "path": rel_path,
        "mtime": path.stat().st_mtime,
    }


def _scan_iteration_dir(iter_dir: Path, repo_root: Path) -> dict[str, Any] | None:
    if not iter_dir.is_dir():
        return None

    summary_path = iter_dir / "summary.json"
    summary: dict[str, Any] | None = None
    if summary_path.is_file():
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            summary = None

    attempts: list[dict[str, Any]] = []
    bugs_attempted: set[str] = set()
    bugs_passed: set[str] = set()

    for path in sorted(iter_dir.glob("*_attempt*.json")):
        parsed = _parse_attempt_path(path)
        if parsed is None:
            continue
        bug_id, _ = parsed
        record = _read_attempt_record(path, repo_root)
        if record is None or not bug_id:
            continue
        attempts.append(record)
        bugs_attempted.add(bug_id)
        if record["accepted"]:
            bugs_passed.add(bug_id)

    attempts.sort(key=lambda row: row.get("mtime") or 0.0, reverse=True)
    recent = [
        {key: value for key, value in row.items() if key != "mtime"}
        for row in attempts[:12]
    ]

    iteration_raw = iter_dir.name.removeprefix("iter")
    try:
        iteration = int(iteration_raw)
    except ValueError:
        return None

    status = "complete" if summary is not None else ("running" if attempts else "idle")
    return {
        "iteration": iteration,
        "playbook_version": (summary or {}).get("playbook_version", f"v{iteration}"),
        "bugs_total": (summary or {}).get("bugs_total", TRAINING_BUGS_TOTAL),
        "bugs_attempted": len(bugs_attempted),
        "bugs_passed": len(bugs_passed),
        "attempts_total": len(attempts),
        "pass_rate": (summary or {}).get("pass_rate"),
        "status": status,
        "summary": summary,
        "recent_attempts": recent,
    }


def _discover_iterations(repo_root: Path) -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    trajectories_root = repo_root / "trajectories"
    if not trajectories_root.is_dir():
        return snapshots
    for path in sorted(trajectories_root.glob("iter*")):
        if not path.is_dir():
            continue
        snapshot = _scan_iteration_dir(path, repo_root)
        if snapshot is not None:
            snapshots.append(snapshot)
    snapshots.sort(key=lambda row: row["iteration"])
    return snapshots


def _pick_active_iteration(snapshots: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not snapshots:
        return None
    running = [row for row in snapshots if row["status"] == "running"]
    if running:
        return running[-1]
    idle = [row for row in snapshots if row["status"] == "idle"]
    if idle:
        return idle[-1]
    return snapshots[-1]


def get_dashboard_state(repo_root: Path | None = None) -> dict[str, Any]:
    """Aggregate metrics, hold-out, and live trajectory progress."""
    root = repo_root or REPO_ROOT
    metrics_path = root / "results" / "metrics.jsonl"
    holdout_path = root / "results" / "holdout.jsonl"
    chart_path = root / "results" / "pass_rate.png"

    metrics = _read_jsonl(metrics_path)
    holdout_rows = _read_jsonl(holdout_path)
    holdout = holdout_rows[-1] if holdout_rows else None

    snapshots = _discover_iterations(root)
    active = _pick_active_iteration(snapshots)
    completed_iterations = {row["iteration"] for row in metrics}

    pipeline_steps: list[dict[str, Any]] = []
    max_iter = max(
        [
            *(row["iteration"] for row in metrics),
            *(row["iteration"] for row in snapshots),
            -1,
        ]
    )
    for iteration in range(max_iter + 1):
        metric = next((row for row in metrics if row["iteration"] == iteration), None)
        snapshot = next(
            (row for row in snapshots if row["iteration"] == iteration), None
        )
        if metric is not None:
            status = "complete"
        elif snapshot is not None:
            status = snapshot["status"]
        elif iteration in completed_iterations:
            status = "complete"
        else:
            status = "pending"
        pipeline_steps.append(
            {
                "iteration": iteration,
                "playbook_version": (metric or snapshot or {}).get(
                    "playbook_version", f"v{iteration}"
                ),
                "pass_rate": (metric or snapshot or {}).get("pass_rate"),
                "bugs_passed": (metric or snapshot or {}).get("bugs_passed"),
                "bugs_total": (metric or snapshot or {}).get(
                    "bugs_total", TRAINING_BUGS_TOTAL
                ),
                "status": status,
            }
        )

    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
        "holdout": holdout,
        "active_iteration": active,
        "iteration_snapshots": snapshots,
        "pipeline_steps": pipeline_steps,
        "chart_available": chart_path.is_file(),
        "chart_path": "results/pass_rate.png" if chart_path.is_file() else None,
        "suggested_start_iteration": suggested_start_iteration(metrics),
        "run_job": get_run_status(repo_root=root),
    }
