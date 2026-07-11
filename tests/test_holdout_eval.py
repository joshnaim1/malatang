from __future__ import annotations

import json
from pathlib import Path

import pytest

from creator.bug_context import build_bug_context
from harness import holdout_eval


def test_creator_context_supports_holdout_manifest() -> None:
    context = build_bug_context("holdout-001")
    assert context.bug_id == "holdout-001"
    assert context.bug_class == "syntax"
    assert context.file_path == "lib/currency.js"


def test_holdout_fake_backend_writes_isolated_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result_path = tmp_path / "holdout.jsonl"
    metrics_path = tmp_path / "metrics.jsonl"
    metrics_path.write_text(
        json.dumps(
            {
                "iteration": 2,
                "playbook_version": "v2",
                "pass_rate": 0.4,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    bugs = [
        {
            "id": "holdout-001",
            "class": "syntax",
            "patch": "holdout-001.patch",
        }
    ]

    monkeypatch.setenv("BENCHMARK_ATTEMPTS_PER_BUG", "1")
    monkeypatch.setattr(holdout_eval, "HOLDOUT_RESULTS_PATH", result_path)
    monkeypatch.setattr(holdout_eval, "METRICS_PATH", metrics_path)
    monkeypatch.setattr(holdout_eval, "load_holdout_bugs", lambda: bugs)
    monkeypatch.setattr(holdout_eval, "load_bug_patch", lambda *_args: "bug patch")
    monkeypatch.setattr(
        holdout_eval,
        "verify_mutation",
        lambda mutation, _patch: {
            "bug_id": mutation["mutation"]["bug_id"],
            "attempt": mutation["mutation"]["attempt"],
            "accepted": False,
            "build_passed": False,
            "tests_passed": False,
            "regression_detected": False,
            "wall_time_s": 0.1,
            "notes": "fixture rejection",
        },
    )
    monkeypatch.setattr(holdout_eval, "record_attempt", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(holdout_eval, "write_summary", lambda *_args, **_kwargs: None)

    record = holdout_eval.run_holdout(creator="fake")

    assert record["eval"] == "holdout"
    assert record["iteration"] == 2
    assert record["playbook_version"] == "v2"
    assert record["bugs_total"] == 1
    assert record["total_llm_calls"] == 1
    assert result_path.exists()
    assert json.loads(result_path.read_text(encoding="utf-8")) == record
