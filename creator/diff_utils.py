"""Normalize Creator fix diffs so the Judge sandbox can apply them.

The live model often emits hunks without ``--- a/`` / ``+++ b/`` headers, or with
wrong ``@@`` line numbers / context lines. The Judge applies fix diffs with
``git apply``, which requires valid headers and matching context. We synthesize
headers from the known target file and re-anchor hunks against the buggy source.
"""

from __future__ import annotations

import difflib
import re

_DIFF_GIT_RE = re.compile(r"^diff --git ")
_INDEX_RE = re.compile(r"^index [0-9a-f]+\.\.[0-9a-f]+")
_MINUS_FILE_RE = re.compile(r"^--- ")
_PLUS_FILE_RE = re.compile(r"^\+\+\+ ")
_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def _strip_git_metadata(lines: list[str]) -> list[str]:
    """Drop ``diff --git`` / ``index`` lines the model sometimes echoes."""
    out: list[str] = []
    for line in lines:
        if _DIFF_GIT_RE.match(line) or _INDEX_RE.match(line):
            continue
        out.append(line)
    return out


def _split_hunks(lines: list[str]) -> list[list[str]]:
    """Return hunks (``@@`` header plus body lines)."""
    hunks: list[list[str]] = []
    current: list[str] = []
    in_hunk = False
    for line in lines:
        if _MINUS_FILE_RE.match(line) or _PLUS_FILE_RE.match(line):
            continue
        if _HUNK_RE.match(line):
            if current:
                hunks.append(current)
            current = [line]
            in_hunk = True
            continue
        if in_hunk:
            current.append(line)
    if current:
        hunks.append(current)
    return hunks


def _hunk_old_new(hunk: list[str]) -> tuple[list[str], list[str]]:
    """Extract old-file and new-file line sequences from one hunk."""
    old_lines: list[str] = []
    new_lines: list[str] = []
    for line in hunk[1:]:
        if line.startswith(" "):
            old_lines.append(line[1:])
            new_lines.append(line[1:])
        elif line.startswith("-"):
            old_lines.append(line[1:])
        elif line.startswith("+"):
            new_lines.append(line[1:])
    return old_lines, new_lines


def _find_block(source_lines: list[str], block: list[str]) -> int | None:
    if not block:
        return None
    n = len(block)
    for start in range(len(source_lines) - n + 1):
        if source_lines[start : start + n] == block:
            return start
    return None


def _find_removals(source_lines: list[str], removals: list[str]) -> int | None:
    if len(removals) != 1:
        return None
    target = removals[0]
    for i, line in enumerate(source_lines):
        if line == target:
            return i
    return None


def _locate_change(
    source_lines: list[str], hunk: list[str]
) -> tuple[int, list[str], list[str]] | None:
    old_chunk, new_chunk = _hunk_old_new(hunk)
    if not old_chunk and not new_chunk:
        return None
    start = _find_block(source_lines, old_chunk)
    if start is None:
        removals = [
            line[1:]
            for line in hunk[1:]
            if line.startswith("-") and not line.startswith("---")
        ]
        additions = [
            line[1:]
            for line in hunk[1:]
            if line.startswith("+") and not line.startswith("+++")
        ]
        start = _find_removals(source_lines, removals)
        if start is not None:
            old_chunk = [removals[0]]
            new_chunk = additions if additions else [removals[0]]
    if start is None:
        return None
    return start, old_chunk, new_chunk


def _reanchor_against_source(file_path: str, buggy_source: str, lines: list[str]) -> str | None:
    """Rebuild a full-file unified diff with correct ``@@`` line numbers."""
    source_lines = buggy_source.splitlines()
    hunks = _split_hunks(lines)
    if not hunks:
        return None

    changes: list[tuple[int, list[str], list[str]]] = []
    for hunk in hunks:
        located = _locate_change(source_lines, hunk)
        if located is None:
            return None
        changes.append(located)

    new_lines = list(source_lines)
    for start, old_chunk, new_chunk in sorted(changes, key=lambda c: c[0], reverse=True):
        new_lines = new_lines[:start] + new_chunk + new_lines[start + len(old_chunk) :]

    if new_lines == source_lines:
        return None

    diff_lines = difflib.unified_diff(
        source_lines,
        new_lines,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
        lineterm="",
        n=3,
    )
    out = list(diff_lines)
    if not out:
        return None
    body = "\n".join(out)
    if not body.endswith("\n"):
        body += "\n"
    return body


def normalize_fix_diff(
    file_path: str,
    raw: str,
    *,
    buggy_source: str | None = None,
) -> str:
    """Return a unified diff ``git apply`` can consume for ``file_path``.

    - Prepends ``--- a/{file}`` / ``+++ b/{file}`` when headers are missing.
    - When ``buggy_source`` is provided, re-anchors hunks so line numbers and
      context match the post-bug file (fixes wrong context from the model).
    - Leaves placeholder diffs untouched (mock/no-fix path).
    """
    if not raw or not raw.strip() or "placeholder diff" in raw:
        return raw

    lines = _strip_git_metadata(raw.strip().splitlines())

    if buggy_source is not None:
        reanchored = _reanchor_against_source(file_path, buggy_source, lines)
        if reanchored is not None:
            return reanchored

    has_minus = any(_MINUS_FILE_RE.match(line) for line in lines)
    has_plus = any(_PLUS_FILE_RE.match(line) for line in lines)
    body = "\n".join(lines)
    if not (has_minus and has_plus):
        body = f"--- a/{file_path}\n+++ b/{file_path}\n{body}"

    if not body.endswith("\n"):
        body += "\n"
    return body
