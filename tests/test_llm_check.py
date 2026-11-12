from dbt_review.llm_check import ModelContext, render_prompt
from dbt_review.manifest import ModelFacts

ORDERS_SQL = """\
select orders.order_id, payments.payment_method
from {{ ref('stg_orders') }} as orders
left join {{ ref('stg_payments') }} as payments
    on orders.order_id = payments.order_id
"""


def orders_context() -> ModelContext:
    return ModelContext(
        path="models/orders.sql",
        sql=ORDERS_SQL,
        added_lines=[3, 4],
        model=ModelFacts("orders", ["stg_orders", "stg_payments"], {"order_id": ["unique", "not_null"]}),
        inputs=[
            ModelFacts("stg_orders", ["raw_orders"], {"order_id": ["unique", "not_null"]}),
            ModelFacts("stg_payments", ["raw_payments"], {"payment_id": ["unique", "not_null"]}),
        ],
    )


def test_prompt_shows_the_file_with_line_numbers_and_marks_the_added_lines():
    prompt = render_prompt(orders_context())

    assert "    2 | from {{ ref('stg_orders') }} as orders\n" in prompt
    assert "+   3 | left join {{ ref('stg_payments') }} as payments\n" in prompt
    assert "+   4 |     on orders.order_id = payments.order_id\n" in prompt
