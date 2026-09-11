"""
Asana task fetching for NightCoder (see night_coder.py).

Reuses the target repo's own already-registered/authorized `asana` MCP
server (read straight out of its .mcp.json at runtime) instead of setting
up a second OAuth client - see README.md "NightCoder" section for the
overnight-OAuth risk this implies and the required --dry-run warm-up run.
"""
import json
from dataclasses import dataclass
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query


@dataclass
class AsanaTask:
    gid: str
    name: str
    permalink_url: str
    notes_summary: str = ""


TASK_LIST_SCHEMA = {
    "type": "object",
    "properties": {
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "gid": {"type": "string"},
                    "name": {"type": "string"},
                    "permalink_url": {"type": "string"},
                    "notes_summary": {
                        "type": "string",
                        "description": "Short summary of the task's description / acceptance criteria.",
                    },
                },
                "required": ["gid", "name", "permalink_url"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["tasks"],
    "additionalProperties": False,
}


def _load_asana_server_config(repo_root: Path) -> dict:
    mcp_json = json.loads((repo_root / ".mcp.json").read_text(encoding="utf-8"))
    try:
        return mcp_json["mcpServers"]["asana"]
    except KeyError as exc:
        raise RuntimeError(
            "No 'asana' MCP server found in .mcp.json - NightCoder needs the same "
            "Asana MCP registration used interactively in this repo."
        ) from exc


async def fetch_tasks(
    asana_project: str, tag: str | None, max_tasks: int, repo_root: Path,
) -> list[AsanaTask]:
    """Fetch incomplete Asana tasks assigned to the current user in
    `asana_project` (optionally further filtered by `tag`), capped at
    `max_tasks`. Raises RuntimeError if the Asana MCP call doesn't come
    back with structured output - callers must treat that as a hard
    failure (e.g. broken OAuth) and not proceed to any git/code changes.
    """
    options = ClaudeAgentOptions(
        mcp_servers={"asana": _load_asana_server_config(repo_root)},
        allowed_tools=["mcp__asana__get_me", "mcp__asana__search_tasks", "mcp__asana__get_task"],
        system_prompt=(
            "You are a read-only Asana task fetcher. Never create, update, comment "
            "on, or delete anything in Asana - only read."
        ),
        output_format={"type": "json_schema", "schema": TASK_LIST_SCHEMA},
        setting_sources=["user"],
    )

    tag_clause = f" that are also tagged '{tag}'" if tag else ""
    prompt = (
        "Call mcp__asana__get_me to find the current user. Then find incomplete "
        f"tasks in Asana project {asana_project} assigned to that user{tag_clause}. "
        f"Return at most {max_tasks} of them as the required structured output. "
        "For notes_summary, give a short 1-3 sentence summary of the task's "
        "description / acceptance criteria."
    )

    structured = None
    async for msg in query(prompt=prompt, options=options):
        if isinstance(msg, ResultMessage) and msg.structured_output:
            structured = msg.structured_output

    if structured is None:
        raise RuntimeError(
            "Asana fetch returned no structured output - aborting before any "
            "git/implement work. This usually means the 'asana' MCP server needs "
            "re-authentication; run with --dry-run while at your desk to fix it."
        )

    return [AsanaTask(**t) for t in structured["tasks"]][:max_tasks]
