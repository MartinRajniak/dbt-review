"""Parse a dbt model's SQL without compiling it.

Jinja is swapped for placeholders: compiling would turn ref() into a plain table name
and move the line numbers.
"""

import re

import sqlglot
from sqlglot import exp

# Comments, statements and config() render to nothing; dbt reads config() while parsing.
JINJA_BLOCK = re.compile(r"\{#.*?#\}|\{%.*?%\}|\{\{\s*config\(.*?\)\s*\}\}", re.DOTALL)
JINJA_REF = re.compile(r"\{\{\s*ref\(\s*['\"](\w+)['\"]\s*\)\s*\}\}")
JINJA_EXPRESSION = re.compile(r"\{\{.*?\}\}")
PLACEHOLDER_PREFIX = "__"


def parse_model(sql: str) -> exp.Expr:
    sql = JINJA_BLOCK.sub(lambda block: "\n" * block.group().count("\n"), sql)
    sql = JINJA_REF.sub(rf"{PLACEHOLDER_PREFIX}ref__\1", sql)
    sql = JINJA_EXPRESSION.sub(f"{PLACEHOLDER_PREFIX}jinja__", sql)
    return sqlglot.parse_one(sql, dialect="duckdb")


def is_placeholder(name: str) -> bool:
    """True for a name that stands in for ref(), source() or another Jinja expression."""
    return name.startswith(PLACEHOLDER_PREFIX)
