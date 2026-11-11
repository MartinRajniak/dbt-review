"""The data shapes every other module shares: a finding, and a whole review."""

from enum import StrEnum

from pydantic import BaseModel


class Severity(StrEnum):
    ERROR = "error"  # would produce wrong data or break the build
    WARNING = "warning"  # fix it, or consciously accept it
    INFO = "info"  # convention or readability


class Source(StrEnum):
    RULE = "rule"  # deterministic: same input, same answer
    LLM = "llm"  # a judgement; should come with evidence


class Finding(BaseModel):
    check_id: str
    source: Source
    severity: Severity
    file: str
    line: int
    end_line: int | None = None
    message: str
    evidence: list[str] = []
    suggestion: str | None = None


class ReviewContext(BaseModel):
    """What the review could see. Printed in the header so a reader knows how far to trust it."""

    repo: bool
    base: str | None = None
    files_changed: int


class Review(BaseModel):
    context: ReviewContext
    findings: list[Finding] = []

    def count(self, severity: Severity) -> int:
        return sum(1 for finding in self.findings if finding.severity == severity)
