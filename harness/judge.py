"""Judge: apply mutation in sandbox and emit verdict JSON."""

from __future__ import annotations

import json
from pathlib import Path
import shlex
from typing import Any

from harness.config import REPO_ROOT
from harness.contracts import validate_mutation, validate_verdict
from harness.sandbox import (
    GateResult,
    apply_unified_diff,
    cleanup_sandbox,
    clone_repo_to_temp,
    run_build_and_tests,
)

PROTECTED_FILENAMES = {
    "package.json",
    "package-lock.json",
    "vite.config.js",
}
PROTECTED_TOP_LEVEL_DIRS = {
    "harness",
    "creator",
    "contracts",
    "benchmark",
    "playbook",
    "results",
    "trajectories",
    "scripts",
}


def _normalize_diff_path(raw: str) -> str | None:
    """Normalize one path token from a git/unified diff."""
    path = raw.strip().split("\t", 1)[0].strip()
    if not path or path == "/dev/null":
        return None
    if len(path) >= 2 and path[0] == path[-1] == '"':
        path = path[1:-1]
    if path.startswith(("a/", "b/")):
        path = path[2:]
    while path.startswith("./"):
        path = path[2:]
    return path.replace("\\", "/")


def parse_touched_paths(diff_text: str) -> set[str]:
    """Return every file path declared by a unified diff.

    Both ``diff --git`` metadata and ``---``/``+++`` file headers are parsed so
    the protected-files gate and the offline win audit share one source of truth.
    """
    paths: set[str] = set()
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            try:
                parts = shlex.split(line)
            except ValueError:
                parts = line.split()
            for raw in parts[2:4]:
                normalized = _normalize_diff_path(raw)
                if normalized:
                    paths.add(normalized)
        elif line.startswith("--- ") or line.startswith("+++ "):
            normalized = _normalize_diff_path(line[4:])
            if normalized:
                paths.add(normalized)
    return paths


def is_protected_path(path: str) -> bool:
    """Whether a Creator fix is forbidden from touching ``path``."""
    normalized = path.replace("\\", "/").lstrip("/")
    parts = [part for part in normalized.split("/") if part not in {"", "."}]
    if not parts or ".." in parts:
        return True
    if parts[0] in PROTECTED_TOP_LEVEL_DIRS:
        return True
    name = parts[-1]
    return name.endswith(".test.js") or name in PROTECTED_FILENAMES


def protected_paths_in_diff(diff_text: str) -> set[str]:
    return {path for path in parse_touched_paths(diff_text) if is_protected_path(path)}


def _summarize_gate(gate: GateResult) -> str:
    if gate.build_passed and gate.tests_passed:
        return "build and tests passed"
    if not gate.build_passed:
        tail = gate.build_output.strip().splitlines()
        hint = tail[-1] if tail else "build failed"
        return f"build failed: {hint[:200]}"
    tail = gate.test_output.strip().splitlines()
    hint = tail[-1] if tail else "tests failed"
    return f"tests failed: {hint[:200]}"


def _summarize_apply_failure(exc: Exception) -> str:
    """One-line note for a fix diff the sandbox could not apply.

    A malformed/unapplyable diff from the Creator is a legitimate rejection, not
    an error the harness should crash on. Kept short so it fits the verdict.
    """
    detail = str(exc).strip().splitlines()
    hint = detail[-1] if detail else "git apply failed"
    return f"fix diff did not apply: {hint[:180]}"


def _detect_regression(gate: GateResult) -> bool:
    """Real, deterministic regression signal.

    A regression means the fix compiles but leaves the suite red — the change
    builds yet behaviour is still wrong. A build failure is a build break, not a
    regression, and an accepted fix (build + tests green) has no regression.
    This never overrides the binary gate; it is a diagnostic flag only.
    """
    return gate.build_passed and not gate.tests_passed


def _rejected_verdict(bug_id: str, attempt: int, notes: str) -> dict[str, Any]:
    return validate_verdict(
        {
            "bug_id": bug_id,
            "attempt": attempt,
            "accepted": False,
            "build_passed": False,
            "tests_passed": False,
            "regression_detected": False,
            "wall_time_s": 0.0,
            "notes": notes,
        }
    )


def verify_mutation(
    mutation_payload: dict[str, Any],
    bug_patch_text: str,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    # Cheat-proof boundary: reject anything that violates the frozen contract
    # before it ever touches the sandbox.
    validate_mutation(mutation_payload)
    mutation = mutation_payload["mutation"]
    bug_id = mutation["bug_id"]
    attempt = mutation["attempt"]
    fix_diff = mutation["diff"]

    protected = sorted(protected_paths_in_diff(fix_diff))
    if protected:
        return _rejected_verdict(
            bug_id,
            attempt,
            f"protected file rejected: {', '.join(protected)}",
        )

    workdir = clone_repo_to_temp(repo_root)
    try:
        apply_unified_diff(workdir, bug_patch_text, label="bug")
        if fix_diff.strip() and "placeholder diff" not in fix_diff:
            try:
                apply_unified_diff(workdir, fix_diff, label="fix")
            except RuntimeError as exc:
                # A contract-valid diff that will not apply is a failed attempt,
                # not a harness crash. Score it as a clean reject so unattended
                # benchmark runs never abort on malformed Creator output.
                return validate_verdict(
                    {
                        "bug_id": bug_id,
                        "attempt": attempt,
                        "accepted": False,
                        "build_passed": False,
                        "tests_passed": False,
                        "regression_detected": False,
                        "wall_time_s": 0.0,
                        "notes": _summarize_apply_failure(exc),
                    }
                )
        gate = run_build_and_tests(workdir)
    finally:
        cleanup_sandbox(workdir)

    accepted = gate.build_passed and gate.tests_passed
    verdict = {
        "bug_id": bug_id,
        "attempt": attempt,
        "accepted": accepted,
        "build_passed": gate.build_passed,
        "tests_passed": gate.tests_passed,
        "regression_detected": _detect_regression(gate),
        "wall_time_s": round(gate.wall_time_s, 2),
        "notes": _summarize_gate(gate),
    }
    return validate_verdict(verdict)


def verify_bug_state(bug_patch_text: str, repo_root: Path | None = None) -> GateResult:
    """Apply only the bug patch; used to confirm seeded bugs break the gate."""
    workdir = clone_repo_to_temp(repo_root)
    try:
        apply_unified_diff(workdir, bug_patch_text, label="bug")
        return run_build_and_tests(workdir)
    finally:
        cleanup_sandbox(workdir)


def write_verdict(verdict: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
