"""The static Vercel replay payload must faithfully mirror committed evidence."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.build_replay_data import build_payload

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_payload_matches_committed_metrics() -> None:
    payload = build_payload(REPO_ROOT)

    # Metrics are copied verbatim from results/metrics.jsonl, in iteration order.
    raw = [
        json.loads(line)
        for line in (REPO_ROOT / "results" / "metrics.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    assert payload["metrics"] == sorted(raw, key=lambda r: r["iteration"])
    assert payload["summary"]["iterations"] == len(raw)
    assert payload["summary"]["baseline_pass_rate"] == raw[0]["pass_rate"]


def test_payload_carries_benchmark_and_playbooks() -> None:
    payload = build_payload(REPO_ROOT)
    bench = payload["benchmark"]

    # The frozen training set is real and non-empty; counts are internally consistent.
    assert bench["training_total"] == len(bench["training_bugs"])
    assert sum(bench["class_counts"].values()) == bench["training_total"]
    assert all(b["id"] and b["class"] for b in bench["training_bugs"])

    # Playbook evolution is present and ordered v0, v1, ...
    versions = [p["version"] for p in payload["playbooks"]]
    assert versions == sorted(versions)
    assert all(p["body"] for p in payload["playbooks"])


def test_annotations_cover_every_iteration() -> None:
    """Every metrics row (and the hold-out) gets a note the UI can show."""
    payload = build_payload(REPO_ROOT)
    for row in payload["metrics"]:
        assert str(row["iteration"]) in payload["annotations"]
    assert "holdout" in payload["annotations"]
    # Annotations live beside metrics, never inside them — rows stay verbatim.
    assert all("note" not in row for row in payload["metrics"])


def test_committed_payload_is_in_sync() -> None:
    """web/data/replay.json must be regenerated when evidence changes."""
    committed = json.loads(
        (REPO_ROOT / "web" / "data" / "replay.json").read_text(encoding="utf-8")
    )
    assert committed["metrics"] == build_payload(REPO_ROOT)["metrics"]
