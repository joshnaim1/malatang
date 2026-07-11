"""Build Creator input ("bug context") from the benchmark set.

SOW defines Creator input as "failing build/test output + relevant file". This
module assembles that from Person B's benchmark artifacts, which it treats as
READ-ONLY data: it never runs the verification gate (that is the Judge's job)
and never modifies anything under ``benchmark/``.

For v0 the "relevant file" is the post-bug source (the seeded bug patch applied
to the clean file in a throwaway temp copy), and the failure signal is the
manifest's bug description. When a live build/test log is available it can be
passed in via ``failing_output`` to replace the description stand-in.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from creator.config import REPO_ROOT

BENCHMARK_DIR = REPO_ROOT / "benchmark"
TRAINING_MANIFEST = BENCHMARK_DIR / "manifest.json"
TRAINING_BUGS_DIR = BENCHMARK_DIR / "bugs"
HOLDOUT_MANIFEST = BENCHMARK_DIR / "holdout" / "manifest.json"
HOLDOUT_BUGS_DIR = BENCHMARK_DIR / "holdout"

_PLUS_FILE_RE = re.compile(r"^\+\+\+ b/(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class BugContext:
    bug_id: str
    bug_class: str
    file_path: str
    buggy_source: str
    failing_output: str
    description: str


def _strip_patch_comments(patch_text: str) -> str:
    lines = patch_text.splitlines()
    while lines and lines[0].startswith("#"):
        lines.pop(0)
    while lines and lines[0].strip() == "":
        lines.pop(0)
    return "\n".join(lines) + ("\n" if lines else "")


def _load_manifest_entry(bug_id: str) -> tuple[dict[str, str], Path]:
    for manifest, bugs_dir in (
        (TRAINING_MANIFEST, TRAINING_BUGS_DIR),
        (HOLDOUT_MANIFEST, HOLDOUT_BUGS_DIR),
    ):
        data = json.loads(manifest.read_text(encoding="utf-8"))
        for bug in data["bugs"]:
            if bug["id"] == bug_id:
                return bug, bugs_dir
    raise KeyError(
        f"bug_id not found in training or hold-out manifests: {bug_id}"
    )


def _target_file_from_patch(patch_text: str) -> str:
    match = _PLUS_FILE_RE.search(patch_text)
    if not match:
        raise ValueError("could not determine target file from bug patch")
    return match.group(1).strip()


def _apply_bug_patch(file_path: str, patch_text: str) -> str:
    """Apply the seeded bug patch to the clean file in a temp copy and return
    the resulting (buggy) source. Uses ``git apply`` against a throwaway tree so
    the real working tree is never touched."""
    tmp = Path(tempfile.mkdtemp(prefix="creator_ctx_"))
    try:
        dest = tmp / file_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / file_path, dest)
        patch_file = tmp / "bug.patch"
        patch_file.write_text(patch_text, encoding="utf-8")
        result = subprocess.run(
            ["git", "apply", "--unsafe-paths", "-p1", str(patch_file)],
            cwd=tmp,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"git apply failed for {file_path}: {result.stderr.strip()}"
            )
        return dest.read_text(encoding="utf-8")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def build_bug_context(bug_id: str, failing_output: str | None = None) -> BugContext:
    entry, bugs_dir = _load_manifest_entry(bug_id)
    patch_text = _strip_patch_comments(
        (bugs_dir / entry["patch"]).read_text(encoding="utf-8")
    )
    file_path = _target_file_from_patch(patch_text)
    buggy_source = _apply_bug_patch(file_path, patch_text)
    description = entry.get("description", "")
    return BugContext(
        bug_id=bug_id,
        bug_class=entry.get("class", "unknown"),
        file_path=file_path,
        buggy_source=buggy_source,
        failing_output=failing_output or f"Seeded failure: {description}",
        description=description,
    )
