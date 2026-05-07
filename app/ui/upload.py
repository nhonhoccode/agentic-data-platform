from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from typing import Any

import psycopg
from fastapi import UploadFile

from app.config import get_settings

ALLOWED_EXTENSIONS = {".csv", ".txt", ".pdf"}
MAX_BYTES = 50 * 1024 * 1024  # 50MB
UPLOAD_SCHEMA = "uploads"
MAX_ROWS = 50_000


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", name).strip("_").lower()
    return slug[:60] or "data"


def _quote_ident(name: str) -> str:
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name):
        raise ValueError(f"invalid identifier: {name}")
    return name


async def handle_upload(file: UploadFile) -> dict[str, Any]:
    filename = file.filename or "upload.csv"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"unsupported file type: {ext or 'unknown'}")

    content = await file.read()
    if len(content) > MAX_BYTES:
        raise ValueError(f"file too large: {len(content)} bytes (max {MAX_BYTES})")

    if ext == ".pdf":
        return _handle_pdf(filename, content)

    return _handle_csv(filename, content)


def _handle_pdf(filename: str, content: bytes) -> dict[str, Any]:
    try:
        from pypdf import PdfReader
    except Exception:  # noqa: BLE001
        return {
            "kind": "pdf",
            "filename": filename,
            "size": len(content),
            "note": "PDF text extraction unavailable (pypdf not installed)",
        }

    reader = PdfReader(io.BytesIO(content))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(pages).strip()
    return {
        "kind": "pdf",
        "filename": filename,
        "size": len(content),
        "n_pages": len(pages),
        "preview": text[:1500],
    }


def _handle_csv(filename: str, content: bytes) -> dict[str, Any]:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV has no header row")

    columns = [_quote_ident(_slugify(c) or f"col_{i}") for i, c in enumerate(reader.fieldnames)]
    rows: list[list[Any]] = []
    for raw in reader:
        if len(rows) >= MAX_ROWS:
            break
        rows.append([raw.get(c) for c in reader.fieldnames])

    base_name = _slugify(filename.rsplit(".", 1)[0])
    suffix = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    table_name = _quote_ident(f"{base_name}_{suffix}")

    settings = get_settings()
    with psycopg.connect(settings.postgres_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {UPLOAD_SCHEMA}")
            col_defs = ", ".join(f"{c} text" for c in columns)
            cur.execute(f"CREATE TABLE {UPLOAD_SCHEMA}.{table_name} ({col_defs})")
            cur.execute(f"GRANT USAGE ON SCHEMA {UPLOAD_SCHEMA} TO {settings.postgres_readonly_user}")
            cur.execute(
                f"GRANT SELECT ON {UPLOAD_SCHEMA}.{table_name} TO {settings.postgres_readonly_user}"
            )
            placeholders = ",".join(["%s"] * len(columns))
            cur.executemany(
                f"INSERT INTO {UPLOAD_SCHEMA}.{table_name} VALUES ({placeholders})",
                rows,
            )
        conn.commit()

    return {
        "kind": "csv",
        "filename": filename,
        "table": f"{UPLOAD_SCHEMA}.{table_name}",
        "rows_loaded": len(rows),
        "columns": columns,
        "size": len(content),
    }
