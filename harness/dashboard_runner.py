"""Spawn and track benchmark runs triggered from the dashboard."""

from __future__ import annotations

import subprocess
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness.config import REPO_ROOT

LOG_PATH = REPO_ROOT / "results" / "dashboard_run.log"
VALID_CREATORS = {"fake", "mock", "live"}


@dataclass
class RunJob:
    status: str = "idle"
    pid: int | None = None
    command: list[str] = field(default_factory=list)
    started_at: str | None = None
    finished_at: str | None = None
    exit_code: int | None = None
    error: str | None = None
    _process: subprocess.Popen[str] | None = field(default=None, repr=False)
    _log_handle: Any = field(default=None, repr=False)


_lock = threading.Lock()
_job = RunJob()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tail_log(path: Path, *, max_lines: int = 20) -> list[str]:
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-max_lines:]


def _watch_process(process: subprocess.Popen[str]) -> None:
    exit_code = process.wait()
    with _lock:
        if _job._process is not process:
            return
        _job.exit_code = exit_code
        _job.finished_at = _utc_now()
        _job.status = "completed" if exit_code == 0 else "failed"
        _job.pid = None
        _job._process = None
        if _job._log_handle is not None:
            _job._log_handle.close()
            _job._log_handle = None


def _build_command(
    *,
    start_iteration: int,
    iterations: int,
    creator: str,
    no_chart: bool,
    fresh: bool,
) -> list[str]:
    if creator not in VALID_CREATORS:
        raise ValueError(f"creator must be one of {sorted(VALID_CREATORS)}")
    if start_iteration < 0:
        raise ValueError("start_iteration must be >= 0")
    if iterations < 1:
        raise ValueError("iterations must be >= 1")

    command = [
        sys.executable,
        "-u",
        "-m",
        "harness.runner",
        "--creator",
        creator,
        "--start-iteration",
        str(start_iteration),
        "--iterations",
        str(iterations),
    ]
    if no_chart:
        command.append("--no-chart")
    if fresh:
        command.append("--fresh")
    return command


def start_run(
    *,
    repo_root: Path | None = None,
    start_iteration: int,
    iterations: int = 1,
    creator: str = "live",
    no_chart: bool = True,
    fresh: bool = False,
) -> dict[str, Any]:
    """Launch ``harness.runner`` in the background if idle."""
    root = repo_root or REPO_ROOT
    command = _build_command(
        start_iteration=start_iteration,
        iterations=iterations,
        creator=creator,
        no_chart=no_chart,
        fresh=fresh,
    )

    with _lock:
        if _job.status == "running" and _job._process is not None:
            poll = _job._process.poll()
            if poll is None:
                raise RuntimeError("A benchmark run is already in progress.")
            _job.exit_code = poll
            _job.status = "completed" if poll == 0 else "failed"
            _job.finished_at = _utc_now()
            _job._process = None

        log_path = root / "results" / "dashboard_run.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_handle = log_path.open("w", encoding="utf-8")
        log_handle.write(f"# started {_utc_now()}\n")
        log_handle.write(f"# command: {' '.join(command)}\n")
        log_handle.flush()

        process = subprocess.Popen(
            command,
            cwd=root,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )

        _job.status = "running"
        _job.pid = process.pid
        _job.command = command
        _job.started_at = _utc_now()
        _job.finished_at = None
        _job.exit_code = None
        _job.error = None
        _job._process = process
        _job._log_handle = log_handle

    watcher = threading.Thread(target=_watch_process, args=(process,), daemon=True)
    watcher.start()
    return get_run_status(repo_root=root)


def get_run_status(*, repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or REPO_ROOT
    log_path = root / "results" / "dashboard_run.log"

    with _lock:
        if _job.status == "running" and _job._process is not None:
            poll = _job._process.poll()
            if poll is not None:
                _job.exit_code = poll
                _job.finished_at = _utc_now()
                _job.status = "completed" if poll == 0 else "failed"
                _job.pid = None
                _job._process = None
                if _job._log_handle is not None:
                    _job._log_handle.close()
                    _job._log_handle = None

        return {
            "status": _job.status,
            "pid": _job.pid,
            "command": _job.command,
            "started_at": _job.started_at,
            "finished_at": _job.finished_at,
            "exit_code": _job.exit_code,
            "error": _job.error,
            "log_tail": _tail_log(log_path),
        }


def reset_run_job() -> None:
    """Clear in-memory job tracking (used by tests)."""
    with _lock:
        if _job._log_handle is not None:
            _job._log_handle.close()
        _job.status = "idle"
        _job.pid = None
        _job.command = []
        _job.started_at = None
        _job.finished_at = None
        _job.exit_code = None
        _job.error = None
        _job._process = None
        _job._log_handle = None


def suggested_start_iteration(metrics: list[dict[str, Any]]) -> int:
    if not metrics:
        return 0
    return max(row["iteration"] for row in metrics) + 1
