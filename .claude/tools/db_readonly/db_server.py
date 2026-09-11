#!/usr/bin/env python3
"""
MCP server (stdio) that exposes query_db_readonly as a tool for Claude
Code - i.e. it runs under your Claude Pro/Max subscription via the `claude`
CLI, not via ANTHROPIC_API_KEY / Anthropic API billing.

The security logic (read-only guard, query check, logging, list of allowed
databases) is unchanged in db_readonly_tool.py - this file is just a thin
MCP wrapper around run_readonly_query(). It connects directly to local
anonymized Postgres databases (in Docker) - no Kubernetes. See DbName in
db_readonly_tool.py for supported databases.

Registering with Claude Code (from this directory):
    claude mcp add db-readonly -- python3 "$(pwd)/db_server.py"

To make it available across all projects, add `-s user`:
    claude mcp add db-readonly -s user -- python3 "$(pwd)/db_server.py"

Then just type a task in a regular `claude` session, e.g.:
    Check order_service for orders with an invalid status in the last
    7 days and suggest a fix
and Claude will call the mcp__db-readonly__query_db_readonly tool itself
with the appropriate database as an argument.

Standalone run for debugging (speaks the MCP protocol over stdio, not
meant for manual interaction):
    python3 db_server.py
"""
from mcp.server import MCPServer

from db_readonly_tool import DbName, run_readonly_query

mcp = MCPServer("db-readonly")

_ALLOWED_DBS = ", ".join(d.value for d in DbName)

QUERY_TOOL_DESCRIPTION = (
    "Runs a READ-ONLY SQL query (typically SELECT/EXPLAIN) against one of "
    f"the local anonymized Postgres databases (Docker): {_ALLOWED_DBS}. "
    "The session has default_transaction_read_only=on enforced, so any "
    "write fails at the database level. Write/DDL commands "
    "(INSERT/UPDATE/DELETE/DROP/ALTER/...) are additionally blocked before "
    "execution as an extra safeguard. The `database` parameter must be one "
    "of the allowed values above - any other value is rejected. Use it for "
    "exploring data, checking integrity, and verifying hypotheses across "
    "microservices - never write write-type SQL, it will be blocked."
)


@mcp.tool(description=QUERY_TOOL_DESCRIPTION)
def query_db_readonly(sql: str, database: DbName) -> str:
    """
    Args:
        sql: SQL query (SELECT / EXPLAIN / etc.).
        database: The database to run the query against - one of DbName
            (e.g. order_service, user_service, ...).
    """
    result = run_readonly_query(sql, database)

    if result.get("blocked"):
        return f"BLOCKED by safety check: {result['error']}"
    if not result["ok"]:
        return f"Error running query: {result.get('error') or result.get('output')}"
    return result["output"] or "(empty result)"


if __name__ == "__main__":
    mcp.run()
