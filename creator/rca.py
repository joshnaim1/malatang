"""Root-cause analysis stage.

Provides the instruction fragment that asks the model to explain *why* the code
fails (not just where), and parses the ``root_cause`` field out of the Creator's
structured response. For v0 RCA, planning, and fix generation share a single
Creator call (cost: 25 bugs x K attempts x M iterations makes extra round-trips
expensive); the stages remain separate functions so they can be split later.
"""

from __future__ import annotations

from creator.observer import Observation

RCA_INSTRUCTION = (
    "Root cause: state the single underlying defect in one sentence. "
    "Tie it to the bug class when possible."
)


def rca_context(obs: Observation) -> str:
    return (
        f"Bug class: {obs.bug_class}\n"
        f"Observed symptom: {obs.symptom}\n"
        f"Target file: {obs.file_path}"
    )
