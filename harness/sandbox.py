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


def _node_bin(workdir: Path, package: str, rel: str) -> Path | None:
    """Resolve a package's CLI entry inside the sandbox node_modules."""
    candidate = workdir / "node_modules" / package / rel
    return candidate if candidate.exists() else None


def _build_command(workdir: Path) -> list[str]:
    """`npm run build` semantics, but skip the npm wrapper's process startup."""
    vite = _node_bin(workdir, "vite", "bin/vite.js")
    if vite is not None:
        return ["node", str(vite), "build"]
    return [_npm_command(), "run", "build"]


def _test_command(workdir: Path) -> list[str]:
    """`npm test` semantics, invoking vitest directly to save startup time."""
    vitest = _node_bin(workdir, "vitest", "vitest.mjs")
    if vitest is not None:
        return ["node", str(vitest), "run"]
    return [_npm_command(), "run", "test"]


def _link_dependencies(source: Path, target: Path) -> None:
    """Link node_modules into the sandbox instead of copying it.

    Copying node_modules per attempt dominates sandbox wall time. A junction
    (Windows) or symlink (POSIX) is transparent to vite/vitest and avoids the
    copy. Falls back to a full copy if linking is unavailable.
    """
    if not source.is_dir():
        return
    try:
        if os.name == "nt":
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(target), str(source)],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                return
        else:
            os.symlink(source, target, target_is_directory=True)
            return
    except OSError:
        pass
    shutil.copytree(source, target)


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

    _link_dependencies(root / "node_modules", temp_dir / "node_modules")

    return temp_dir


def cleanup_sandbox(workdir: Path) -> None:
    # Remove a linked node_modules first so rmtree never recurses into the real
    # dependency tree (a junction/symlink points back at the repo copy).
    node_modules = workdir / "node_modules"
    try:
        if node_modules.is_symlink():
            node_modules.unlink()
        elif os.name == "nt" and node_modules.is_dir():
            try:
                os.rmdir(node_modules)  # removes a junction, not its target
            except OSError:
                pass  # a real copied dir; rmtree will handle it
    except OSError:
        pass
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
    started = time.perf_counter()

    ensure_dependencies(workdir, timeout)

    build = _run(_build_command(workdir), workdir, timeout)
    build_passed = build.returncode == 0

    tests_passed = False
    test_output = ""
    if build_passed:
        tests = _run(_test_command(workdir), workdir, timeout)
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
