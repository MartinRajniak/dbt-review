from pathlib import Path

from dbt_review.checks import select_star
from dbt_review.diff import ChangedFile
from dbt_review.models import Finding


def run_checks(repo: Path, changed: list[ChangedFile]) -> list[Finding]:
    """Findings on the lines the change added; older problems are not this author's to fix."""
    findings = []
    for file in changed:
        model = repo / file.path
        if model.suffix == ".sql" and model.is_file():
            found = select_star.check(file.path, model.read_text(encoding="utf-8"))
            findings += [finding for finding in found if finding.line in file.added_lines]
    return findings
