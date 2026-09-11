"""
query_db_readonly - tool the agent calls to read from local anonymized
Postgres databases (running in Docker). See DbName below for supported
databases.

Security model:
1) At the start of every session, SET default_transaction_read_only = on
   is issued (+ timeouts), so any write at the Postgres level fails.
2) Before execution, the query text is additionally checked:
   - against attempts to disable/reset that safeguard,
   - against obvious write commands (INSERT/UPDATE/DELETE/DDL/...).
   This is NOT bulletproof protection (it can be bypassed with sufficiently
   creative SQL) - it's an extra tripwire. The real protection is point (1)
   plus the fact that these are local anonymized copies of the data, not
   production.
3) The target database is selected from a closed enum (DbName) - you can't
   send an arbitrary database name, only one of the pre-approved values.
4) Every attempt (allowed or blocked) is logged to a file as a JSON line,
   including which database it targeted.
"""
import json
import re
import threading
import time
from datetime import datetime, timezone
from enum import Enum

import psycopg2

import config

_log_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Allowed databases
# ---------------------------------------------------------------------------

class DbName(str, Enum):
    """Closed list of databases the tool is allowed to access.

    The values correspond to the actual database names on the Postgres
    server (same host/port/user/password from config.py, just a different
    dbname).
    """

    SHOPIFY_INTEGRATION = "shopify_integration"
    PROJECT_SERVICE = "project_service"
    NOTIFICATION_SERVICE = "notification_service"
    AVANTRO_ADMIN = "avantro_admin"
    SEARCH_SERVICE = "search_service"
    ORDER_SERVICE = "order_service"
    AFFILIATE_SERVICE = "affiliate_service"
    USER_SERVICE = "user_service"
    INTEGRATION_SERVICE = "integration_service"
    BLOG_SERVICE = "blog_service"
    TRANSLATION_SERVICE = "translation_service"


# ---------------------------------------------------------------------------
# Query safety check
# ---------------------------------------------------------------------------

# Patterns that could disable/bypass our read-only safeguard
READONLY_BYPASS_PATTERNS = [
    (re.compile(r"default_transaction_read_only\s*(=|to)\s*(off|false|0)\b", re.I),
     "attempt to disable default_transaction_read_only"),
    (re.compile(r"\breset\s+default_transaction_read_only\b", re.I),
     "RESET default_transaction_read_only (would fall back to the server default, which is usually OFF)"),
    (re.compile(r"\breset\s+all\b", re.I),
     "RESET ALL would also wipe out our read-only safeguard"),
    (re.compile(r"\bset\s+transaction\s+read\s+write\b", re.I),
     "SET TRANSACTION READ WRITE"),
    (re.compile(r"\b(begin|start\s+transaction)\b[^;]*\bread\s+write\b", re.I),
     "BEGIN/START TRANSACTION ... READ WRITE"),
    (re.compile(r"\bset\s+session\s+characteristics\s+as\s+transaction\s+read\s+write\b", re.I),
     "SET SESSION CHARACTERISTICS ... READ WRITE"),
    (re.compile(r"\bset\s+(local\s+)?statement_timeout\s*(=|to)\s*0\b", re.I),
     "disabling statement_timeout (0 = no limit)"),
    (re.compile(r"\bset\s+(local\s+)?lock_timeout\s*(=|to)\s*0\b", re.I),
     "disabling lock_timeout"),
    (re.compile(r"\bset\s+(local\s+)?idle_in_transaction_session_timeout\s*(=|to)\s*0\b", re.I),
     "disabling idle_in_transaction_session_timeout"),
]

# Obvious write/DDL commands - they have no business in a read-only query.
# \b...\b matches whole words, so it won't false-positive on e.g. an
# "updated_at" column.
WRITE_KEYWORD_PATTERNS = [
    re.compile(rf"\b{kw}\b", re.I)
    for kw in [
        "insert", "update", "delete", "truncate", "drop", "alter", "create",
        "grant", "revoke", "merge", "copy", "vacuum", "reindex",
        "refresh\\s+materialized\\s+view", "lock\\s+table",
    ]
]


def check_query_safety(sql: str) -> list[str]:
    """Returns a list of found issues. Empty list = the query looks safe."""
    violations = []
    for pattern, description in READONLY_BYPASS_PATTERNS:
        if pattern.search(sql):
            violations.append(description)
    for pattern in WRITE_KEYWORD_PATTERNS:
        if pattern.search(sql):
            violations.append(f"write/DDL keyword in query: '{pattern.pattern}'")
    return violations


def _build_guarded_sql(sql: str) -> str:
    guard = f"""\
SET default_transaction_read_only = on;
SET statement_timeout = '{config.STATEMENT_TIMEOUT}';
SET lock_timeout = '{config.LOCK_TIMEOUT}';
SET idle_in_transaction_session_timeout = '{config.IDLE_IN_TX_TIMEOUT}';
SET application_name = 'llm-diag-agent';
"""
    return guard + "\n" + sql


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log_event(event: dict) -> None:
    record = {"ts": datetime.now(timezone.utc).isoformat(), **event}
    line = json.dumps(record, ensure_ascii=False)
    with _log_lock:
        with open(config.LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")


# ---------------------------------------------------------------------------
# Postgres
# ---------------------------------------------------------------------------

MAX_OUTPUT_CHARS = 20_000


def _format_rows(columns: list[str], rows: list[tuple]) -> str:
    """Simple plain-text table output, similar to `psql`."""
    if not rows:
        return "(0 rows)"

    str_rows = [["" if v is None else str(v) for v in row] for row in rows]
    widths = [len(c) for c in columns]
    for row in str_rows:
        for i, v in enumerate(row):
            widths[i] = max(widths[i], len(v))

    def fmt(vals: list[str]) -> str:
        return " | ".join(v.ljust(widths[i]) for i, v in enumerate(vals))

    lines = [fmt(columns), "-+-".join("-" * w for w in widths)]
    lines.extend(fmt(r) for r in str_rows)
    lines.append(f"({len(rows)} row{'s' if len(rows) != 1 else ''})")
    return "\n".join(lines)


def _connect(database: DbName):
    return psycopg2.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        dbname=database.value,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        connect_timeout=config.CONNECT_TIMEOUT_S,
    )


def run_readonly_query(sql: str, database: "DbName | str") -> dict:
    """Main entry point of the tool. Always returns a dict with an 'ok' key."""
    started = time.monotonic()

    if not sql or not sql.strip():
        return {"ok": False, "blocked": False, "error": "Empty query."}

    # 0) database must be one of the allowed values - no arbitrary name
    if not isinstance(database, DbName):
        try:
            database = DbName(database)
        except ValueError:
            allowed = ", ".join(d.value for d in DbName)
            log_event({"event": "blocked", "reason": "unknown_database", "database": str(database), "sql": sql})
            return {
                "ok": False,
                "blocked": True,
                "error": f"Unknown/disallowed database '{database}'. Allowed values: {allowed}",
            }

    # 1) safety check BEFORE anything else - no connection is opened yet
    violations = check_query_safety(sql)
    if violations:
        log_event({"event": "blocked", "database": database.value, "violations": violations, "sql": sql})
        return {
            "ok": False,
            "blocked": True,
            "error": "Query blocked by safety check: " + "; ".join(violations),
        }

    guarded_sql = _build_guarded_sql(sql)

    try:
        conn = _connect(database)
    except Exception as e:
        log_event({"event": "error", "phase": "connect", "database": database.value, "error": str(e)})
        return {"ok": False, "blocked": False, "error": f"Failed to connect to DB '{database.value}': {e}"}

    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(guarded_sql)
            if cur.description is not None:
                columns = [d.name for d in cur.description]
                rows = cur.fetchall()
                output = _format_rows(columns, rows)
            else:
                output = "OK" if cur.rowcount in (-1, None) else f"OK ({cur.rowcount} rows)"

        duration_ms = int((time.monotonic() - started) * 1000)

        log_event({
            "event": "query",
            "ok": True,
            "database": database.value,
            "duration_ms": duration_ms,
            "sql": sql,
            "output_len": len(output),
        })

        truncated = len(output) > MAX_OUTPUT_CHARS
        if truncated:
            output = output[:MAX_OUTPUT_CHARS] + "\n... [output truncated, full result is in the log file] ..."

        return {"ok": True, "blocked": False, "output": output, "duration_ms": duration_ms, "truncated": truncated}

    except Exception as e:
        duration_ms = int((time.monotonic() - started) * 1000)
        log_event({"event": "error", "phase": "query", "database": database.value, "error": str(e), "sql": sql, "duration_ms": duration_ms})
        return {"ok": False, "blocked": False, "error": f"Query error: {e}", "duration_ms": duration_ms}

    finally:
        conn.close()
