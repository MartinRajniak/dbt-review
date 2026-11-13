from sqlglot import exp

from dbt_review.models import Finding, Severity, Source
from dbt_review.sql import parse_model

check_id = "select-star"


def check(path: str, sql: str) -> list[Finding]:
    tree = parse_model(sql)
    if not isinstance(tree, exp.Select):  # e.g. a union: not checked
        return []
    ctes = {cte.alias: cte.this for cte in tree.find_all(exp.CTE)}
    return [
        Finding(
            check_id=check_id,
            source=Source.RULE,
            severity=Severity.WARNING,
            file=path,
            line=star.meta["line"],
            message="The model's columns are not written out: a column added upstream appears here unannounced.",
            suggestion="List the columns this model should return.",
        )
        for star in _open_stars(tree, ctes)
    ]


def _open_stars(select: exp.Select, ctes: dict[str, exp.Select]) -> list[exp.Star]:
    """Stars that reach a relation without the columns being written out on the way."""
    select, ctes = _output_select(select, ctes)
    return [
        star
        for star in _stars(select)
        if any(
            name not in ctes or _open_stars(ctes[name], _without(ctes, name))
            for name in _sources(star, select)
        )
    ]


def _output_select(
    select: exp.Select, ctes: dict[str, exp.Select]
) -> tuple[exp.Select, dict[str, exp.Select]]:
    """A closing `select * from final` names no columns; the select inside `final` does."""
    while (source := _passed_through(select)) in ctes:
        select, ctes = ctes[source], _without(ctes, source)
    return select, ctes


def _without(ctes: dict[str, exp.Select], name: str) -> dict[str, exp.Select]:
    """Inside a CTE its own name means the table it reads, so `customers as (select * from raw.customers)` ends."""
    return {other: cte for other, cte in ctes.items() if other != name}


def _passed_through(select: exp.Select) -> str:
    """The table a bare `select * from x` reads; empty when the select is anything else."""
    tables = _tables(select)
    only_a_star = len(select.expressions) == 1 and isinstance(select.expressions[0], exp.Star)
    return _cte_name(tables[0]) if only_a_star and len(tables) == 1 else ""


def _stars(select: exp.Select) -> list[exp.Star]:
    """`*` and `customers.*` among the selected columns; `count(*)` is not one."""
    columns = [c.this if isinstance(c, exp.Column) else c for c in select.expressions]
    return [column for column in columns if isinstance(column, exp.Star)]


def _sources(star: exp.Star, select: exp.Select) -> list[str]:
    """Names of the CTEs or relations the star expands."""
    tables = _tables(select)
    if isinstance(star.parent, exp.Column):
        tables = [table for table in tables if table.alias_or_name == star.parent.table]
    return [_cte_name(table) for table in tables]


def _cte_name(table: exp.Table) -> str:
    """The name a CTE could answer to; `raw.payments` is a table even when a CTE is called `payments`."""
    return "" if table.db else table.name


def _tables(select: exp.Select) -> list[exp.Table]:
    if not (from_ := select.args.get("from_")):  # `select 1 as id` reads nothing
        return []
    joined = [join.this for join in select.args.get("joins") or []]
    return [t for t in [from_.this, *joined] if isinstance(t, exp.Table)]
