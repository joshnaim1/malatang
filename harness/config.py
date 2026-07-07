"""Load configuration from environment variables (SOW section 10)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]

load_dotenv(REPO_ROOT / ".env")


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def require_env_int(name: str) -> int:
    raw = require_env(name)
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(
            f"Environment variable {name} must be an integer, got: {raw!r}"
        ) from exc


def require_env_float(name: str) -> float:
    raw = require_env(name)
    try:
        return float(raw)
    except ValueError as exc:
        raise RuntimeError(
            f"Environment variable {name} must be a number, got: {raw!r}"
        ) from exc


def sandbox_timeout_s() -> int:
    return require_env_int("SANDBOX_TIMEOUT_S")


def benchmark_attempts_per_bug() -> int:
    return require_env_int("BENCHMARK_ATTEMPTS_PER_BUG")
