from __future__ import annotations

import asyncio
from collections import Counter
from pathlib import Path
import shutil

import pytest

from creator import playbook, reflection

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "trajectories"


def _record(
    bug_id: str,
    bug_class: str,
    *,
    accepted: bool = False,
    notes: str = "tests failed: fixture",
) -> dict:
    return {
        "bug_id": bug_id,
        "bug_class": bug_class,
        "accepted": accepted,
        "mutation": {
            "mutation": {
                "reasoning": f"reasoning for {bug_id}",
                "diff": "--- a/src/App.jsx\n+++ b/src/App.jsx\n@@ -1 +1 @@\n-old\n+new\n",
            }
        },
        "verdict": {"notes": notes},
    }


def test_failure_sampling_respects_class_and_total_caps() -> None:
    classes = ["syntax", "off-by-one", "null-handling", "wrong-api", "async"]
    modes = [
        "fix diff did not apply: fixture",
        "build failed: fixture",
        "tests failed: fixture",
        "other rejection",
    ]
    failures = [
        _record(f"{bug_class}-{i}", bug_class, notes=modes[i % len(modes)])
        for bug_class in classes
        for i in range(8)
    ]

    sampled = reflection.sample_failures(failures)
    counts = Counter(record["bug_class"] for record in sampled)

    assert len(sampled) == reflection.MAX_FAILURES_TOTAL
    assert all(count <= reflection.MAX_FAILURES_PER_CLASS for count in counts.values())


def test_failure_sampling_prioritizes_bucket_diversity() -> None:
    failures = [
        _record("apply", "syntax", notes="fix diff did not apply: fixture"),
        _record("build", "syntax", notes="build failed: fixture"),
        _record("tests", "syntax", notes="tests failed: fixture"),
        *[
            _record(f"other-{i}", "syntax", notes="generic reject")
            for i in range(10)
        ],
    ]

    sampled = reflection.sample_failures(failures)
    modes = {reflection.failure_mode(record) for record in sampled}

    assert {"diff_apply", "build", "tests"}.issubset(modes)
    assert len(sampled) == reflection.MAX_FAILURES_PER_CLASS


def test_fewshot_selection_covers_distinct_strategic_classes() -> None:
    wins = [
        _record("api-first", "wrong-api", accepted=True),
        _record("syntax", "syntax", accepted=True),
        _record("offbyone", "off-by-one", accepted=True),
        _record("async", "async", accepted=True),
    ]

    selected = reflection.select_fewshot_wins(wins)

    assert [record["bug_class"] for record in selected] == [
        "syntax",
        "off-by-one",
        "wrong-api",
    ]


def test_prompt_uses_bounded_failures_without_failure_diffs() -> None:
    wins = [_record("syntax-win", "syntax", accepted=True)]
    failures = [
        _record(
            "syntax-fail",
            "syntax",
            notes="fix diff did not apply: bad hunk",
        )
    ]
    traj = reflection.IterationTrajectories(0, wins=wins, failures=failures)

    messages = reflection.build_reflection_prompt(
        "# Creator Strategy Playbook — v0\n\n## Rules\n\nKeep fixes small.",
        traj,
        current_version="v0",
        next_version="v1",
    )
    user = messages[1]["content"]

    assert "mode=diff_apply" in user
    assert "syntax-fail [syntax]" in user
    assert "reasoning tail:" in user
    assert user.count("```diff") == 1  # only the selected win includes a diff
    assert f"under {reflection.PLAYBOOK_MAX_WORDS} words" in messages[0]["content"]


def test_dry_run_writes_valid_labeled_next_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    playbook_dir = tmp_path / "playbook"
    playbook_dir.mkdir()
    shutil.copy(Path("playbook/v0.md"), playbook_dir / "v0.md")
    monkeypatch.setattr(reflection, "TRAJECTORIES_DIR", FIXTURE_ROOT)
    monkeypatch.setattr(playbook, "PLAYBOOK_DIR", playbook_dir)

    version, output_path = asyncio.run(reflection.reflect(0, dry_run=True))
    generated = Path(output_path).read_text(encoding="utf-8")

    assert version == "v1"
    assert generated.startswith("# Creator Strategy Playbook — v1 (DRY-RUN)")
    assert "Fireworks was not called" in generated
    assert generated != (playbook_dir / "v0.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("generated", ["", "same"])
def test_guardrail_rejects_empty_or_identical_output(generated: str) -> None:
    current = "same"
    with pytest.raises(ValueError, match="refusing to write"):
        reflection.validate_generated_playbook(generated, current)
