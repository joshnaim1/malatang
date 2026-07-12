"""Bake committed benchmark evidence into a static replay payload.

The Vercel showcase is a *static* site: no Python server, no live runner. This
script reads the same committed artifacts the harness writes and emits one
self-contained JSON file the frontend fetches once and replays client-side.

    python -m scripts.build_replay_data
    python -m scripts.build_replay_data --out web/data/replay.json

Source of truth (all committed, all honest):
  results/metrics.jsonl    per-iteration pass rate + llm calls (the evidence curve)
  results/holdout.jsonl    isolated hold-out eval
  benchmark/manifest.json  the frozen 25-bug training set (ids, class, description)
  benchmark/holdout/...     the 5 hold-out bugs
  playbook/v*.md           the Level-1 self-modification the reflection step rewrites

Per-bug pass/fail was NOT committed (trajectories were gitignored during the AMD
notebook run, see docs/PRESENTATION_RUNBOOK.md). We therefore surface the real
*pass count* per iteration and never invent which specific bug passed.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "web" / "data" / "replay.json"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(json.loads(stripped))
    return rows


def _load_manifest(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    bugs = data.get("bugs", data) if isinstance(data, dict) else data
    out: list[dict[str, Any]] = []
    for bug in bugs:
        out.append(
            {
                "id": bug.get("id"),
                "class": bug.get("class", "unknown"),
                "description": bug.get("description", ""),
            }
        )
    return out


def _load_playbooks(playbook_dir: Path) -> list[dict[str, Any]]:
    playbooks: list[dict[str, Any]] = []
    for path in sorted(playbook_dir.glob("v*.md")):
        version = path.stem
        text = path.read_text(encoding="utf-8")
        first_para = next(
            (ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")),
            "",
        )
        playbooks.append(
            {
                "version": version,
                "summary": first_para[:280],
                "body": text,
                "chars": len(text),
            }
        )
    return playbooks


def build_payload(repo_root: Path) -> dict[str, Any]:
    metrics = _read_jsonl(repo_root / "results" / "metrics.jsonl")
    metrics.sort(key=lambda r: r["iteration"])
    holdout_rows = _read_jsonl(repo_root / "results" / "holdout.jsonl")
    holdout = holdout_rows[-1] if holdout_rows else None

    training_bugs = _load_manifest(repo_root / "benchmark" / "manifest.json")
    holdout_bugs = _load_manifest(repo_root / "benchmark" / "holdout" / "manifest.json")
    class_counts = Counter(b["class"] for b in training_bugs)

    playbooks = _load_playbooks(repo_root / "playbook")

    baseline = metrics[0]["pass_rate"] if metrics else None
    final = metrics[-1]["pass_rate"] if metrics else None

    return {
        "generated_from": "results/metrics.jsonl + holdout.jsonl + benchmark/manifest.json + playbook/",
        "note": (
            "Real committed evidence. Per-bug pass/fail was not committed "
            "(trajectories were gitignored during the AMD run); pass COUNTS are real, "
            "individual bug verdicts are not reconstructed."
        ),
        "benchmark": {
            "training_total": len(training_bugs),
            "holdout_total": len(holdout_bugs),
            "class_counts": dict(sorted(class_counts.items())),
            "training_bugs": training_bugs,
            "holdout_bugs": holdout_bugs,
        },
        "metrics": metrics,
        "holdout": holdout,
        "playbooks": playbooks,
        "summary": {
            "baseline_pass_rate": baseline,
            "final_pass_rate": final,
            "holdout_pass_rate": holdout["pass_rate"] if holdout else None,
            "iterations": len(metrics),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build static replay payload")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output JSON path")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args()

    payload = build_payload(args.repo_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    metrics = payload["metrics"]
    print(f"Wrote {args.out.relative_to(args.repo_root)}")
    print(
        f"  {len(metrics)} iterations · "
        f"{payload['benchmark']['training_total']} training bugs · "
        f"{len(payload['playbooks'])} playbooks · "
        f"holdout {'present' if payload['holdout'] else 'missing'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
