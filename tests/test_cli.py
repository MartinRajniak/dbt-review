from dbt_review.cli import EXIT_TOOL_FAILED, main


def test_no_input_is_a_tool_failure_not_a_review_result(capsys):
    assert main([]) == EXIT_TOOL_FAILED
    assert "nothing to review" in capsys.readouterr().err
