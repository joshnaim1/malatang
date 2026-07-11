from __future__ import annotations

from pathlib import Path

from scripts.audit_wins import audit_wins, print_report

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "audit"


def test_audit_flags_clean_and_contaminated_wins(capsys) -> None:
    summaries = audit_wins(FIXTURE_ROOT)

    assert summaries["iter0"]["wins_checked"] == 2
    assert summaries["iter0"]["contaminated_count"] == 1
    assert summaries["iter0"]["offenders"] == [
        {
            "bug_id": "contaminated-win",
            "paths": ["lib/stats.test.js"],
        }
    ]

    exit_code = print_report(summaries)
    output = capsys.readouterr().out
    assert exit_code == 1
    assert "clean-win" not in output
    assert "contaminated-win: lib/stats.test.js" in output
