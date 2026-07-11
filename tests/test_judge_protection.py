from __future__ import annotations

import pytest

from harness import judge


def _mutation(diff: str) -> dict:
    return {
        "mutation": {
            "iteration": 0,
            "playbook_version": "v0",
            "bug_id": "syntax-001",
            "attempt": 1,
            "type": "code",
            "trigger": "benchmark",
            "file": "src/App.jsx",
            "diff": diff,
            "reasoning": "test",
            "model": "fixture",
        }
    }


@pytest.mark.parametrize(
    ("path", "protected"),
    [
        ("src/App.jsx", False),
        ("lib/stats.js", False),
        ("lib/stats.test.js", True),
        ("package.json", True),
        ("package-lock.json", True),
        ("vite.config.js", True),
        ("harness/judge.py", True),
        ("creator/fix.py", True),
        ("contracts/verdict.schema.json", True),
        ("benchmark/manifest.json", True),
        ("playbook/v0.md", True),
        ("results/metrics.jsonl", True),
        ("trajectories/iter0/win.json", True),
        ("scripts/reflect.py", True),
    ],
)
def test_protected_path_patterns(path: str, protected: bool) -> None:
    assert judge.is_protected_path(path) is protected


def test_parse_touched_paths_reads_git_and_file_headers() -> None:
    diff = """\
diff --git a/src/App.jsx b/src/App.jsx
--- a/src/App.jsx
+++ b/src/App.jsx
@@ -1 +1 @@
-old
+new
"""
    assert judge.parse_touched_paths(diff) == {"src/App.jsx"}


def test_protected_diff_rejected_before_sandbox(monkeypatch: pytest.MonkeyPatch) -> None:
    diff = """\
--- a/lib/stats.test.js
+++ b/lib/stats.test.js
@@ -1 +1 @@
-old
+new
"""

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("sandbox must not be created for protected diffs")

    monkeypatch.setattr(judge, "clone_repo_to_temp", fail_if_called)
    verdict = judge.verify_mutation(_mutation(diff), "unused bug patch")

    assert verdict["accepted"] is False
    assert verdict["build_passed"] is False
    assert verdict["tests_passed"] is False
    assert verdict["wall_time_s"] == 0.0
    assert "protected file rejected" in verdict["notes"]
    assert "lib/stats.test.js" in verdict["notes"]
