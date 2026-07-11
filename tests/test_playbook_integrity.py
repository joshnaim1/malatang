from __future__ import annotations

from typing import Any

import pytest

from harness import runner


class RecordingBackend:
    name = "recording"

    def __init__(self) -> None:
        self.prepared: list[str] = []
        self.mutation_versions: list[str] = []

    def prepare_iteration(self, playbook_version: str) -> str:
        self.prepared.append(playbook_version)
        return "v-actually-loaded"

    def create_mutation(
        self,
        bug: dict[str, str],
        *,
        iteration: int,
        playbook_version: str,
        attempt: int,
        failing_output: str | None = None,
    ) -> dict[str, Any]:
        self.mutation_versions.append(playbook_version)
        return {
            "mutation": {
                "iteration": iteration,
                "playbook_version": playbook_version,
                "bug_id": bug["id"],
                "attempt": attempt,
                "type": "code",
                "trigger": "benchmark",
                "file": "src/App.jsx",
                "diff": "placeholder diff",
                "reasoning": "fixture",
                "model": "fixture",
            }
        }

    def close(self) -> None:
        pass


def test_runner_records_version_returned_by_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = RecordingBackend()
    bug = {"id": "syntax-001", "class": "syntax", "patch": "syntax-001.patch"}

    monkeypatch.setenv("BENCHMARK_ATTEMPTS_PER_BUG", "1")
    monkeypatch.setattr(runner, "load_training_bugs", lambda: [bug])
    monkeypatch.setattr(runner, "load_bug_patch", lambda *_args: "bug patch")
    monkeypatch.setattr(
        runner,
        "verify_mutation",
        lambda mutation, _patch: {
            "bug_id": mutation["mutation"]["bug_id"],
            "attempt": 1,
            "accepted": True,
            "build_passed": True,
            "tests_passed": True,
            "regression_detected": False,
            "wall_time_s": 0.1,
            "notes": "fixture accepted",
        },
    )
    monkeypatch.setattr(runner, "record_attempt", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(runner, "write_summary", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(runner, "append_metrics", lambda _record: None)

    record = runner.run_iteration(
        iteration=1,
        playbook_version="v1-requested",
        backend=backend,
    )

    assert backend.prepared == ["v1-requested"]
    assert backend.mutation_versions == ["v-actually-loaded"]
    assert record["playbook_version"] == "v-actually-loaded"
