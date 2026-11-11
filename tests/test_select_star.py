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


def test_count_star_is_not_a_star_select():
    sql = "select customer_id, count(*) as number_of_orders from {{ ref('stg_orders') }} group by 1\n"

    assert check("models/customer_orders.sql", sql) == []


STAR_FROM_AN_IMPORT = """\
with customers as (

    select * from {{ ref('stg_customers') }}

),

final as (

    select
        customers.*,
        customer_orders.number_of_orders

    from customers

    left join {{ ref('customer_orders') }} as customer_orders
        on customers.customer_id = customer_orders.customer_id

)

select * from final
"""


def test_qualified_star_is_flagged_on_its_own_line():
    [finding] = check("models/customers.sql", STAR_FROM_AN_IMPORT)

    assert finding.line == 10


STAR_FROM_NAMED_COLUMNS = """\
with renamed as (

    select
        id as customer_id,
        first_name

    from {{ ref('raw_customers') }}

)

select
    renamed.*,
    customer_orders.number_of_orders

from renamed

left join {{ ref('customer_orders') }} as customer_orders
    on renamed.customer_id = customer_orders.customer_id
"""


def test_star_of_a_cte_that_writes_its_columns_out_is_fine():
    assert check("models/customers.sql", STAR_FROM_NAMED_COLUMNS) == []
