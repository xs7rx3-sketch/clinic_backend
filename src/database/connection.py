import logging
import os
import re
from contextlib import contextmanager
from typing import Any, Generator, Optional
from urllib.parse import unquote
import psycopg2
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()
log = logging.getLogger(__name__)

CONN_STR = os.getenv("POSTGRES_URI")
if not CONN_STR:
    raise RuntimeError("POSTGRES_URI is not set. Please provide the Neon PostgreSQL connection string in .env")

# SQLAlchemy 2.0 Engine & Session Factory
engine = create_engine(CONN_STR, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager providing a transactional database session."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _parse_conn_str(conn_str: str) -> dict[str, Any]:
    """Extracts connection parameters from connection string."""
    m = re.match(r"^postgresql://([^:]+):(.+)@([^@/:]+):(\d+)/(.+)$", conn_str)
    if m:
        user, pwd, host, port, db = m.groups()
        return {
            "user": user,
            "password": unquote(pwd),
            "host": host,
            "port": int(port),
            "dbname": db,
        }
    return {}


def get_connection():
    """Establishes and returns a low-level psycopg2 database connection."""
    params = _parse_conn_str(CONN_STR)
    if params:
        return psycopg2.connect(**params)
    return psycopg2.connect(CONN_STR)


def _normalize_table_names(sql: str) -> str:
    """Ensures database entity names map accurately to plural schema tables."""
    replacements = [
        (r"\bFROM\s+doctor\b", "FROM doctors"),
        (r"\bJOIN\s+doctor\b", "JOIN doctors"),
        (r"\bUPDATE\s+doctor\b", "UPDATE doctors"),
        (r"\bINSERT\s+INTO\s+doctor\b", "INSERT INTO doctors"),
        (r"\bFROM\s+department\b", "FROM departments"),
        (r"\bJOIN\s+department\b", "JOIN departments"),
        (r"\bUPDATE\s+department\b", "UPDATE departments"),
        (r"\bINSERT\s+INTO\s+department\b", "INSERT INTO departments"),
        (r"\bFROM\s+appointment\b", "FROM appointments"),
        (r"\bJOIN\s+appointment\b", "JOIN appointments"),
        (r"\bUPDATE\s+appointment\b", "UPDATE appointments"),
        (r"\bINSERT\s+INTO\s+appointment\b", "INSERT INTO appointments"),
        (r"\bFROM\s+patient\b", "FROM patients"),
        (r"\bJOIN\s+patient\b", "JOIN patients"),
        (r"\bUPDATE\s+patient\b", "UPDATE patients"),
        (r"\bINSERT\s+INTO\s+patient\b", "INSERT INTO patients"),
        (r"\bFROM\s+hospital\b", "FROM hospitals"),
        (r"\bJOIN\s+hospital\b", "JOIN hospitals"),
    ]
    for pattern, repl in replacements:
        sql = re.sub(pattern, repl, sql, flags=re.IGNORECASE)
    return sql


def execute_sql(sql_query: str, params: Optional[Any] = None) -> dict[str, Any]:
    """Executes dynamic query produced by the AI Agent and returns mapped dictionary results."""
    cleaned_query = _normalize_table_names(sql_query.strip().rstrip(";"))

    first_word = cleaned_query.split()[0].upper() if cleaned_query else ""
    if first_word in ("DROP", "TRUNCATE", "ALTER"):
        return {
            "status": "ERROR",
            "error": f"Security violation: {first_word} operations are strictly forbidden.",
        }

    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(cleaned_query, params)

        is_query = first_word in ("SELECT", "WITH")
        has_returning = "RETURNING" in cleaned_query.upper()

        if is_query or has_returning:
            col_names = [desc[0] for desc in cur.description] if cur.description else []
            rows = cur.fetchall()
            results = [
                dict(zip(col_names, [str(val) if val is not None else None for val in row]))
                for row in rows
            ]
            if not is_query:
                conn.commit()
            conn.close()
            return {"status": "SUCCESS", "count": len(results), "data": results}
        else:
            affected = cur.rowcount
            conn.commit()
            conn.close()
            return {"status": "SUCCESS", "affected_rows": affected, "data": []}
    except Exception as e:
        log.error("Execution error: %s", e)
        return {"status": "ERROR", "error": str(e)}
