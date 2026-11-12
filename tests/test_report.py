import json

from dbt_review.models import Finding, Review, ReviewContext, Skipped
from dbt_review.report import render_json, render_text


def test_review_without_findings_is_a_header_and_a_count_line():
    review = Review(context=ReviewContext(repo=False, files_changed=0))
    assert render_text(review) == "\n".join(
        [
            "dbt-review · 0 files changed · context: diff-only",
            "",
            "0 errors · 0 warnings · 0 info",
        ]
    )


def fanout_finding() -> Finding:
    return Finding(
        check_id="join-fanout",
        source="llm",
        severity="warning",
        file="models/orders.sql",
        line=55,
        end_line=56,
        message="Joining `payments` on `order_id` returns one row per payment.",
        evidence=[
            "stg_payments has a unique test on payment_id, none on order_id",
            "orders.order_id has a unique test, which this join breaks",
        ],
        suggestion="take payment_method from a CTE grouped by order_id.",
    )


def test_finding_shows_where_what_evidence_and_fix_under_its_file():
    review = Review(
        context=ReviewContext(repo=True, base="duckdb", files_changed=2),
        findings=[fanout_finding()],
    )
    assert render_text(review) == "\n".join(
        [
            "dbt-review · base duckdb · 2 files changed · context: repo",
            "",
            "models/orders.sql",
            "  55-56  warning  join-fanout (llm)",
            "         Joining `payments` on `order_id` returns one row per payment.",
            "         Evidence: stg_payments has a unique test on payment_id, none on order_id",
            "                   orders.order_id has a unique test, which this join breaks",
            "         Fix: take payment_method from a CTE grouped by order_id.",
            "",
            "0 errors · 1 warning · 0 info",
        ]
    )


def test_finding_without_range_evidence_or_fix_takes_two_lines():
    finding = Finding(
        check_id="hardcoded-relation",
        source="rule",
        severity="error",
        file="models/orders.sql",
        line=11,
        message="`main.stg_payments` is hardcoded; use ref('stg_payments').",
    )
    review = Review(context=ReviewContext(repo=True, files_changed=1), findings=[finding])
    assert render_text(review) == "\n".join(
        [
            "dbt-review · 1 file changed · context: repo",
            "",
            "models/orders.sql",
            "  11     error    hardcoded-relation (rule)",
            "         `main.stg_payments` is hardcoded; use ref('stg_payments').",
            "",
            "1 error · 0 warnings · 0 info",
        ]
    )


def small_finding(file: str, line: int, severity: str = "warning") -> Finding:
    return Finding(check_id="check", source="rule", severity=severity, file=file, line=line, message="m")


def test_findings_are_grouped_by_file_and_ordered_by_line_then_severity():
    review = Review(
        context=ReviewContext(repo=True, files_changed=2),
        findings=[
            small_finding("models/b.sql", 1),
            small_finding("models/a.sql", 9),
            small_finding("models/a.sql", 3),
            small_finding("models/a.sql", 3, severity="error"),
        ],
    )
    assert render_text(review) == "\n".join(
        [
            "dbt-review · 2 files changed · context: repo",
            "",
            "models/a.sql",
            "  3      error    check (rule)",
            "         m",
            "",
            "  3      warning  check (rule)",
            "         m",
            "",
            "  9      warning  check (rule)",
            "         m",
            "",
            "models/b.sql",
            "  1      warning  check (rule)",
            "         m",
            "",
            "1 error · 3 warnings · 0 info",
        ]
    )


def review_with_a_warning_and_an_info() -> Review:
    return Review(
        context=ReviewContext(repo=True, files_changed=1),
        findings=[
            small_finding("models/a.sql", 1),
            small_finding("models/a.sql", 2, severity="info"),
        ],
    )


def test_info_findings_are_hidden_by_default_but_still_counted():
    assert render_text(review_with_a_warning_and_an_info()) == "\n".join(
        [
            "dbt-review · 1 file changed · context: repo",
            "",
            "models/a.sql",
            "  1      warning  check (rule)",
            "         m",
            "",
            "0 errors · 1 warning · 1 info hidden (--show-info)",
        ]
    )


def test_info_findings_are_shown_on_request():
    text = render_text(review_with_a_warning_and_an_info(), show_info=True)
    assert "  2      info     check (rule)" in text
    assert text.endswith("0 errors · 1 warning · 1 info")


def test_json_carries_context_summary_and_every_field_of_a_finding():
    review = Review(
        context=ReviewContext(repo=True, base="duckdb", files_changed=2),
        findings=[fanout_finding()],
    )
    assert json.loads(render_json(review)) == {
        "context": {"repo": True, "base": "duckdb", "files_changed": 2},
        "summary": {"errors": 0, "warnings": 1, "infos": 0},
        "skipped": [],
        "findings": [
            {
                "check_id": "join-fanout",
                "source": "llm",
                "severity": "warning",
                "file": "models/orders.sql",
                "line": 55,
                "end_line": 56,
                "message": "Joining `payments` on `order_id` returns one row per payment.",
                "evidence": [
                    "stg_payments has a unique test on payment_id, none on order_id",
                    "orders.order_id has a unique test, which this join breaks",
                ],
                "suggestion": "take payment_method from a CTE grouped by order_id.",
            }
        ],
    }


def test_json_hides_info_findings_like_the_text_report_and_still_counts_them():
    review = review_with_a_warning_and_an_info()
    default = json.loads(render_json(review))
    assert [finding["severity"] for finding in default["findings"]] == ["warning"]
    assert default["summary"]["infos"] == 1
    everything = json.loads(render_json(review, show_info=True))
    assert [finding["severity"] for finding in everything["findings"]] == ["warning", "info"]


def review_with_skipped_checks() -> Review:
    return Review(
        context=ReviewContext(repo=False, files_changed=1),
        skipped=[
            Skipped(check_id="select-star", reason="no dbt project"),
            Skipped(check_id="hardcoded-relation", reason="no dbt project"),
        ],
    )


def test_skipped_checks_are_named_with_the_reason_on_the_last_line():
    last_line = render_text(review_with_skipped_checks()).splitlines()[-1]

    assert last_line == "skipped (no dbt project): select-star, hardcoded-relation"


def test_json_lists_skipped_checks():
    payload = json.loads(render_json(review_with_skipped_checks()))

    assert payload["skipped"][0] == {"check_id": "select-star", "reason": "no dbt project"}
