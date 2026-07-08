"""Planner stage.

Provides the instruction fragment that asks the model to commit to a minimal,
surgical edit plan before emitting a diff. The plan is captured in the Creator's
structured response so it can be logged in trajectories and mined by the
reflection step.
"""

from __future__ import annotations

PLANNER_INSTRUCTION = (
    "Plan: describe the smallest edit that fixes the root cause without "
    "touching unrelated lines. Prefer a one- or two-line change."
)
