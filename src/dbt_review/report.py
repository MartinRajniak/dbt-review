import json
from itertools import groupby

from dbt_review.models import Finding, Review, Severity

SEVERITY_ORDER = [Severity.ERROR, Severity.WARNING, Severity.INFO]
INDENT = " " * 9
EVIDENCE_LABEL = "Evidence: "


def render_text(review: Review) -> str:
    lines = [_header(review), ""]
    for file, findings in groupby(_sorted_findings(review), key=lambda f: f.file):
        lines.append(file)
        for finding in findings:
            lines.extend(_finding_lines(finding))
            lines.append("")
    lines.append(_counts(review))
    lines.extend(_skipped_lines(review))
    return "\n".join(lines)


def render_json(review: Review) -> str:
    payload = {
        "context": review.context.model_dump(),
        "summary": {
            "errors": review.count(Severity.ERROR),
            "warnings": review.count(Severity.WARNING),
            "infos": review.count(Severity.INFO),
        },
        "skipped": [skipped.model_dump() for skipped in review.skipped],
        "findings": [f.model_dump(mode="json") for f in _sorted_findings(review)],
    }
    return json.dumps(payload, indent=2)


def _sorted_findings(review: Review) -> list[Finding]:
    """Sorted, so two runs print the same."""
    return sorted(review.findings, key=lambda f: (f.file, f.line, SEVERITY_ORDER.index(f.severity)))


def _header(review: Review) -> str:
    context = review.context
    parts = ["dbt-review"]
    if context.base:
        parts.append(f"base {context.base}")
    parts.append(_plural(context.files_changed, "file") + " changed")
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


def _skipped_lines(review: Review) -> list[str]:
    """One line per reason, naming the checks it kept from running."""
    reasons = dict.fromkeys(skipped.reason for skipped in review.skipped)
    return [
        f"skipped ({reason}): " + ", ".join(s.check_id for s in review.skipped if s.reason == reason)
        for reason in reasons
    ]


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"
