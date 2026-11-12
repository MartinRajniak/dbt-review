from typing import Protocol

from dbt_review.checks import hardcoded_relation, select_star
from dbt_review.models import Finding


class Rule(Protocol):
    """A deterministic check on one model. Each module in this package is one."""

    check_id: str

    def check(self, path: str, sql: str) -> list[Finding]: ...


RULES: list[Rule] = [select_star, hardcoded_relation]
