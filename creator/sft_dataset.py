"""Build the Level 2 SFT dataset from verified winning trajectories.

SOW section 7 (Level 2 step 1): collect all accepted trajectories across
iterations into an SFT dataset where prompt = bug context and completion =
winning diff + reasoning. The training distribution mirrors the Creator's
inference prompt (``creator.fix``) so the fine-tune reinforces exactly what the
model sees at serve time.

Minimum data bar (SOW section 7): if fewer than ~60 verified wins exist, Level 2
is skipped. This module reports the count so the go/no-go call is data-driven.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from creator import fix, observer, playbook
from creator.bug_context import build_bug_context
from creator.config import TRAJECTORIES_DIR

MIN_WINS_FOR_LEVEL2 = 60


def _iter_win_records() -> list[dict[str, Any]]:
    wins: list[dict[str, Any]] = []
    if not TRAJECTORIES_DIR.exists():
        return wins
    for iter_dir in sorted(TRAJECTORIES_DIR.glob("iter*")):
        for path in sorted(iter_dir.glob("*.json")):
            if path.name == "summary.json":
                continue
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("accepted"):
                wins.append(record)
    return wins


def _completion_from_mutation(mut: dict[str, Any]) -> str:
    return json.dumps(
        {
            "root_cause": mut.get("reasoning", ""),
            "plan": "apply the verified minimal fix",
            "reasoning": mut.get("reasoning", ""),
            "diff": mut.get("diff", ""),
        },
        ensure_ascii=False,
    )


def build_samples(playbook_version: str = "v0") -> list[dict[str, Any]]:
    """Return chat-format SFT samples: [{"messages": [...]}, ...]."""
    playbook_text = playbook.load_playbook(playbook_version)
    samples: list[dict[str, Any]] = []
    for record in _iter_win_records():
        mut = record.get("mutation", {}).get("mutation", record.get("mutation", {}))
        bug_id = record.get("bug_id")
        try:
            ctx = build_bug_context(bug_id)
        except Exception:  # noqa: BLE001 - skip bugs we can't rebuild context for
            continue
        obs = observer.observe(ctx)
        samples.append(
            {
                "messages": [
                    {"role": "system", "content": fix._system_prompt(playbook_text)},
                    {"role": "user", "content": fix._user_prompt(obs)},
                    {"role": "assistant", "content": _completion_from_mutation(mut)},
                ]
            }
        )
    return samples


def write_dataset(out_path: Path, playbook_version: str = "v0") -> int:
    samples = build_samples(playbook_version)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for sample in samples:
            fh.write(json.dumps(sample, ensure_ascii=False) + "\n")
    return len(samples)
