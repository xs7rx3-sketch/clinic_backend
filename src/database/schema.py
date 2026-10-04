import logging
import os
from sqlalchemy import inspect
from src.database.connection import engine

log = logging.getLogger(__name__)

_CACHE: str | None = None


def _fetch_structure() -> str:
    """Introspects tables and column metadata dynamically using SQLAlchemy Inspector."""
    try:
        inspector = inspect(engine)
        table_names = sorted(inspector.get_table_names())
        if not table_names:
            return ""

        lines = ["DATABASE STRUCTURE:"]
        for table in table_names:
            if table.startswith(("pg_", "sql_")):
                continue
            lines.append(f"\nTABLE: {table}")
            for col in inspector.get_columns(table):
                nullable = "NULL" if col.get("nullable", True) else "NOT NULL"
                default = f" DEFAULT {col['default']}" if col.get("default") else ""
                lines.append(f"  - {col['name']}: {col['type']} [{nullable}{default}]")
        return "\n".join(lines)
    except Exception as e:
        log.error("Failed to inspect schema via SQLAlchemy: %s", e)
        return ""


def _load_semantics() -> str:
    """Loads semantic guidelines and clinical policies from schema.txt."""
    schema_path = os.path.join(os.path.dirname(__file__), "schema.txt")
    if os.path.exists(schema_path):
        with open(schema_path, "r", encoding="utf-8-sig") as f:
            return f.read().strip()
    return ""


def load_schema(force_refresh: bool = False) -> str:
    """Returns database schema context combined with clinical rules."""
    global _CACHE
    if _CACHE and not force_refresh:
        return _CACHE

    structure = _fetch_structure()
    semantics = _load_semantics()

    if not structure:
        _CACHE = semantics or "DATABASE SCHEMA UNAVAILABLE"
        return _CACHE

    parts = [structure]
    if semantics:
        parts.append("\n" + "=" * 70 + "\n")
        parts.append(semantics)

    _CACHE = "\n".join(parts)
    return _CACHE
