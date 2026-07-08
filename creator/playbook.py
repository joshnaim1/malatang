"""Playbook versioning helpers.

The playbook is a markdown file per version under ``playbook/`` (``v0.md``,
``v1.md``, ...). ``playbook_version`` in the mutation contract is the ``vN`` stem
of whichever file was injected into the Creator's system prompt.
"""

from __future__ import annotations

import re
from pathlib import Path

from creator.config import PLAYBOOK_DIR

_VERSION_RE = re.compile(r"^v(\d+)\.md$")


def playbook_path(version: str) -> Path:
    return PLAYBOOK_DIR / f"{version}.md"


def load_playbook(version: str) -> str:
    path = playbook_path(version)
    if not path.exists():
        raise FileNotFoundError(f"playbook version not found: {path}")
    return path.read_text(encoding="utf-8")


def latest_version() -> str:
    versions = []
    for p in PLAYBOOK_DIR.glob("v*.md"):
        m = _VERSION_RE.match(p.name)
        if m:
            versions.append(int(m.group(1)))
    if not versions:
        raise FileNotFoundError(f"no playbook versions found in {PLAYBOOK_DIR}")
    return f"v{max(versions)}"


def next_version(current: str) -> str:
    n = int(current.lstrip("v"))
    return f"v{n + 1}"
