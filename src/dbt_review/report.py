"""Render a review as text, for people."""

from dbt_review.models import Finding, Review, Severity

INDENT = " " * 9
EVIDENCE_LABEL = "Evidence: "


def render_text(review: Review) -> str:
    lines = [_header(review), ""]
    for finding in review.findings:
        lines.append(finding.file)
        lines.extend(_finding_lines(finding))
        lines.append("")
    lines.append(_counts(review))
    return "\n".join(lines)


def _header(review: Review) -> str:
    """Says what the review could see, so a reader knows how far to trust it."""
    context = review.context
    parts = ["dbt-review"]
    if context.base:
        parts.append(f"base {context.base}")
    parts.append(_plural(context.files_changed, "file") + " changed")
    parts.append("context: " + ("repo" if context.repo else "diff-only"))
    return " · ".join(parts)


def _finding_lines(finding: Finding) -> list[str]:
    where = str(finding.line)
    if finding.end_line:
        where += f"-{finding.end_line}"
    lines = [
        f"  {where:<6} {finding.severity:<8} {finding.check_id} ({finding.source})",
        INDENT + finding.message,
    ]
    for index, fact in enumerate(finding.evidence):
        label = EVIDENCE_LABEL if index == 0 else " " * len(EVIDENCE_LABEL)
        lines.append(INDENT + label + fact)
    if finding.suggestion:
        lines.append(f"{INDENT}Fix: {finding.suggestion}")
    return lines


def _counts(review: Review) -> str:
    return " · ".join(
        [
            _plural(review.count(Severity.ERROR), "error"),
            _plural(review.count(Severity.WARNING), "warning"),
            f"{review.count(Severity.INFO)} info",
        ]
    )


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"
