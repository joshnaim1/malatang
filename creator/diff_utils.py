"""Normalize Creator fix diffs so the Judge sandbox can apply them.

The live model often emits hunks without ``--- a/`` / ``+++ b/`` headers even
when the prompt asks for them. The Judge applies fix diffs with ``git apply``,
which requires standard unified-diff headers. We synthesize headers from the
known target file rather than trusting model output.
"""

from __future__ import annotations

import re

_DIFF_GIT_RE = re.compile(r"^diff --git ")
_INDEX_RE = re.compile(r"^index [0-9a-f]+\.\.[0-9a-f]+")
_MINUS_FILE_RE = re.compile(r"^--- ")
_PLUS_FILE_RE = re.compile(r"^\+\+\+ ")


def _strip_git_metadata(lines: list[str]) -> list[str]:
    """Drop ``diff --git`` / ``index`` lines the model sometimes echoes."""
    out: list[str] = []
    for line in lines:
        if _DIFF_GIT_RE.match(line) or _INDEX_RE.match(line):
            continue
        out.append(line)
    return out


def normalize_fix_diff(file_path: str, raw: str) -> str:
    """Return a unified diff ``git apply`` can consume for ``file_path``.

    - Preserves hunks that already include ``---`` / ``+++`` headers.
    - Prepends ``--- a/{file}`` and ``+++ b/{file}`` when headers are missing.
    - Leaves placeholder diffs untouched (mock/no-fix path).
    """
    if not raw or not raw.strip() or "placeholder diff" in raw:
        return raw

    lines = _strip_git_metadata(raw.strip().splitlines())
    has_minus = any(_MINUS_FILE_RE.match(line) for line in lines)
    has_plus = any(_PLUS_FILE_RE.match(line) for line in lines)

    body = "\n".join(lines)
    if not (has_minus and has_plus):
        body = f"--- a/{file_path}\n+++ b/{file_path}\n{body}"

    if not body.endswith("\n"):
        body += "\n"
    return body
