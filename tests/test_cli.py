import io
import json
import subprocess
import sys
from pathlib import Path

import pytest
from helpers import model_answering, model_node, write_manifest

from dbt_review.cli import ExitCode, main
from dbt_review.llm_check import reviewer

FANOUT_DIFF = str(Path(__file__).parent.parent / "examples" / "fanout-join" / "input.diff")

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
    """A dbt project checked out after the change in STAR_DIFF."""
    (tmp_path / "dbt_project.yml").write_text("name: shop\n")
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "customers.sql").write_text("select *\n\nfrom {{ ref('stg_customers') }}\n")
    return tmp_path


def review_of(project: Path, diff_text: str) -> list[str]:
    """Command line arguments that review `diff_text` against `project`."""
    diff_file = project / "change.diff"
    diff_file.write_text(diff_text)
    return ["--repo", str(project), "--diff", str(diff_file)]


def test_no_input_is_a_tool_failure_not_a_review_result(capsys):
    assert main([]) == ExitCode.TOOL_FAILED
    assert "nothing to review" in capsys.readouterr().err


def test_diff_file_is_reviewed_and_the_report_printed(dbt_project, capsys):
    assert main(review_of(dbt_project, STAR_DIFF)) == ExitCode.OK
    assert capsys.readouterr().out.startswith("dbt-review · 1 file changed")


def test_unreadable_diff_file_is_a_tool_failure(tmp_path, capsys):
    assert main(["--diff", str(tmp_path / "missing.diff")]) == ExitCode.TOOL_FAILED
    assert "cannot read diff file" in capsys.readouterr().err


def test_without_a_dbt_project_the_tool_refuses_to_review(tmp_path, capsys):
    assert main(["--repo", str(tmp_path), "--diff", FANOUT_DIFF]) == ExitCode.TOOL_FAILED
    assert "no dbt project" in capsys.readouterr().err


def test_dash_reads_the_diff_from_standard_input(dbt_project, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(STAR_DIFF))
    assert main(["--repo", str(dbt_project), "--diff", "-"]) == ExitCode.OK
    assert "1 file changed" in capsys.readouterr().out


def test_format_json_prints_the_review_as_json(dbt_project, capsys):
    assert main([*review_of(dbt_project, STAR_DIFF), "--format", "json"]) == ExitCode.OK
    assert json.loads(capsys.readouterr().out)["context"]["files_changed"] == 1


def git(repo: Path, *arguments: str) -> None:
    subprocess.run(["git", "-C", str(repo), *arguments], check=True, capture_output=True)


@pytest.fixture
def repo_on_a_branch(tmp_path):
    """A dbt project where branch `change` edits orders.sql, and `main` has moved on since."""
    orders, customers = tmp_path / "models" / "orders.sql", tmp_path / "models" / "customers.sql"
    orders.parent.mkdir()
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.email", "test@example.com")
    git(tmp_path, "config", "user.name", "Test")
    git(tmp_path, "config", "commit.gpgsign", "false")
    (tmp_path / "dbt_project.yml").write_text("name: shop\n")
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
    assert main(["--repo", str(repo_on_a_branch), "--base", "main"]) == ExitCode.OK
    assert capsys.readouterr().out.startswith("dbt-review · base main · 1 file changed")


def test_unknown_base_is_a_tool_failure(repo_on_a_branch, capsys):
    assert main(["--repo", str(repo_on_a_branch), "--base", "nope"]) == ExitCode.TOOL_FAILED
    assert "git diff against 'nope' failed" in capsys.readouterr().err


def test_base_and_diff_together_are_rejected(capsys):
    assert main(["--base", "main", "--diff", "change.diff"]) == ExitCode.TOOL_FAILED
    assert "either --base or --diff" in capsys.readouterr().err


def test_output_is_utf8_whatever_the_console_code_page(dbt_project):
    """Run as a real process: on Windows, piped output otherwise uses a legacy code page."""
    run_main = "import sys; from dbt_review.cli import main; sys.exit(main())"
    command = [sys.executable, "-c", run_main, *review_of(dbt_project, STAR_DIFF)]
    result = subprocess.run(command, capture_output=True, check=True)
    assert result.stdout.decode("utf-8").startswith("dbt-review · 1 file changed")


def test_rule_findings_on_changed_models_are_reported(dbt_project, capsys):
    main(review_of(dbt_project, STAR_DIFF))

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


def test_problems_the_change_did_not_introduce_are_not_reported(dbt_project, capsys):
    main(review_of(dbt_project, UNRELATED_DIFF))

    assert "0 errors · 0 warnings" in capsys.readouterr().out


HARDCODED_DIFF = """\
diff --git a/models/orders.sql b/models/orders.sql
new file mode 100644
--- /dev/null
+++ b/models/orders.sql
@@ -0,0 +1 @@
+select order_id from main.stg_orders
"""


@pytest.fixture
def hardcoded_change(dbt_project):
    (dbt_project / "models" / "orders.sql").write_text("select order_id from main.stg_orders\n")
    return review_of(dbt_project, HARDCODED_DIFF)


def test_every_rule_runs_on_a_changed_model(hardcoded_change, capsys):
    main(hardcoded_change)

    assert "  1      error    hardcoded-relation (rule)" in capsys.readouterr().out


def test_an_error_finding_fails_the_run(hardcoded_change):
    assert main(hardcoded_change) == ExitCode.FOUND_ERRORS


def test_warnings_alone_do_not_fail_the_run(dbt_project):
    assert main(review_of(dbt_project, STAR_DIFF)) == ExitCode.OK


def test_checkout_from_before_the_change_is_refused(dbt_project, capsys):
    (dbt_project / "models" / "customers.sql").write_text(
        "select customer_id\n\nfrom {{ ref('stg_customers') }}\n"
    )

    assert main(review_of(dbt_project, STAR_DIFF)) == ExitCode.TOOL_FAILED
    assert "models/customers.sql:1 does not match the diff" in capsys.readouterr().err


def test_changed_file_missing_from_the_checkout_is_refused(dbt_project, capsys):
    assert main(review_of(dbt_project, HARDCODED_DIFF)) == ExitCode.TOOL_FAILED
    assert "models/orders.sql is in the diff but not in the checkout" in capsys.readouterr().err


@pytest.fixture
def parsed_project(dbt_project, monkeypatch):
    """The dbt project after `dbt parse` has written its manifest, with a key for the default model."""
    monkeypatch.setenv("GROQ_API_KEY", "not-a-real-key")
    (dbt_project / "target").mkdir()
    customers = model_node("customers", "models/customers.sql", reads=("stg_customers",))
    write_manifest(dbt_project / "target", customers)
    return dbt_project


LLM_WARNING = {
    "check_id": "join-fanout",
    "severity": "warning",
    "line": 1,
    "message": "This join returns one row per payment.",
    "evidence": ["stg_payments has no unique test on order_id"],
}


def test_llm_findings_on_changed_models_are_reported(parsed_project, capsys):
    with reviewer.override(model=model_answering(LLM_WARNING)):
        main(review_of(parsed_project, STAR_DIFF))

    assert "  1      warning  join-fanout (llm)" in capsys.readouterr().out


def test_without_a_manifest_the_llm_check_is_reported_as_skipped(dbt_project, capsys):
    main(review_of(dbt_project, STAR_DIFF))

    last_line = capsys.readouterr().out.splitlines()[-1]
    assert last_line == "skipped (no target/manifest.json: run `dbt parse`): llm-review"


def test_without_an_api_key_the_llm_check_is_reported_as_skipped(parsed_project, monkeypatch, capsys):
    monkeypatch.delenv("GROQ_API_KEY")

    main(review_of(parsed_project, STAR_DIFF))

    assert capsys.readouterr().out.splitlines()[-1] == "skipped (GROQ_API_KEY is not set): llm-review"


def test_model_option_chooses_the_provider(parsed_project, monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    main([*review_of(parsed_project, STAR_DIFF), "--model", "anthropic:claude-haiku-5-5"])

    assert capsys.readouterr().out.splitlines()[-1] == "skipped (ANTHROPIC_API_KEY is not set): llm-review"
