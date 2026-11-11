from pathlib import Path

from dbt_review import select_star
from dbt_review.diff import ChangedFile
from dbt_review.models import Finding


def run_checks(repo: Path, changed: list[ChangedFile]) -> list[Finding]:
    findings = []
    for file in changed:
        model = repo / file.path
        if model.suffix == ".sql" and model.is_file():
            findings += select_star.check(file.path, model.read_text(encoding="utf-8"))
    return findings
