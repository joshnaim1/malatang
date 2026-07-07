"""Shared benchmark loaders for training and hold-out bug sets."""

from __future__ import annotations

import json
from pathlib import Path

from harness.config import REPO_ROOT

TRAINING_DIR = REPO_ROOT / "benchmark" / "bugs"
TRAINING_MANIFEST = REPO_ROOT / "benchmark" / "manifest.json"
HOLDOUT_DIR = REPO_ROOT / "benchmark" / "holdout"
HOLDOUT_MANIFEST = HOLDOUT_DIR / "manifest.json"


def strip_patch_comments(patch_text: str) -> str:
    """Drop leading ``#`` description lines and blank padding from a patch."""
    lines = patch_text.splitlines()
    while lines and lines[0].startswith("#"):
        lines.pop(0)
    while lines and lines[0].strip() == "":
        lines.pop(0)
    return "\n".join(lines) + ("\n" if lines else "")


def load_manifest(manifest_path: Path) -> list[dict[str, str]]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    return data["bugs"]


def load_bug_patch(bugs_dir: Path, bug: dict[str, str]) -> str:
    patch_path = bugs_dir / bug["patch"]
    return strip_patch_comments(patch_path.read_text(encoding="utf-8"))


def load_training_bugs() -> list[dict[str, str]]:
    return load_manifest(TRAINING_MANIFEST)


def load_holdout_bugs() -> list[dict[str, str]]:
    return load_manifest(HOLDOUT_MANIFEST)
