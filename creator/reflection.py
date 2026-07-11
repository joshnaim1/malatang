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

from collections import defaultdict
import json
from dataclasses import dataclass
from typing import Any

from creator import config, llm, playbook
from creator.config import TRAJECTORIES_DIR

MAX_FEWSHOT = 3
MAX_FAILURES_PER_CLASS = 6
MAX_FAILURES_TOTAL = 30
PLAYBOOK_MAX_WORDS = 1200
REASONING_TAIL_CHARS = 240
VERDICT_NOTES_CHARS = 240
FAILURE_BUCKET_ORDER = ("diff_apply", "build", "tests", "other")


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


def _mutation(record: dict[str, Any]) -> dict[str, Any]:
    mutation = record.get("mutation", {})
    return mutation.get("mutation", mutation)


def _one_line(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return f"…{text[-(limit - 1):]}"


def failure_mode(record: dict[str, Any]) -> str:
    notes = str(record.get("verdict", {}).get("notes", "")).lower()
    if "fix diff did not apply" in notes:
        return "diff_apply"
    if "build failed" in notes:
        return "build"
    if "tests failed" in notes:
        return "tests"
    return "other"


def sample_failures(
    failures: list[dict[str, Any]],
    *,
    per_class: int = MAX_FAILURES_PER_CLASS,
    total: int = MAX_FAILURES_TOTAL,
) -> list[dict[str, Any]]:
    """Select bounded, deterministic failures with mode diversity per class."""
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for record in failures:
        bug_class = str(record.get("bug_class") or "unknown")
        grouped[bug_class][failure_mode(record)].append(record)

    selected_by_class: dict[str, list[dict[str, Any]]] = {}
    for bug_class in sorted(grouped):
        buckets = grouped[bug_class]
        selected: list[dict[str, Any]] = []
        while len(selected) < per_class:
            added = False
            for mode in FAILURE_BUCKET_ORDER:
                if buckets[mode] and len(selected) < per_class:
                    selected.append(buckets[mode].pop(0))
                    added = True
            if not added:
                break
        selected_by_class[bug_class] = selected

    # Round-robin classes so a >5-class dataset cannot let early classes consume
    # the global budget.
    sampled: list[dict[str, Any]] = []
    class_names = sorted(selected_by_class)
    index = 0
    while len(sampled) < total:
        added = False
        for bug_class in class_names:
            records = selected_by_class[bug_class]
            if index < len(records) and len(sampled) < total:
                sampled.append(records[index])
                added = True
        if not added:
            break
        index += 1
    return sampled


def _class_key(record: dict[str, Any]) -> str:
    return str(record.get("bug_class") or "unknown").lower()


def select_fewshot_wins(
    wins: list[dict[str, Any]], *, limit: int = MAX_FEWSHOT
) -> list[dict[str, Any]]:
    """Prefer three successful examples from distinct strategic bug groups."""
    selected: list[dict[str, Any]] = []

    preferred_groups = (
        lambda key: key == "syntax",
        lambda key: key in {"off-by-one", "offbyone"},
        lambda key: key in {"null-handling", "null", "wrong-api", "api", "async"},
    )
    for matches in preferred_groups:
        match = next(
            (record for record in wins if record not in selected and matches(_class_key(record))),
            None,
        )
        if match is not None:
            selected.append(match)
        if len(selected) == limit:
            return selected

    represented = {_class_key(record) for record in selected}
    for record in wins:
        key = _class_key(record)
        if record not in selected and key not in represented:
            selected.append(record)
            represented.add(key)
        if len(selected) == limit:
            return selected

    for record in wins:
        if record not in selected:
            selected.append(record)
        if len(selected) == limit:
            break
    return selected


def _failure_block(failures: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for record in failures:
        mutation = _mutation(record)
        notes = _one_line(record.get("verdict", {}).get("notes"), VERDICT_NOTES_CHARS)
        reasoning = _one_line(mutation.get("reasoning"), REASONING_TAIL_CHARS)
        lines.append(
            f"- {record.get('bug_id')} [{record.get('bug_class')}] "
            f"mode={failure_mode(record)} | verdict: {notes or '(none)'} | "
            f"reasoning tail: {reasoning or '(none)'}"
        )
    return "\n".join(lines) if lines else "(none)"


def _fewshot_block(wins: list[dict[str, Any]]) -> str:
    blocks = []
    for rec in select_fewshot_wins(wins):
        mut = _mutation(rec)
        blocks.append(
            f"### win: {rec.get('bug_id')} [{rec.get('bug_class')}]\n"
            f"reasoning: {mut.get('reasoning', '').strip()}\n"
            f"diff:\n```diff\n{mut.get('diff', '').strip()}\n```"
        )
    return "\n\n".join(blocks) if blocks else "(no verified wins this iteration)"


def build_reflection_prompt(
    current_playbook: str,
    traj: IterationTrajectories,
    *,
    current_version: str | None = None,
    next_version: str | None = None,
) -> list[dict[str, str]]:
    current_version = current_version or playbook.latest_version()
    next_version = next_version or playbook.next_version(current_version)
    sampled_failures = sample_failures(traj.failures)
    selected_wins = select_fewshot_wins(traj.wins)
    system = (
        "You are the Reflection module of a self-improving bug-fix agent. You "
        "must rewrite the complete strategy playbook from verified benchmark "
        "evidence. Output ONLY the complete next playbook as GitHub-flavored "
        "markdown: no preamble, analysis transcript, or code fence. Start with "
        f"'# Creator Strategy Playbook — {next_version}'. Keep the output under "
        f"{PLAYBOOK_MAX_WORDS} words. Include: (1) concise global rules; "
        "(2) a 'What failed and why' section with evidence-grounded analysis for "
        "each represented bug class; (3) per-bug-class tactics written as "
        "concrete imperative instructions the fix model can execute, such as "
        "'For async bugs, first check the tested function for a missing await'; "
        "and (4) 2-3 verified few-shot examples when supplied. Preserve only "
        "useful prior rules, remove redundancy, and never fabricate evidence."
    )
    user = (
        f"Iteration {traj.iteration} results: "
        f"{len(traj.wins)} wins, {len(traj.failures)} failures.\n\n"
        f"=== CURRENT PLAYBOOK ({current_version}) ===\n{current_playbook}\n\n"
        f"=== SAMPLED FAILURES ({len(sampled_failures)} of {len(traj.failures)}) ===\n"
        f"{_failure_block(sampled_failures)}\n\n"
        f"=== VERIFIED FEW-SHOT WINS ({len(selected_wins)} selected) ===\n"
        f"{_fewshot_block(selected_wins)}\n\n"
        f"Rewrite the complete {next_version} playbook now. It must differ "
        f"materially from {current_version} and remain under {PLAYBOOK_MAX_WORDS} words."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _dry_run_playbook(
    current_playbook: str,
    traj: IterationTrajectories,
    *,
    next_version: str,
) -> str:
    sampled_failures = sample_failures(traj.failures)
    body_lines = current_playbook.strip().splitlines()
    if body_lines and body_lines[0].startswith("# "):
        body_lines = body_lines[1:]
    body = "\n".join(body_lines).strip()
    header = (
        f"# Creator Strategy Playbook — {next_version} (DRY-RUN)\n\n"
        f"> Dry-run: {len(traj.wins)} wins / {len(traj.failures)} failures. "
        "Fireworks was not called. This file validates the bounded evidence and "
        "versioning path only; it is not evidence of model-driven reflection.\n\n"
    )
    evidence = (
        "## Dry-run sampled failure evidence\n\n"
        f"{_failure_block(sampled_failures)}\n\n"
        "## Few-shot examples (mined from verified wins)\n\n"
        f"{_fewshot_block(traj.wins)}\n"
    )
    return f"{header}{body}\n\n{evidence}"


def validate_generated_playbook(new_text: str, current_playbook: str) -> str:
    """Validate a generated playbook before it can replace iteration state."""
    normalized = new_text.strip()
    if not normalized:
        raise ValueError("Reflection produced an empty playbook; refusing to write it")
    if normalized == current_playbook.strip():
        raise ValueError("Reflection produced an unchanged playbook; refusing to write it")
    lines = normalized.splitlines()
    if not lines[0].startswith("# "):
        raise ValueError(
            "Reflection output is not complete markdown (missing top-level heading)"
        )
    if not any(line.startswith("## ") for line in lines[1:]):
        raise ValueError(
            "Reflection output is not complete markdown (missing section headings)"
        )
    word_count = len(normalized.split())
    if word_count > PLAYBOOK_MAX_WORDS:
        raise ValueError(
            f"Reflection output exceeds {PLAYBOOK_MAX_WORDS}-word playbook budget "
            f"({word_count} words)"
        )
    return normalized + "\n"


async def reflect(iteration: int, *, dry_run: bool = False) -> tuple[str, str]:
    """Rewrite the playbook from iteration ``iteration``'s trajectories.

    Returns ``(next_version, output_path)``.
    """
    traj = load_iteration_trajectories(iteration)
    current_version = playbook.latest_version()
    current_playbook = playbook.load_playbook(current_version)
    next_version = playbook.next_version(current_version)

    if dry_run:
        new_text = _dry_run_playbook(
            current_playbook,
            traj,
            next_version=next_version,
        )
    else:
        client = llm.fireworks_client()
        try:
            resp = await llm.chat(
                client,
                backend="fireworks",
                role="reflection",
                model=config.fireworks_model(),
                messages=build_reflection_prompt(
                    current_playbook,
                    traj,
                    current_version=current_version,
                    next_version=next_version,
                ),
                temperature=0.4,
                max_tokens=2200,
                log_extra={"iteration": iteration},
            )
            new_text = resp.text
        finally:
            await client.close()

    new_text = validate_generated_playbook(new_text, current_playbook)
    out_path = playbook.playbook_path(next_version)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(new_text, encoding="utf-8")
    return next_version, str(out_path)
