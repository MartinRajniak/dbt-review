import re

import sqlglot
from sqlglot import exp

from dbt_review.models import Finding, Severity, Source

REF = re.compile(r"\{\{\s*ref\(\s*['\"](\w+)['\"]\s*\)\s*\}\}")


def check(path: str, sql: str) -> list[Finding]:
    tree = sqlglot.parse_one(REF.sub(r"__ref__\1", sql), dialect="duckdb")
    return [
        Finding(
            check_id="select-star",
            source=Source.RULE,
            severity=Severity.WARNING,
            file=path,
            line=star.meta["line"],
            message="The model's columns are not written out: a column added upstream appears here unannounced.",
            suggestion="List the columns this model should return.",
        )
        for star in tree.find_all(exp.Star)
    ]
