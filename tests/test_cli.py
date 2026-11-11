import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

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


def git(repo: Path, *arguments: str) -> None:
    subprocess.run(["git", "-C", str(repo), *arguments], check=True, capture_output=True)


@pytest.fixture
def repo_on_a_branch(tmp_path):
    """A repo where branch `change` edits orders.sql, and `main` has moved on since."""
    orders, customers = tmp_path / "models" / "orders.sql", tmp_path / "models" / "customers.sql"
    orders.parent.mkdir()
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.email", "test@example.com")
    git(tmp_path, "config", "user.name", "Test")
    git(tmp_path, "config", "commit.gpgsign", "false")
    orders.write_text("select 1\n")
    customers.write_text("select 1\n")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "base")
    git(tmp_path, "checkout", "-q", "-b", "change")
    orders.write_text("select 1\nunion all select 2\n")
    git(tmp_path, "commit", "-q", "-am", "change orders")
    git(tmp_path, "checkout", "-q", "main")
    customers.write_text("select 3\n")
    git(tmp_path, "commit", "-q", "-am", "main moves on")
    git(tmp_path, "checkout", "-q", "change")
    return tmp_path


def test_base_reviews_only_what_the_branch_changed_since_it_left_base(repo_on_a_branch, capsys):
    assert main(["--repo", str(repo_on_a_branch), "--base", "main"]) == EXIT_OK
    assert capsys.readouterr().out.startswith("dbt-review · base main · 1 file changed")


def test_unknown_base_is_a_tool_failure(repo_on_a_branch, capsys):
    assert main(["--repo", str(repo_on_a_branch), "--base", "nope"]) == EXIT_TOOL_FAILED
    assert "git diff against 'nope' failed" in capsys.readouterr().err


def test_base_and_diff_together_are_rejected(capsys):
    assert main(["--base", "main", "--diff", FANOUT_DIFF]) == EXIT_TOOL_FAILED
    assert "either --base or --diff" in capsys.readouterr().err


def test_output_is_utf8_whatever_the_console_code_page():
    """Run as a real process: on Windows, piped output otherwise uses a legacy code page."""
    run_main = "import sys; from dbt_review.cli import main; sys.exit(main())"
    result = subprocess.run([sys.executable, "-c", run_main, "--diff", FANOUT_DIFF], capture_output=True)
    assert result.stdout.decode("utf-8").startswith("dbt-review · 2 files changed")


STAR_DIFF = """\
diff --git a/models/customers.sql b/models/customers.sql
--- a/models/customers.sql
+++ b/models/customers.sql
@@ -1,3 +1,3 @@
-select customer_id
+select *
 
 from {{ ref('stg_customers') }}
"""


@pytest.fixture
def dbt_project(tmp_path):
    (tmp_path / "dbt_project.yml").write_text("name: shop\n")
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "customers.sql").write_text("select *\n\nfrom {{ ref('stg_customers') }}\n")
    return tmp_path


def test_rule_findings_on_changed_models_are_reported(dbt_project, tmp_path, capsys):
    (tmp_path / "change.diff").write_text(STAR_DIFF)

    main(["--repo", str(dbt_project), "--diff", str(tmp_path / "change.diff")])

    out = capsys.readouterr().out
    assert "models/customers.sql\n  1      warning  select-star (rule)" in out
    assert "0 errors · 1 warning" in out


UNRELATED_DIFF = """\
diff --git a/models/customers.sql b/models/customers.sql
--- a/models/customers.sql
+++ b/models/customers.sql
@@ -1,3 +1,3 @@
 select *
 
-from {{ ref('customers') }}
+from {{ ref('stg_customers') }}
"""


def test_problems_the_change_did_not_introduce_are_not_reported(dbt_project, tmp_path, capsys):
    (tmp_path / "change.diff").write_text(UNRELATED_DIFF)

    main(["--repo", str(dbt_project), "--diff", str(tmp_path / "change.diff")])

    assert "0 errors · 0 warnings" in capsys.readouterr().out
