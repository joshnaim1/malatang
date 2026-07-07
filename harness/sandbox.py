"""Sandbox: tempdir clone, patch apply, build + test gate."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from harness.config import REPO_ROOT, sandbox_timeout_s

SANDBOX_COPY_PATHS = (
    "src",
    "lib",
    "index.html",
    "package.json",
    "package-lock.json",
    "vite.config.js",
)


@dataclass
class GateResult:
    build_passed: bool
    tests_passed: bool
    build_output: str
    test_output: str
    wall_time_s: float


def _npm_command() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def clone_repo_to_temp(repo_root: Path | None = None) -> Path:
    root = repo_root or REPO_ROOT
    temp_dir = Path(tempfile.mkdtemp(prefix="malatang-sandbox-"))
    for rel in SANDBOX_COPY_PATHS:
        source = root / rel
        if not source.exists():
            continue
        target = temp_dir / rel
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    node_modules = root / "node_modules"
    if node_modules.is_dir():
        shutil.copytree(node_modules, temp_dir / "node_modules")

    return temp_dir


def cleanup_sandbox(workdir: Path) -> None:
    shutil.rmtree(workdir, ignore_errors=True)


def _strip_patch_comments(patch_text: str) -> str:
    lines = patch_text.splitlines()
    while lines and lines[0].startswith("#"):
        lines.pop(0)
    while lines and lines[0].strip() == "":
        lines.pop(0)
    return "\n".join(lines) + ("\n" if lines else "")


def apply_unified_diff(workdir: Path, diff_text: str, label: str) -> None:
    diff_text = _strip_patch_comments(diff_text)
    if not diff_text or not diff_text.strip():
        raise ValueError(f"{label}: diff is empty")

    patch_path = workdir / f".{label}.patch"
    patch_path.write_text(diff_text, encoding="utf-8")

    init = subprocess.run(
        ["git", "init"],
        cwd=workdir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if init.returncode != 0:
        raise RuntimeError(f"git init failed: {init.stderr}")

    subprocess.run(
        ["git", "add", "-A"],
        cwd=workdir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    apply = subprocess.run(
        ["git", "apply", "--whitespace=nowarn", str(patch_path)],
        cwd=workdir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if apply.returncode != 0:
        raise RuntimeError(
            f"git apply failed for {label}: {apply.stderr or apply.stdout}"
        )


def _run(cmd: list[str], workdir: Path, timeout_s: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=workdir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_s,
        check=False,
    )


def ensure_dependencies(workdir: Path, timeout_s: int) -> None:
    if (workdir / "node_modules").is_dir():
        return
    npm = _npm_command()
    install = _run([npm, "ci"], workdir, timeout_s)
    if install.returncode != 0:
        install = _run([npm, "install"], workdir, timeout_s)
    if install.returncode != 0:
        raise RuntimeError(
            "npm install failed:\n"
            f"{install.stdout}\n{install.stderr}"
        )


def run_build_and_tests(workdir: Path, timeout_s: int | None = None) -> GateResult:
    timeout = timeout_s if timeout_s is not None else sandbox_timeout_s()
    npm = _npm_command()
    started = time.perf_counter()

    ensure_dependencies(workdir, timeout)

    build = _run([npm, "run", "build"], workdir, timeout)
    build_passed = build.returncode == 0

    tests_passed = False
    test_output = ""
    if build_passed:
        tests = _run([npm, "run", "test"], workdir, timeout)
        tests_passed = tests.returncode == 0
        test_output = (tests.stdout or "") + (tests.stderr or "")
    else:
        test_output = "skipped: build failed"

    wall_time_s = time.perf_counter() - started
    build_output = (build.stdout or "") + (build.stderr or "")

    return GateResult(
        build_passed=build_passed,
        tests_passed=tests_passed,
        build_output=build_output,
        test_output=test_output,
        wall_time_s=wall_time_s,
    )
