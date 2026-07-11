from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.chart import generate_chart, load_latest_holdout


def test_chart_works_with_one_point_and_no_holdout(tmp_path: Path) -> None:
    output = tmp_path / "one-point.png"
    missing_holdout = tmp_path / "missing-holdout.jsonl"
    metrics = [{"iteration": 0, "pass_rate": 0.4, "playbook_version": "v0"}]

    result = generate_chart(
        metrics=metrics,
        output_path=output,
        holdout_path=missing_holdout,
    )

    assert result == output
    assert output.exists()
    assert output.stat().st_size > 0


def test_chart_renders_latest_holdout_marker(tmp_path: Path) -> None:
    output = tmp_path / "with-holdout.png"
    holdout_path = tmp_path / "holdout.jsonl"
    holdout_path.write_text(
        json.dumps({"eval": "holdout", "pass_rate": 0.6}) + "\n",
        encoding="utf-8",
    )
    metrics = [
        {"iteration": 0, "pass_rate": 0.4, "playbook_version": "v0"},
        {"iteration": 1, "pass_rate": 0.52, "playbook_version": "v1"},
    ]

    generate_chart(metrics=metrics, output_path=output, holdout_path=holdout_path)

    assert output.exists()
    assert load_latest_holdout(holdout_path)["pass_rate"] == 0.6


def test_chart_refuses_empty_metrics(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="refusing to generate"):
        generate_chart(
            metrics=[],
            output_path=tmp_path / "no.png",
            holdout_path=tmp_path / "none.jsonl",
        )
