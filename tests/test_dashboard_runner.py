"""Tests for dashboard-triggered benchmark runs."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harness.dashboard_runner import (
    get_run_status,
    reset_run_job,
    start_run,
    suggested_start_iteration,
)


@pytest.fixture(autouse=True)
def _clear_run_job() -> None:
    reset_run_job()


def test_suggested_start_iteration_from_metrics() -> None:
    metrics = [{"iteration": 0}, {"iteration": 3}]
    assert suggested_start_iteration(metrics) == 4
    assert suggested_start_iteration([]) == 0


def test_start_run_rejects_invalid_creator(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="creator"):
        start_run(repo_root=tmp_path, start_iteration=0, creator="invalid")


def test_start_run_rejects_when_already_running(tmp_path: Path) -> None:
    process = MagicMock()
    process.pid = 4242
    process.poll.return_value = None

    with (
        patch("harness.dashboard_runner.subprocess.Popen", return_value=process),
        patch("harness.dashboard_runner.threading.Thread"),
    ):
        start_run(repo_root=tmp_path, start_iteration=1, creator="fake")
        with pytest.raises(RuntimeError, match="already in progress"):
            start_run(repo_root=tmp_path, start_iteration=2, creator="fake")


def test_start_run_spawns_runner_and_records_status(tmp_path: Path) -> None:
    process = MagicMock()
    process.pid = 999
    process.poll.return_value = None

    with (
        patch("harness.dashboard_runner.subprocess.Popen", return_value=process),
        patch("harness.dashboard_runner.threading.Thread"),
    ):
        status = start_run(
            repo_root=tmp_path,
            start_iteration=3,
            iterations=1,
            creator="fake",
            no_chart=True,
        )

    assert status["status"] == "running"
    assert status["pid"] == 999
    assert "harness.runner" in " ".join(status["command"])

    log_path = tmp_path / "results" / "dashboard_run.log"
    assert log_path.is_file()

    process.poll.return_value = 0
    final = get_run_status(repo_root=tmp_path)
    assert final["status"] == "completed"
    assert final["exit_code"] == 0
