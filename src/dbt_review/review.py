from pathlib import Path

from dbt_review.checks import hardcoded_relation, select_star
from dbt_review.diff import ChangedFile
from dbt_review.models import Finding

RULES = [select_star.check, hardcoded_relation.check]


def run_checks(repo: Path, changed: list[ChangedFile]) -> list[Finding]:
    """Findings on the lines the change added; older problems are not this author's to fix."""
    findings = []
    for file in changed:
        model = repo / file.path
        if model.suffix == ".sql" and model.is_file():
            sql = model.read_text(encoding="utf-8")
            found = [finding for rule in RULES for finding in rule(file.path, sql)]
            findings += [finding for finding in found if finding.line in file.added_lines]
    return findings
