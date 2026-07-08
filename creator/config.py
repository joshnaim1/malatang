"""Configuration for the Creator half, loaded from env vars (SOW section 10).

Fails loudly with the missing variable name, per SOW section 0. Secrets are
never hardcoded and never committed; values come from ``.env`` (gitignored) or
the process environment. This mirrors the fail-loud pattern in
``harness/config.py`` but is kept self-contained so the Creator half does not
couple to Person B's module.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACTS_DIR = REPO_ROOT / "contracts"
PLAYBOOK_DIR = REPO_ROOT / "playbook"
TRAJECTORIES_DIR = REPO_ROOT / "trajectories"
RESULTS_DIR = REPO_ROOT / "results"

load_dotenv(REPO_ROOT / ".env")


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        raise RuntimeError(
            f"Missing required environment variable: {name} "
            f"(set it in {REPO_ROOT / '.env'} or the environment; see .env.example)"
        )
    return value


def require_env_float(name: str) -> float:
    raw = require_env(name)
    try:
        return float(raw)
    except ValueError as exc:
        raise RuntimeError(
            f"Environment variable {name} must be a number, got: {raw!r}"
        ) from exc


def optional_env(name: str, default: str) -> str:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value


# --- vLLM (self-hosted Creator model on MI300X) ---

def vllm_base_url() -> str:
    return require_env("VLLM_BASE_URL")


def vllm_api_key() -> str:
    return require_env("VLLM_API_KEY")


def creator_model() -> str:
    return require_env("CREATOR_MODEL")


# --- Fireworks (reflection / playbook rewriting) ---

def fireworks_base_url() -> str:
    return require_env("FIREWORKS_BASE_URL")


def fireworks_api_key() -> str:
    return require_env("FIREWORKS_API_KEY")


def fireworks_model() -> str:
    return require_env("FIREWORKS_MODEL")


# --- Sampling ---

def benchmark_temperature() -> float:
    return require_env_float("BENCHMARK_TEMPERATURE")
