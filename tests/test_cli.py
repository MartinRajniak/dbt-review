from pathlib import Path

from dbt_review.cli import EXIT_OK, EXIT_TOOL_FAILED, main

FANOUT_DIFF = str(Path(__file__).parent.parent / "examples" / "fanout-join" / "input.diff")


def test_no_input_is_a_tool_failure_not_a_review_result(capsys):
    assert main([]) == EXIT_TOOL_FAILED
    assert "nothing to review" in capsys.readouterr().err


def test_diff_file_is_reviewed_and_the_report_printed(capsys):
    assert main(["--diff", FANOUT_DIFF]) == EXIT_OK
    assert capsys.readouterr().out.startswith("dbt-review · 2 files changed")


def test_unreadable_diff_file_is_a_tool_failure(tmp_path, capsys):
    assert main(["--diff", str(tmp_path / "missing.diff")]) == EXIT_TOOL_FAILED
    assert "cannot read diff file" in capsys.readouterr().err
