from __future__ import annotations

from pathlib import Path


def test_committed_playbooks_document_known_truncation() -> None:
    """Guardrails: v2/v3 truncation is documented, not silently repaired."""
    v2 = Path("playbook/v2.md").read_text(encoding="utf-8")
    v3 = Path("playbook/v3.md").read_text(encoding="utf-8")

    v1 = Path("playbook/v1.md").read_text(encoding="utf-8")
    assert "dry-run" in v1.lower()
    assert v2.rstrip().endswith("formatCents(grandTotal)}</p>")
    assert "fraction` or `decimal`?" in v3.rstrip()


def test_metrics_and_holdout_rows_present() -> None:
    metrics = Path("results/metrics.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(metrics) == 4
    holdout = Path("results/holdout.jsonl").read_text(encoding="utf-8").strip()
    assert '"pass_rate": 0.6' in holdout
