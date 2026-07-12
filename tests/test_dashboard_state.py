"""Tests for dashboard state aggregation."""

from __future__ import annotations

import json
from pathlib import Path

from harness.dashboard_state import get_dashboard_state


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_dashboard_state_reads_metrics_and_active_iteration(tmp_path: Path) -> None:
    _write_jsonl(
        tmp_path / "results" / "metrics.jsonl",
        [
            {
                "iteration": 0,
                "playbook_version": "v0",
                "bugs_total": 25,
                "bugs_passed": 10,
                "pass_rate": 0.4,
                "total_llm_calls": 12,
            }
        ],
    )

    iter_dir = tmp_path / "trajectories" / "iter1"
    iter_dir.mkdir(parents=True)
    (iter_dir / "syntax-001_attempt1.json").write_text(
        json.dumps(
            {
                "iteration": 1,
                "bug_id": "syntax-001",
                "bug_class": "syntax",
                "attempt": 1,
                "accepted": False,
                "verdict": {
                    "accepted": False,
                    "build_passed": False,
                    "tests_passed": False,
                    "notes": "patch does not apply",
                },
            }
        ),
        encoding="utf-8",
    )
    (iter_dir / "syntax-002_attempt1.json").write_text(
        json.dumps(
            {
                "iteration": 1,
                "bug_id": "syntax-002",
                "bug_class": "syntax",
                "attempt": 1,
                "accepted": True,
                "verdict": {
                    "accepted": True,
                    "build_passed": True,
                    "tests_passed": True,
                    "notes": "build and tests passed",
                },
            }
        ),
        encoding="utf-8",
    )

    state = get_dashboard_state(tmp_path)

    assert len(state["metrics"]) == 1
    assert state["metrics"][0]["pass_rate"] == 0.4
    assert state["active_iteration"]["iteration"] == 1
    assert state["active_iteration"]["status"] == "running"
    assert state["active_iteration"]["bugs_attempted"] == 2
    assert state["active_iteration"]["bugs_passed"] == 1
    assert len(state["active_iteration"]["recent_attempts"]) == 2


def test_dashboard_state_marks_complete_when_summary_exists(tmp_path: Path) -> None:
    iter_dir = tmp_path / "trajectories" / "iter0"
    iter_dir.mkdir(parents=True)
    summary = {
        "iteration": 0,
        "playbook_version": "v0",
        "bugs_total": 25,
        "bugs_passed": 10,
        "pass_rate": 0.4,
    }
    (iter_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    _write_jsonl(tmp_path / "results" / "metrics.jsonl", [summary])

    state = get_dashboard_state(tmp_path)

    assert state["active_iteration"]["status"] == "complete"
    assert state["pipeline_steps"][0]["status"] == "complete"
