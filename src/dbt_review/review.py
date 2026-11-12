from pathlib import Path

from dbt_review.checks import RULES
from dbt_review.diff import ChangedFile, parse_diff
from dbt_review.errors import ToolError
from dbt_review.models import Finding, Review, ReviewContext


def review_diff(diff_text: str, repo: Path, base: str | None = None) -> Review:
    changed = parse_diff(diff_text)
    has_project = (repo / "dbt_project.yml").is_file()
    context = ReviewContext(repo=has_project, base=base, files_changed=len(changed))
    if not has_project:
        raise ToolError(f"no dbt project at {repo} (dbt_project.yml not found); the review needs the code")
    return Review(context=context, findings=_rule_findings(repo, changed))


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
