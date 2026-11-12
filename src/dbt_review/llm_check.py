from dataclasses import dataclass
from importlib import resources
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from dbt_review.manifest import ModelFacts
from dbt_review.models import MAX_TEXT_LENGTH, Finding, Severity, Source


class LlmFinding(BaseModel):
    """What the model may say. `error` is not a severity it can choose, and evidence is required."""

    check_id: Literal["join-fanout", "naming"]
    severity: Literal["info", "warning"]
    line: int
    end_line: int | None = None
    message: str = Field(max_length=MAX_TEXT_LENGTH)
    evidence: list[str] = Field(min_length=1)
    suggestion: str | None = Field(default=None, max_length=MAX_TEXT_LENGTH)


class LlmReview(BaseModel):
    findings: list[LlmFinding]


INSTRUCTIONS = resources.files("dbt_review").joinpath("instructions.md").read_text(encoding="utf-8")
reviewer = Agent(output_type=LlmReview, instructions=INSTRUCTIONS)


@dataclass(frozen=True)
class ModelContext:
    """Everything the LLM is shown about one changed model."""

    path: str
    sql: str
    added_lines: list[int]
    model: ModelFacts
    inputs: list[ModelFacts]


def review_model(context: ModelContext, model: str) -> list[Finding]:
    """One call to the LLM for one changed model. `model` is `provider:name`, e.g. `groq:openai/gpt-oss-120b`."""
    answer = reviewer.run_sync(render_prompt(context), model=model).output
    return [
        Finding(
            check_id=found.check_id,
            source=Source.LLM,
            severity=Severity(found.severity),
            file=context.path,
            line=found.line,
            end_line=found.end_line,
            message=found.message,
            evidence=found.evidence,
            suggestion=found.suggestion,
        )
        for found in answer.findings
        if found.line in context.added_lines  # the model sometimes cites a line it was not asked about
    ]


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
