from enum import StrEnum

from pydantic import BaseModel, Field


class Severity(StrEnum):
    ERROR = "error"  # would produce wrong data or break the build
    WARNING = "warning"  # fix it, or consciously accept it
    INFO = "info"  # convention or readability


class Source(StrEnum):
    RULE = "rule"  # deterministic: same input, same answer
    LLM = "llm"  # a judgement; should come with evidence


MAX_TEXT_LENGTH = 300


class Finding(BaseModel):
    check_id: str
    source: Source
    severity: Severity
    file: str
    line: int
    end_line: int | None = None
    message: str = Field(max_length=MAX_TEXT_LENGTH)
    evidence: list[str] = []
    suggestion: str | None = Field(default=None, max_length=MAX_TEXT_LENGTH)


class Skipped(BaseModel):
    """A check that did not run, so its silence is not mistaken for a pass."""

    check_id: str
    reason: str


class ReviewContext(BaseModel):
    """What the review could see."""

    repo: bool
    base: str | None = None
    files_changed: int


class Review(BaseModel):
    context: ReviewContext
    findings: list[Finding] = []
    skipped: list[Skipped] = []

    def count(self, severity: Severity) -> int:
        return sum(1 for finding in self.findings if finding.severity == severity)
