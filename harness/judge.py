"""Judge: apply mutation in sandbox and emit verdict JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from harness.config import REPO_ROOT
from harness.sandbox import (
    GateResult,
    apply_unified_diff,
    cleanup_sandbox,
    clone_repo_to_temp,
    run_build_and_tests,
)


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


def _detect_regression(gate: GateResult) -> bool:
    """Real, deterministic regression signal.

    A regression means the fix compiles but leaves the suite red — the change
    builds yet behaviour is still wrong. A build failure is a build break, not a
    regression, and an accepted fix (build + tests green) has no regression.
    This never overrides the binary gate; it is a diagnostic flag only.
    """
    return gate.build_passed and not gate.tests_passed


def verify_mutation(
    mutation_payload: dict[str, Any],
    bug_patch_text: str,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    mutation = mutation_payload["mutation"]
    bug_id = mutation["bug_id"]
    attempt = mutation["attempt"]
    fix_diff = mutation["diff"]

    workdir = clone_repo_to_temp(repo_root)
    try:
        apply_unified_diff(workdir, bug_patch_text, label="bug")
        if fix_diff.strip() and "placeholder diff" not in fix_diff:
            apply_unified_diff(workdir, fix_diff, label="fix")
        gate = run_build_and_tests(workdir)
    finally:
        cleanup_sandbox(workdir)

    accepted = gate.build_passed and gate.tests_passed
    return {
        "bug_id": bug_id,
        "attempt": attempt,
        "accepted": accepted,
        "build_passed": gate.build_passed,
        "tests_passed": gate.tests_passed,
        "regression_detected": _detect_regression(gate),
        "wall_time_s": round(gate.wall_time_s, 2),
        "notes": _summarize_gate(gate),
    }


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
