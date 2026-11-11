import io
import json
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


def test_without_a_dbt_project_the_review_says_it_only_saw_the_diff(tmp_path, capsys):
    main(["--repo", str(tmp_path), "--diff", FANOUT_DIFF])
    assert "context: diff-only" in capsys.readouterr().out


def test_with_a_dbt_project_the_review_says_it_saw_the_repo(tmp_path, capsys):
    (tmp_path / "dbt_project.yml").write_text("name: jaffle_shop")
    main(["--repo", str(tmp_path), "--diff", FANOUT_DIFF])
    assert "context: repo" in capsys.readouterr().out


def test_dash_reads_the_diff_from_standard_input(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(Path(FANOUT_DIFF).read_text(encoding="utf-8")))
    assert main(["--diff", "-"]) == EXIT_OK
    assert "2 files changed" in capsys.readouterr().out


def test_format_json_prints_the_review_as_json(capsys):
    assert main(["--diff", FANOUT_DIFF, "--format", "json"]) == EXIT_OK
    assert json.loads(capsys.readouterr().out)["context"]["files_changed"] == 2
