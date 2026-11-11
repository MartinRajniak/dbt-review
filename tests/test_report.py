from dbt_review.models import Finding, Review, ReviewContext
from dbt_review.report import render_text


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
