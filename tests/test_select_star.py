from dbt_review.models import Severity, Source
from dbt_review.select_star import check


def test_model_that_only_stars_a_relation_is_flagged():
    [finding] = check("models/customers.sql", "select * from {{ ref('stg_customers') }}\n")

    assert finding.check_id == "select-star"
    assert (finding.source, finding.severity) == (Source.RULE, Severity.WARNING)
    assert (finding.file, finding.line) == ("models/customers.sql", 1)


NAMED_COLUMNS = """\
with customers as (

    select * from {{ ref('stg_customers') }}

),

final as (

    select
        customers.customer_id,
        customers.first_name

    from customers

)

select * from final
"""


def test_stars_are_fine_when_the_columns_are_written_out_in_the_file():
    assert check("models/customers.sql", NAMED_COLUMNS) == []
