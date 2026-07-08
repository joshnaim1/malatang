"""Fake Judge (Person A's mock of Person B's side).

Per SOW section 5: "Person A's fake Judge returns example_verdict.json with
randomized `accepted`." This lets the Creator half run end-to-end in isolation
before integration. It does NOT verify anything (no build, no tests) — the real,
deterministic Judge lives in ``harness/judge.py`` and is Person B's. This mock
only validates the incoming mutation against the frozen contract and returns a
contract-valid verdict.
"""

from __future__ import annotations

import random
from typing import Any

from creator import contracts


def judge(mutation_payload: dict[str, Any], *, rng: random.Random | None = None) -> dict[str, Any]:
    contracts.validate_mutation(mutation_payload)
    mutation = mutation_payload["mutation"]
    rng = rng or random.Random()

    verdict = contracts.load_example_verdict()
    verdict["bug_id"] = mutation["bug_id"]
    verdict["attempt"] = mutation["attempt"]

    accepted = rng.random() < 0.5
    verdict["accepted"] = accepted
    if accepted:
        verdict["build_passed"] = True
        verdict["tests_passed"] = True
        verdict["regression_detected"] = False
        verdict["notes"] = "mock accept — randomized fake Judge (no real verification)"
    else:
        # not accepted: build broke, or built but tests failed (regression)
        build_passed = rng.random() < 0.5
        verdict["build_passed"] = build_passed
        verdict["tests_passed"] = False
        verdict["regression_detected"] = build_passed
        verdict["notes"] = "mock reject — randomized fake Judge (no real verification)"
    verdict["wall_time_s"] = round(rng.uniform(5.0, 60.0), 1)

    return contracts.validate_verdict(verdict)
