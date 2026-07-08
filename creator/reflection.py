"""Reflection step (SOW section 7, Level 1 step 3).

Given one iteration's trajectories (wins + failures), rewrite the strategy
playbook into the next version via the Fireworks API. The rewritten playbook is
what makes iteration N+1 behave differently from iteration N — the Level 1
self-improvement lever.

Inputs come from ``trajectories/iterN/`` (written by either the real Runner or
the Creator's own trajectory store). Output is ``playbook/vN+1.md``.

Backend is Fireworks (SOW section 4: bigger frontier-class model, low volume,
high reasoning). ``dry_run=True`` builds the prompt and writes a deterministic
derived playbook without calling the API — useful before Fireworks credits are
confirmed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from creator import config, llm, playbook
from creator.config import TRAJECTORIES_DIR

MAX_FEWSHOT = 3


@dataclass
class IterationTrajectories:
    iteration: int
    wins: list[dict[str, Any]]
    failures: list[dict[str, Any]]

    @property
    def total(self) -> int:
        return len(self.wins) + len(self.failures)


def load_iteration_trajectories(iteration: int) -> IterationTrajectories:
    iter_dir = TRAJECTORIES_DIR / f"iter{iteration}"
    if not iter_dir.exists():
        raise FileNotFoundError(f"no trajectories for iteration {iteration}: {iter_dir}")
    wins: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for path in sorted(iter_dir.glob("*.json")):
        if path.name == "summary.json":
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("accepted"):
            wins.append(record)
        else:
            failures.append(record)
    return IterationTrajectories(iteration=iteration, wins=wins, failures=failures)


def _summarize(records: list[dict[str, Any]], *, limit: int | None = None) -> str:
    lines = []
    for rec in records[: limit or len(records)]:
        mut = rec.get("mutation", {}).get("mutation", rec.get("mutation", {}))
        lines.append(
            f"- {rec.get('bug_id')} [{rec.get('bug_class')}]: "
            f"{mut.get('reasoning', '').strip()}"
        )
    return "\n".join(lines) if lines else "(none)"


def _fewshot_block(wins: list[dict[str, Any]]) -> str:
    blocks = []
    for rec in wins[:MAX_FEWSHOT]:
        mut = rec.get("mutation", {}).get("mutation", rec.get("mutation", {}))
        blocks.append(
            f"### win: {rec.get('bug_id')} [{rec.get('bug_class')}]\n"
            f"reasoning: {mut.get('reasoning', '').strip()}\n"
            f"diff:\n```diff\n{mut.get('diff', '').strip()}\n```"
        )
    return "\n\n".join(blocks) if blocks else "(no verified wins this iteration)"


def build_reflection_prompt(
    current_playbook: str, traj: IterationTrajectories
) -> list[dict[str, str]]:
    system = (
        "You are the Reflection module of a self-improving bug-fix agent. You "
        "rewrite the Creator's strategy playbook between benchmark iterations. "
        "Mine concrete, transferable tactics from the iteration's verified wins "
        "and failures. Output ONLY the new playbook as GitHub-flavored markdown, "
        "no preamble. Keep the global rules, tighten per-bug-class tactics based "
        "on evidence, and embed 2-3 few-shot examples selected from the verified "
        "wins below. Do not fabricate examples."
    )
    user = (
        f"Iteration {traj.iteration} results: "
        f"{len(traj.wins)} wins, {len(traj.failures)} failures.\n\n"
        f"=== CURRENT PLAYBOOK ({playbook.latest_version()}) ===\n{current_playbook}\n\n"
        f"=== VERIFIED WINS ===\n{_summarize(traj.wins)}\n\n"
        f"=== FAILURES ===\n{_summarize(traj.failures)}\n\n"
        f"=== CANDIDATE FEW-SHOT EXAMPLES (from wins) ===\n{_fewshot_block(traj.wins)}\n\n"
        "Produce the improved playbook now."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _dry_run_playbook(current_playbook: str, traj: IterationTrajectories) -> str:
    next_ver = playbook.next_version(playbook.latest_version())
    header = (
        f"# Creator Strategy Playbook — {next_ver} "
        f"(reflection dry-run from iteration {traj.iteration})\n\n"
        f"> Dry-run: {len(traj.wins)} wins / {len(traj.failures)} failures. "
        "Fireworks was not called; this is the current playbook plus mined "
        "few-shot examples so the pipeline is exercisable end-to-end.\n\n"
    )
    fewshot = (
        "## Few-shot examples (mined from verified wins)\n\n"
        f"{_fewshot_block(traj.wins)}\n"
    )
    return header + current_playbook.strip() + "\n\n" + fewshot


async def reflect(iteration: int, *, dry_run: bool = False) -> tuple[str, str]:
    """Rewrite the playbook from iteration ``iteration``'s trajectories.

    Returns ``(next_version, output_path)``.
    """
    traj = load_iteration_trajectories(iteration)
    current_version = playbook.latest_version()
    current_playbook = playbook.load_playbook(current_version)
    next_version = playbook.next_version(current_version)

    if dry_run:
        new_text = _dry_run_playbook(current_playbook, traj)
    else:
        client = llm.fireworks_client()
        resp = await llm.chat(
            client,
            backend="fireworks",
            role="reflection",
            model=config.fireworks_model(),
            messages=build_reflection_prompt(current_playbook, traj),
            temperature=0.4,
            max_tokens=4096,
            log_extra={"iteration": iteration},
        )
        new_text = resp.text.strip() + "\n"

    out_path = playbook.playbook_path(next_version)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(new_text, encoding="utf-8")
    return next_version, str(out_path)
