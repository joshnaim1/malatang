"""Contract validation at the Judge boundary (SOW section 5).

The Judge is the cheat-proof gate, so it validates the mutation it receives
against the frozen ``mutation.schema.json`` and its own verdict against
``verdict.schema.json`` before returning. Kept self-contained (no dependency on
the Creator half) so the two sides only share the schema files, never code.
Schemas are read-only here — any change routes through a joint PR.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from jsonschema import Draft202012Validator

from harness.config import REPO_ROOT

CONTRACTS_DIR = REPO_ROOT / "contracts"
MUTATION_SCHEMA_PATH = CONTRACTS_DIR / "mutation.schema.json"
VERDICT_SCHEMA_PATH = CONTRACTS_DIR / "verdict.schema.json"


@lru_cache(maxsize=None)
def _validator(path_str: str) -> Draft202012Validator:
    schema = json.loads((CONTRACTS_DIR / path_str).read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def validate_mutation(payload: dict[str, Any]) -> dict[str, Any]:
    """Raise ValueError if the incoming mutation violates the frozen contract."""
    errors = sorted(
        _validator("mutation.schema.json").iter_errors(payload),
        key=lambda e: list(e.path),
    )
    if errors:
        joined = "; ".join(f"{list(e.path)}: {e.message}" for e in errors)
        raise ValueError(f"mutation does not match contract: {joined}")
    return payload


def validate_verdict(payload: dict[str, Any]) -> dict[str, Any]:
    """Raise ValueError if the outgoing verdict violates the frozen contract."""
    errors = sorted(
        _validator("verdict.schema.json").iter_errors(payload),
        key=lambda e: list(e.path),
    )
    if errors:
        joined = "; ".join(f"{list(e.path)}: {e.message}" for e in errors)
        raise ValueError(f"verdict does not match contract: {joined}")
    return payload
