from pathlib import Path

from dbt_review.checks import RULES
from dbt_review.diff import ChangedFile
from dbt_review.models import Finding, Skipped


def run_checks(project: Path | None, changed: list[ChangedFile]) -> tuple[list[Finding], list[Skipped]]:
    """Findings on the lines the change added; older problems are not this author's to fix."""
    if project is None:
        return [], [Skipped(check_id=rule.check_id, reason="no dbt project") for rule in RULES]
    findings = []
    for file in changed:
        model = project / file.path
        if model.suffix == ".sql" and model.is_file():
            sql = model.read_text(encoding="utf-8")
            found = [finding for rule in RULES for finding in rule.check(file.path, sql)]
            findings += [finding for finding in found if finding.line in file.added_lines]
    return findings, []
