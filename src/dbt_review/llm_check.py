from dataclasses import dataclass

from dbt_review.manifest import ModelFacts


@dataclass(frozen=True)
class ModelContext:
    """Everything the LLM is shown about one changed model."""

    path: str
    sql: str
    added_lines: list[int]
    model: ModelFacts
    inputs: list[ModelFacts]


def render_prompt(context: ModelContext) -> str:
    model = context.model
    return (
        f"Model `{model.name}` ({context.path}) reads: {', '.join(model.reads)}\n\n"
        "Tests dbt declares on columns:\n"
        + "".join(_column_tests(facts) for facts in [model, *context.inputs])
        + '\nThe file. Lines the change added start with "+":\n<file>\n'
        + _numbered(context)
        + "</file>\n"
    )


def _column_tests(facts: ModelFacts) -> str:
    columns = [f"{column} ({', '.join(tests)})" for column, tests in facts.column_tests.items()]
    return f"- {facts.name}: {', '.join(columns) or 'no column tests'}\n"


def _numbered(context: ModelContext) -> str:
    return "".join(
        f"{'+' if number in context.added_lines else ' '}{number:>4} | {text}\n"
        for number, text in enumerate(context.sql.splitlines(), start=1)
    )
