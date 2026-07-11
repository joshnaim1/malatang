"""Generate pass-rate chart from results/metrics.jsonl."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

from harness.config import REPO_ROOT

METRICS_PATH = REPO_ROOT / "results" / "metrics.jsonl"
CHART_PATH = REPO_ROOT / "results" / "pass_rate.png"
HOLDOUT_PATH = REPO_ROOT / "results" / "holdout.jsonl"
CALIBRATION_LOW = 0.20
CALIBRATION_HIGH = 0.45


def load_metrics(path: Path = METRICS_PATH) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Metrics file not found: {path}")

    records: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def load_latest_holdout(path: Path = HOLDOUT_PATH) -> dict | None:
    if not path.exists():
        return None
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return rows[-1] if rows else None


def generate_chart(
    metrics: list[dict] | None = None,
    output_path: Path = CHART_PATH,
    holdout_path: Path = HOLDOUT_PATH,
) -> Path:
    rows = metrics if metrics is not None else load_metrics()
    if not rows:
        raise ValueError(
            "results/metrics.jsonl is empty; refusing to generate an evidence chart"
        )

    iterations = [row["iteration"] for row in rows]
    pass_rates = [row["pass_rate"] for row in rows]

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.axhspan(
        CALIBRATION_LOW,
        CALIBRATION_HIGH,
        color="#d8b365",
        alpha=0.18,
        label="Iteration-0 calibration target",
        zorder=0,
    )
    ax.text(
        min(iterations),
        CALIBRATION_HIGH + 0.015,
        "20–45% calibration target",
        fontsize=9,
        color="#7a5b16",
        va="bottom",
    )
    ax.plot(
        iterations,
        pass_rates,
        color="#2563eb",
        marker="o",
        markersize=7,
        linewidth=2.5,
        label="Training benchmark",
        zorder=3,
    )
    for iteration, pass_rate, row in zip(iterations, pass_rates, rows):
        ax.annotate(
            f"{row.get('playbook_version', '?')}\n{pass_rate:.0%}",
            (iteration, pass_rate),
            xytext=(0, 10),
            textcoords="offset points",
            ha="center",
            fontsize=9,
            fontweight="semibold",
        )

    holdout = load_latest_holdout(holdout_path)
    x_ticks = list(iterations)
    x_tick_labels = [str(iteration) for iteration in iterations]
    if holdout is not None:
        holdout_x = max(iterations) + 0.55
        holdout_rate = holdout["pass_rate"]
        ax.scatter(
            [holdout_x],
            [holdout_rate],
            marker="D",
            s=80,
            color="#dc2626",
            edgecolor="white",
            linewidth=0.8,
            label="Hold-out",
            zorder=4,
        )
        ax.annotate(
            f"hold-out\n{holdout_rate:.0%}",
            (holdout_x, holdout_rate),
            xytext=(0, 10),
            textcoords="offset points",
            ha="center",
            fontsize=9,
            fontweight="semibold",
            color="#991b1b",
        )
        x_ticks.append(holdout_x)
        x_tick_labels.append("hold-out")

    ax.set_xlabel("Iteration")
    ax.set_ylabel("Pass rate")
    ax.set_title("Malatang self-improvement: pass rate by iteration")
    ax.set_xticks(x_ticks, labels=x_tick_labels)
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=1.0))
    ax.grid(axis="y", alpha=0.25)
    ax.set_ylim(0, 1)
    ax.legend(loc="best", frameon=False)
    ax.spines[["top", "right"]].set_visible(False)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return output_path


def main() -> int:
    try:
        path = generate_chart()
    except (FileNotFoundError, ValueError) as exc:
        print(f"Cannot generate chart: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote chart to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
