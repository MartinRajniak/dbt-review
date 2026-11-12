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
    lines = [
        f"{'+' if number in context.added_lines else ' '}{number:>4} | {text}\n"
        for number, text in enumerate(context.sql.splitlines(), start=1)
    ]
    return "".join(lines)
