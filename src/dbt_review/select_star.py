import re

import sqlglot
from sqlglot import exp

from dbt_review.models import Finding, Severity, Source

REF = re.compile(r"\{\{\s*ref\(\s*['\"](\w+)['\"]\s*\)\s*\}\}")


def check(path: str, sql: str) -> list[Finding]:
    tree = sqlglot.parse_one(REF.sub(r"__ref__\1", sql), dialect="duckdb")
    ctes = {cte.alias: cte.this for cte in tree.find_all(exp.CTE)}
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
        for star in _stars(_output_select(tree, ctes))
    ]


def _output_select(select: exp.Select, ctes: dict[str, exp.Select]) -> exp.Select:
    """The select that decides the model's columns: `select * from final` defers to `final`."""
    while _is_pass_through(select) and _source(select) in ctes:
        select = ctes[_source(select)]
    return select


def _stars(select: exp.Select) -> list[exp.Star]:
    """`*` and `customers.*` among the selected columns; `count(*)` is not one."""
    columns = [c.this if isinstance(c, exp.Column) else c for c in select.expressions]
    return [column for column in columns if isinstance(column, exp.Star)]


def _is_pass_through(select: exp.Select) -> bool:
    only_a_star = len(select.expressions) == 1 and isinstance(select.expressions[0], exp.Star)
    return only_a_star and not select.args.get("joins")


def _source(select: exp.Select) -> str:
    return select.args["from_"].this.name
