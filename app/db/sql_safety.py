from __future__ import annotations

import re
from collections.abc import Iterable

from sqlglot import exp, parse_one
from sqlglot.errors import ParseError

ALLOWED_SQL_SCHEMAS = {"serving", "marts"}
BLOCKED_FUNCTIONS = {
    "pg_sleep",
    "dblink",
    "copy",
    "pg_read_file",
    "pg_ls_dir",
    "pg_stat_file",
    "lo_import",
    "lo_export",
}
BLOCKED_EXPRESSIONS: tuple[type[exp.Expression], ...] = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Alter,
    exp.TruncateTable,
    exp.Create,
    exp.Grant,
    exp.Revoke,
)
_LIMIT_PATTERN = re.compile(r"\blimit\s+(\d+)\b", flags=re.IGNORECASE)


class UnsafeQueryError(ValueError):
    """Raised when SQL violates read-only guardrails."""


def _normalize(sql_text: str) -> str:
    return re.sub(r"\s+", " ", sql_text.strip().lower())


def _cte_names(tree: exp.Expression) -> set[str]:
    names: set[str] = set()
    for cte in tree.find_all(exp.CTE):
        alias = cte.alias
        if alias:
            names.add(alias.lower())
    return names


def _extract_schema(table: exp.Table) -> str:
    if isinstance(table.db, exp.Identifier):
        return table.db.name.lower()
    if isinstance(table.db, str):
        return table.db.lower()
    return ""


def _extract_table_name(table: exp.Table) -> str:
    if isinstance(table.this, exp.Identifier):
        return table.this.name.lower()
    if isinstance(table.this, str):
        return table.this.lower()
    return ""


def _iter_function_names(tree: exp.Expression) -> Iterable[str]:
    for node in tree.find_all(exp.Func):
        sql_name = node.sql_name() if hasattr(node, "sql_name") else ""
        if sql_name:
            yield sql_name.lower()


def validate_read_only_sql(sql_text: str, allowed_schemas: set[str] | None = None) -> None:
    normalized = _normalize(sql_text)
    if not normalized:
        raise UnsafeQueryError("Query is empty.")

    if ";" in normalized:
        raise UnsafeQueryError("Semicolons are not allowed.")

    try:
        tree = parse_one(sql_text, read="postgres")
    except ParseError as exc:
        raise UnsafeQueryError(f"Could not parse SQL safely: {exc}") from exc

    if not tree.find(exp.Select):
        raise UnsafeQueryError("Only SELECT/CTE read queries are allowed.")

    for expr_type in BLOCKED_EXPRESSIONS:
        if tree.find(expr_type):
            raise UnsafeQueryError(f"Blocked SQL expression detected: {expr_type.__name__}")

    cte_names = _cte_names(tree)
    safe_schemas = {schema.lower() for schema in (allowed_schemas or ALLOWED_SQL_SCHEMAS)}

    for table in tree.find_all(exp.Table):
        schema = _extract_schema(table)
        table_name = _extract_table_name(table)
        if table_name in cte_names:
            continue

        if not schema:
            raise UnsafeQueryError(
                "All source tables must be schema-qualified and restricted to allowlist schemas."
            )

        if schema not in safe_schemas:
            raise UnsafeQueryError(
                f"Schema '{schema}' is not allowed. Allowed schemas: {sorted(safe_schemas)}"
            )

    for func_name in _iter_function_names(tree):
        if func_name in BLOCKED_FUNCTIONS:
            raise UnsafeQueryError(f"Blocked SQL function detected: {func_name}")


def enforce_limit(sql_text: str, default_limit: int = 500, max_limit: int = 5000) -> str:
    match = _LIMIT_PATTERN.search(sql_text)
    if not match:
        return f"{sql_text.rstrip()} LIMIT {default_limit}"

    current_limit = int(match.group(1))
    if current_limit > max_limit:
        return _LIMIT_PATTERN.sub(f"LIMIT {max_limit}", sql_text)
    return sql_text
