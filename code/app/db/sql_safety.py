import re

BLOCKED_PATTERNS = [
    r"\binsert\b",
    r"\bupdate\b",
    r"\bdelete\b",
    r"\bdrop\b",
    r"\balter\b",
    r"\btruncate\b",
    r"\bgrant\b",
    r"\brevoke\b",
    r"\bcopy\b",
    r"\bcreate\b",
]


class UnsafeQueryError(ValueError):
    """Raised when SQL violates read-only guardrails."""


def _normalize(sql_text: str) -> str:
    return re.sub(r"\s+", " ", sql_text.strip().lower())


def validate_read_only_sql(sql_text: str) -> None:
    normalized = _normalize(sql_text)

    if not normalized:
        raise UnsafeQueryError("Query is empty.")

    if ";" in normalized:
        raise UnsafeQueryError("Semicolons are not allowed.")

    if not (normalized.startswith("select") or normalized.startswith("with")):
        raise UnsafeQueryError("Only SELECT/CTE read queries are allowed.")

    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, normalized):
            raise UnsafeQueryError(f"Blocked SQL keyword detected: {pattern}")


_LIMIT_PATTERN = re.compile(r"\blimit\s+(\d+)\b", flags=re.IGNORECASE)


def enforce_limit(sql_text: str, default_limit: int = 500, max_limit: int = 5000) -> str:
    match = _LIMIT_PATTERN.search(sql_text)
    if not match:
        return f"{sql_text.rstrip()} LIMIT {default_limit}"

    current_limit = int(match.group(1))
    if current_limit > max_limit:
        return _LIMIT_PATTERN.sub(f"LIMIT {max_limit}", sql_text)
    return sql_text
