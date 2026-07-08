"""Observer stage: detect and localize the failure.

In the live-heal / benchmark flow the Observer reads build/console/test output
and identifies the offending file. For v0 the failure signal and target file
already come packaged in ``BugContext`` (built from Person B's benchmark data),
so the Observer's job here is deterministic normalization into an
``Observation`` the downstream RCA/Planner/Fix stages consume.
"""

from __future__ import annotations

from dataclasses import dataclass

from creator.bug_context import BugContext


@dataclass(frozen=True)
class Observation:
    bug_id: str
    bug_class: str
    file_path: str
    symptom: str
    buggy_source: str


def observe(ctx: BugContext) -> Observation:
    symptom = ctx.failing_output.strip() or "unknown failure"
    return Observation(
        bug_id=ctx.bug_id,
        bug_class=ctx.bug_class,
        file_path=ctx.file_path,
        symptom=symptom,
        buggy_source=ctx.buggy_source,
    )
