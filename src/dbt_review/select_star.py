import re

import sqlglot
from sqlglot import exp

from dbt_review.models import Finding, Severity, Source

JINJA_BLOCK = re.compile(r"\{#.*?#\}|\{%.*?%\}", re.DOTALL)
JINJA_REF = re.compile(r"\{\{\s*ref\(\s*['\"](\w+)['\"]\s*\)\s*\}\}")
JINJA_EXPRESSION = re.compile(r"\{\{.*?\}\}")


def check(path: str, sql: str) -> list[Finding]:
    tree = sqlglot.parse_one(_without_jinja(sql), dialect="duckdb")
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
        for star in _open_stars(tree, ctes)
    ]


def _without_jinja(sql: str) -> str:
    """SQL that sqlglot can parse, with every statement still on its original line."""
    sql = JINJA_BLOCK.sub(lambda block: "\n" * block.group().count("\n"), sql)
    sql = JINJA_REF.sub(r"__ref__\1", sql)
    return JINJA_EXPRESSION.sub("__jinja__", sql)


def _open_stars(select: exp.Select, ctes: dict[str, exp.Select]) -> list[exp.Star]:
    """Stars that reach a relation without the columns being written out on the way."""
    select = _output_select(select, ctes)
    return [
        star
        for star in _stars(select)
        if any(name not in ctes or _open_stars(ctes[name], ctes) for name in _sources(star, select))
    ]


def _output_select(select: exp.Select, ctes: dict[str, exp.Select]) -> exp.Select:
    """The select that decides the columns: `select * from final` defers to `final`."""
    while _is_pass_through(select) and _tables(select)[0].name in ctes:
        select = ctes[_tables(select)[0].name]
    return select


def _is_pass_through(select: exp.Select) -> bool:
    only_a_star = len(select.expressions) == 1 and isinstance(select.expressions[0], exp.Star)
    return only_a_star and len(_tables(select)) == 1


def _stars(select: exp.Select) -> list[exp.Star]:
    """`*` and `customers.*` among the selected columns; `count(*)` is not one."""
    columns = [c.this if isinstance(c, exp.Column) else c for c in select.expressions]
    return [column for column in columns if isinstance(column, exp.Star)]


def _sources(star: exp.Star, select: exp.Select) -> list[str]:
    """Names of the CTEs or relations the star expands."""
    tables = _tables(select)
    if isinstance(star.parent, exp.Column):
        tables = [table for table in tables if table.alias_or_name == star.parent.table]
    return [table.name for table in tables]


def _tables(select: exp.Select) -> list[exp.Table]:
    joined = [join.this for join in select.args.get("joins") or []]
    return [t for t in [select.args["from_"].this, *joined] if isinstance(t, exp.Table)]
