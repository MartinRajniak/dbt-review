import json
from itertools import groupby

from dbt_review.models import Finding, Review, Severity

SEVERITY_ORDER = [Severity.ERROR, Severity.WARNING, Severity.INFO]
INDENT = " " * 9
EVIDENCE_LABEL = "Evidence: "


def render_text(review: Review, show_info: bool = False) -> str:
    lines = [_header(review), ""]
    for file, findings in groupby(_shown_findings(review, show_info), key=lambda f: f.file):
        lines.append(file)
        for finding in findings:
            lines.extend(_finding_lines(finding))
            lines.append("")
    lines.append(_counts(review, show_info))
    return "\n".join(lines)


def render_json(review: Review, show_info: bool = False) -> str:
    """The summary counts every finding, shown or not."""
    payload = {
        "context": review.context.model_dump(),
        "summary": {
            "errors": review.count(Severity.ERROR),
            "warnings": review.count(Severity.WARNING),
            "infos": review.count(Severity.INFO),
        },
        "findings": [f.model_dump(mode="json") for f in _shown_findings(review, show_info)],
    }
    return json.dumps(payload, indent=2)


def _shown_findings(review: Review, show_info: bool) -> list[Finding]:
    """Sorted, so two runs print the same."""
    shown = [f for f in review.findings if show_info or f.severity != Severity.INFO]
    return sorted(shown, key=lambda f: (f.file, f.line, SEVERITY_ORDER.index(f.severity)))


def _header(review: Review) -> str:
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


def _counts(review: Review, show_info: bool) -> str:
    infos = review.count(Severity.INFO)
    hidden_note = " hidden (--show-info)" if infos and not show_info else ""
    return " · ".join(
        [
            _plural(review.count(Severity.ERROR), "error"),
            _plural(review.count(Severity.WARNING), "warning"),
            f"{infos} info{hidden_note}",
        ]
    )


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"
