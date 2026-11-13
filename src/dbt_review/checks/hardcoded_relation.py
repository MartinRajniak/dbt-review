from sqlglot import exp

from dbt_review.models import Finding, Severity, Source
from dbt_review.sql import is_placeholder, parse_model

check_id = "hardcoded-relation"


def check(path: str, sql: str) -> list[Finding]:
    tree = parse_model(sql)
    ctes = {cte.alias for cte in tree.find_all(exp.CTE)}
    return [
        Finding(
            check_id=check_id,
            source=Source.RULE,
            severity=Severity.ERROR,
            file=path,
            line=table.this.meta["line"],
            message=f"`{_name(table)}` is named directly, so dbt does not know this model depends on it: "
            "build order and other environments can break.",
            suggestion=f"Use {{{{ ref('{table.name}') }}}}, or {{{{ source(...) }}}} for a raw table.",
        )
        for table in tree.find_all(exp.Table)
        if _named_directly(table, ctes)
    ]


def _named_directly(table: exp.Table, ctes: set[str]) -> bool:
    """Not a CTE, not ref() or source(), and not a table function such as generate_series()."""
    return bool(table.name) and table.name not in ctes and not is_placeholder(table.name)


def _name(table: exp.Table) -> str:
    return ".".join(part.name for part in table.parts)
