"""Mock Creator (Person A stub) — emits frozen mutation contract JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from harness.config import REPO_ROOT

EXAMPLE_MUTATION_PATH = REPO_ROOT / "contracts" / "example_mutation.json"
FIXES_DIR = REPO_ROOT / "benchmark" / "fixes"
CANNED_FIX_BUG_ID = "syntax-001"


def load_example_mutation() -> dict[str, Any]:
    return json.loads(EXAMPLE_MUTATION_PATH.read_text(encoding="utf-8"))


def load_fix_diff(bug_id: str) -> str | None:
    fix_path = FIXES_DIR / f"{bug_id}.patch"
    if not fix_path.exists():
        return None
    return _strip_patch_comments(fix_path.read_text(encoding="utf-8"))


def _strip_patch_comments(patch_text: str) -> str:
    lines = patch_text.splitlines()
    while lines and lines[0].startswith("#"):
        lines.pop(0)
    while lines and lines[0].strip() == "":
        lines.pop(0)
    return "\n".join(lines) + "\n"


def create_mutation(
    bug_id: str,
    *,
    iteration: int = 0,
    playbook_version: str = "v0",
    attempt: int = 1,
    use_canned_fix: bool = True,
) -> dict[str, Any]:
    """Build a mutation payload matching contracts/example_mutation.json shape."""
    payload = load_example_mutation()
    mutation = payload["mutation"]
    mutation["bug_id"] = bug_id
    mutation["iteration"] = iteration
    mutation["playbook_version"] = playbook_version
    mutation["attempt"] = attempt
    mutation["trigger"] = "benchmark"
    mutation["model"] = "mock-creator"

    if use_canned_fix and bug_id == CANNED_FIX_BUG_ID:
        fix_diff = load_fix_diff(bug_id)
        if fix_diff:
            mutation["diff"] = fix_diff
            mutation["file"] = "src/App.jsx"
            mutation["reasoning"] = "restore closing JSX tag on </main>"
            return payload

    mutation["diff"] = (
        "--- a/src/App.jsx\n+++ b/src/App.jsx\n"
        "@@ -1,1 +1,1 @@\n placeholder diff for mock Creator\n"
    )
    mutation["file"] = "src/App.jsx"
    mutation["reasoning"] = "mock Creator stub — no fix attempt"
    return payload
