from dbt_review.hardcoded_relation import check
from dbt_review.models import Severity, Source

HARDCODED = """\
with payments as (

    select * from main.stg_payments

)

select order_id, amount from payments
"""


def test_table_named_directly_is_an_error():
    [finding] = check("models/orders.sql", HARDCODED)

    assert finding.check_id == "hardcoded-relation"
    assert (finding.source, finding.severity) == (Source.RULE, Severity.ERROR)
    assert (finding.file, finding.line) == ("models/orders.sql", 3)
    assert "main.stg_payments" in finding.message


THROUGH_DBT = """\
{% set statuses = ['placed', 'shipped'] %}

with orders as (

    select * from {{ ref('stg_orders') }}

),

payments as (

    select * from {{ source('shop', 'payments') }}

)

select orders.order_id, payments.amount

from orders

left join payments on orders.order_id = payments.order_id
"""


def test_ref_source_and_cte_names_are_fine():
    assert check("models/orders.sql", THROUGH_DBT) == []
