"""Generate pass-rate chart from results/metrics.jsonl."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt

from harness.config import REPO_ROOT

METRICS_PATH = REPO_ROOT / "results" / "metrics.jsonl"
CHART_PATH = REPO_ROOT / "results" / "pass_rate.png"


def load_metrics(path: Path = METRICS_PATH) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Metrics file not found: {path}")

    records: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def generate_chart(
    metrics: list[dict] | None = None,
    output_path: Path = CHART_PATH,
) -> Path:
    rows = metrics if metrics is not None else load_metrics()
    if not rows:
        raise ValueError("No metrics records to chart")

    iterations = [row["iteration"] for row in rows]
    pass_rates = [row["pass_rate"] * 100 for row in rows]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(iterations, pass_rates, marker="o", linewidth=2)
    ax.set_xlabel("Iteration")
    ax.set_ylabel("Pass rate (%)")
    ax.set_title("Benchmark pass rate by iteration")
    ax.set_xticks(iterations)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 100)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def main() -> None:
    path = generate_chart()
    print(f"Wrote chart to {path}")


if __name__ == "__main__":
    main()
