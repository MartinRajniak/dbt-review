from pathlib import Path

from dbt_review.checks import RULES
from dbt_review.diff import ChangedFile, parse_diff
from dbt_review.errors import ToolError
from dbt_review.models import Finding, Review, ReviewContext


def review_diff(diff_text: str, repo: Path, base: str | None = None) -> Review:
    changed = parse_diff(diff_text)
    if not (repo / "dbt_project.yml").is_file():
        raise ToolError(f"no dbt project at {repo} (dbt_project.yml not found); the review needs the code")
    _require_matching_checkout(repo, changed)
    context = ReviewContext(base=base, files_changed=len(changed))
    return Review(context=context, findings=_rule_findings(repo, changed))


def _require_matching_checkout(project: Path, changed: list[ChangedFile]) -> None:
    """Every added line must be in the checkout, or findings would be missed or misplaced."""
    for file in changed:
        path = project / file.path
        lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else None
        for number, text in file.added_lines.items():
            if lines is not None and (number > len(lines) or lines[number - 1] != text):
                raise ToolError(
                    f"{file.path}:{number} does not match the diff; "
                    "check out the branch the diff was made from"
                )


def _rule_findings(project: Path, changed: list[ChangedFile]) -> list[Finding]:
    """Findings on the lines the change added; older problems are not this author's to fix."""
    findings = []
    for file in changed:
        model = project / file.path
        if model.suffix == ".sql" and model.is_file():
            sql = model.read_text(encoding="utf-8")
            found = [finding for rule in RULES for finding in rule.check(file.path, sql)]
            findings += [finding for finding in found if finding.line in file.added_lines]
    return findings
