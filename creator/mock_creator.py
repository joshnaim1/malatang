"""Local mock of the Creator's fix stage (no GPU required).

Lets the pipeline run end-to-end before the MI300X vLLM endpoint is live. It
returns a ``FixResult`` using the canned true-positive fix from
``benchmark/fixes/`` when one exists (read-only benchmark data), otherwise a
placeholder diff. Swap this for the real ``creator.fix.generate_fix`` once the
droplet is up.
"""

from __future__ import annotations

from creator.config import REPO_ROOT
from creator.fix import FixResult
from creator.observer import Observation

FIXES_DIR = REPO_ROOT / "benchmark" / "fixes"


def _strip_patch_comments(text: str) -> str:
    lines = text.splitlines()
    while lines and lines[0].startswith("#"):
        lines.pop(0)
    while lines and lines[0].strip() == "":
        lines.pop(0)
    return "\n".join(lines) + ("\n" if lines else "")


def _canned_diff(bug_id: str) -> str | None:
    path = FIXES_DIR / f"{bug_id}.patch"
    if not path.exists():
        return None
    return _strip_patch_comments(path.read_text(encoding="utf-8"))


def generate_fix_mock(obs: Observation) -> FixResult:
    diff = _canned_diff(obs.bug_id)
    if diff is None:
        diff = (
            f"--- a/{obs.file_path}\n+++ b/{obs.file_path}\n"
            "@@ -1,1 +1,1 @@\n placeholder diff (mock creator, no canned fix)\n"
        )
        reasoning = "mock creator — no canned fix available"
    else:
        reasoning = f"mock creator — canned fix for {obs.bug_id}"
    return FixResult(
        root_cause=f"[mock] {obs.symptom}",
        plan="[mock] apply canned minimal fix",
        reasoning=reasoning,
        diff=diff,
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
    )
