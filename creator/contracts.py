"""Frozen-contract loading and validation (SOW section 5).

The schemas and example payloads in ``contracts/`` are the single interface
between the Creator and the Judge. This module only READS them and validates
payloads against them; it never mutates a schema. If a contract change ever
seems necessary, stop and route it through a PR to Person B — do not edit the
files under ``contracts/`` from the Creator half.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from jsonschema import Draft202012Validator

from creator.config import CONTRACTS_DIR

MUTATION_SCHEMA_PATH = CONTRACTS_DIR / "mutation.schema.json"
VERDICT_SCHEMA_PATH = CONTRACTS_DIR / "verdict.schema.json"
EXAMPLE_MUTATION_PATH = CONTRACTS_DIR / "example_mutation.json"
EXAMPLE_VERDICT_PATH = CONTRACTS_DIR / "example_verdict.json"


def _load_json(path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def _mutation_validator() -> Draft202012Validator:
    return Draft202012Validator(_load_json(MUTATION_SCHEMA_PATH))


@lru_cache(maxsize=None)
def _verdict_validator() -> Draft202012Validator:
    return Draft202012Validator(_load_json(VERDICT_SCHEMA_PATH))


def validate_mutation(payload: dict[str, Any]) -> dict[str, Any]:
    """Raise if ``payload`` does not match the frozen mutation contract."""
    errors = sorted(_mutation_validator().iter_errors(payload), key=lambda e: e.path)
    if errors:
        joined = "; ".join(f"{list(e.path)}: {e.message}" for e in errors)
        raise ValueError(f"mutation does not match contract: {joined}")
    return payload


def validate_verdict(payload: dict[str, Any]) -> dict[str, Any]:
    """Raise if ``payload`` does not match the frozen verdict contract."""
    errors = sorted(_verdict_validator().iter_errors(payload), key=lambda e: e.path)
    if errors:
        joined = "; ".join(f"{list(e.path)}: {e.message}" for e in errors)
        raise ValueError(f"verdict does not match contract: {joined}")
    return payload


def load_example_mutation() -> dict[str, Any]:
    return _load_json(EXAMPLE_MUTATION_PATH)


def load_example_verdict() -> dict[str, Any]:
    return _load_json(EXAMPLE_VERDICT_PATH)
