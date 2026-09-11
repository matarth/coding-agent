"""
Configuration for the read-only DB tool (see db_readonly_tool.py / db_server.py).

Connects to local anonymized Postgres databases (Docker) - the target
database is chosen per-query from the closed DbName enum, while
host/port/user/password are shared by all of them (same Postgres server,
just a different dbname). Values are read from a `.env` file next to this
script; `.env` itself does not belong in git.
"""
import os

from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.environ.get("DB_AGENT_HOST", "localhost")
DB_PORT = os.environ.get("DB_AGENT_PORT", "5432")
DB_USER = os.environ.get("DB_AGENT_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_AGENT_PASSWORD", "")

# Postgres session-level safeguards, see db_readonly_tool.py -> _build_guarded_sql()
STATEMENT_TIMEOUT = "60s"
LOCK_TIMEOUT = "3s"
IDLE_IN_TX_TIMEOUT = "90s"

# Hard cap on establishing the connection (the DB is local, so a short timeout is enough)
CONNECT_TIMEOUT_S = 10

LOG_FILE = os.environ.get("DB_AGENT_LOG_FILE", "db_agent.log")
