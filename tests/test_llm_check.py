from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from dbt_review.llm_check import ModelContext, render_prompt, review_model, reviewer
from dbt_review.manifest import ModelFacts
from dbt_review.models import Severity, Source

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


def test_prompt_states_the_tests_dbt_declares_on_the_model_and_its_inputs():
    prompt = render_prompt(orders_context())

    assert "Model `orders` (models/orders.sql) reads: stg_orders, stg_payments" in prompt
    assert "- orders: order_id (unique, not_null)\n" in prompt
    assert "- stg_payments: payment_id (unique, not_null)\n" in prompt


def test_prompt_says_so_when_a_model_has_no_column_tests():
    context = orders_context()
    context.inputs.append(ModelFacts("raw_refunds", [], {}))

    assert "- raw_refunds: no column tests\n" in render_prompt(context)


def model_answering(*findings: dict) -> FunctionModel:
    """A fake LLM that returns these findings whatever it is asked."""

    def answer(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {"findings": list(findings)})])

    return FunctionModel(answer)


FANOUT = {
    "check_id": "join-fanout",
    "severity": "warning",
    "line": 3,
    "end_line": 4,
    "message": "Joining stg_payments on order_id returns one row per payment.",
    "evidence": ["stg_payments has a unique test on payment_id, none on order_id"],
    "suggestion": "Aggregate payments to one row per order before joining.",
}


def test_an_answer_from_the_model_becomes_a_finding_on_the_reviewed_file():
    with reviewer.override(model=model_answering(FANOUT)):
        [finding] = review_model(orders_context(), model="groq:any")

    assert (finding.source, finding.file) == (Source.LLM, "models/orders.sql")
    assert (finding.check_id, finding.severity) == ("join-fanout", Severity.WARNING)
    assert (finding.line, finding.end_line) == (3, 4)
    assert finding.evidence == ["stg_payments has a unique test on payment_id, none on order_id"]


def test_a_finding_on_a_line_the_change_did_not_add_is_dropped():
    on_an_old_line = FANOUT | {"line": 1, "end_line": None}

    with reviewer.override(model=model_answering(on_an_old_line, FANOUT)):
        findings = review_model(orders_context(), model="groq:any")

    assert [finding.line for finding in findings] == [3]
