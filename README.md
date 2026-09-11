## Overview

This repo shares a Claude Code project setup, built around the three
required building blocks — **no plugins or marketplace**:

- **MCP servers** (`.mcp.json`, `PROJECT/.claude/tools/`): `asana` (hosted,
  OAuth) and `db-readonly` (local, read-only Postgres access) — see below.
- **Skills** (`PROJECT/.claude/skills/`): [`code-review`](PROJECT/.claude/skills/code-review/SKILL.md),
  [`bug-fix`](PROJECT/.claude/skills/bug-fix/SKILL.md), and
  [`docblock-audit`](PROJECT/.claude/skills/docblock-audit/SKILL.md) —
  each a self-contained workflow invoked for a specific kind of task.
- **Subagents** (`PROJECT/.claude/agents/`): [`investigator`](PROJECT/.claude/agents/investigator.md)
  — a read-only subagent for investigating production data across the
  microservice databases (via `db-readonly`) and Asana. It's a subagent
  rather than a skill because its *process* is noisy (exploratory
  queries, dead ends) while its *result* summarizes cleanly, and its
  narrower toolset (no `Write`/`Edit`) can't accidentally start changing
  anything mid-investigation. [`docblock-checker`](PROJECT/.claude/agents/docblock-checker.md)
  is the same shape, used by `docblock-audit` — see below.
- **Global conventions** (`GLOBAL/.claude/CLAUDE.md`): install at
  `~/.claude/CLAUDE.md` — branch-first workflow, no force-push, no
  Kubernetes access, etc. Shared by every skill/subagent/tool below instead
  of being repeated in each.

`PROJECT/.claude/tools/night_coder/` is a **bonus, experimental side
project** — an unattended overnight orchestrator built directly on the
Claude Agent SDK, not a native MCP server/Skill/Subagent. It's included for
reference but isn't one of the three required building blocks; see its own
section at the bottom of this file.

## `db-readonly` MCP tool

Read-only SQL access to the local anonymized Postgres databases, exposed as
the `mcp__db-readonly__query_db_readonly` tool
(`PROJECT/.claude/tools/db_readonly/db_server.py`).

### Prerequisites

- **Python packages** — install with:
  ```
  pip3 install --user "mcp>=1.0.0" psycopg2-binary python-dotenv
  ```
  (`mcp` must provide `mcp.server.fastmcp.FastMCP`)
- **Local Postgres (Docker)** reachable with the anonymized databases already
  loaded, one of: `shopify_integration`, `project_service`,
  `notification_service`, `avantro_admin`, `search_service`, `order_service`,
  `affiliate_service`, `user_service`, `integration_service`, `blog_service`,
  `translation_service`.
- **`.env` file** next to `db_server.py`
  (`PROJECT/.claude/tools/db_readonly/.env`, not committed to git) with the
  connection details, e.g.:
  ```
  DB_AGENT_HOST=localhost
  DB_AGENT_PORT=5432
  DB_AGENT_USER=postgres
  DB_AGENT_PASSWORD=...
  ```
  All variables are optional and fall back to `localhost` / `5432` /
  `postgres` / empty password if omitted.
- **`db_server.py` must be executable** (`chmod +x`) and start with a
  `#!/usr/bin/env python3` shebang, since it is registered and spawned
  directly (not via `python3 db_server.py`).

### Registering

Run once, from inside `PROJECT/.claude/tools/db_readonly/`:
```
claude mcp add db-readonly "$(pwd)/db_server.py"
```
Add `-s user` to make it available across all projects. Registration takes
effect only in new `claude` sessions started afterwards. Verify with
`claude mcp list`.

## Subagents

`PROJECT/.claude/agents/investigator.md` is a plain Claude Code subagent
(loaded automatically from `.claude/agents/` in this repo, no registration
step needed) — delegate to it with the `Task` tool.

- **Read-only across the board**: only `Read, Grep, Glob, Bash,
  mcp__db-readonly__query_db_readonly, mcp__asana__get_task(_stories)` —
  no `Write`/`Edit`, so it's structurally unable to start changing
  anything while it's still figuring out what's going on.
- **Standalone use**: ask it directly to explain a concrete production
  case ("why is order X stuck", "what's user Y's current state") across
  the project's microservice databases.
- **Used by the `bug-fix` skill**: its "inspect production state" step
  delegates to `investigator` instead of running the exploratory
  `db-readonly` queries inline — the main conversation only sees the
  records that actually matter for the reproduction, not every dead end
  along the way.

Why this one thing is a subagent and the reproduce → fix → verify flow
around it (`bug-fix`) is a skill instead: `bug-fix` is one continuous,
stateful chain where every step needs the *exact* artifacts of the
previous one (the specific records → the specific test fixtures → the
specific fix) — splitting that across subagent boundaries would mean
re-summarizing and losing fidelity at every hop. `investigator`'s job, by
contrast, is inherently noisy-in/clean-out, and benefits from being
tool-restricted — exactly what a subagent is good for.

## Docblock audit

Checks that docblocks (PHPDoc, JSDoc/TSDoc, Python docstrings) still
match what their code actually does, and keeps a browsable report.

- **`docblock-checker`** (`PROJECT/.claude/agents/docblock-checker.md`):
  a read-only subagent — given a file and the symbols in it to check, it
  compares each docblock's claims against the implementation and returns
  a JSON verdict per symbol. Same rationale as `investigator`: the
  checking itself is exploratory (reading implementations, following
  calls), the result is one clean verdict per docblock.
- **`docblock-audit`** (`PROJECT/.claude/skills/docblock-audit/SKILL.md`):
  the orchestrating skill — discovers docblocks in a given path, decides
  which ones actually need a (re-)check, delegates those to
  `docblock-checker` via `Task`, and merges the results into a
  persisted JSON report.

Staleness: each entry in the report is keyed by a hash of the docblock
text plus the code it documents. A docblock is skipped on a run as long
as that hash hasn't changed *and* it was last checked within the
staleness threshold (default 180 days, overridable per run) — so nothing
is endlessly re-checked, but even an unchanged docblock eventually comes
up for review again.

Output: `PROJECT/.claude/tools/docblock_checker/reports/docblock_report.json`
(the persisted state) and `docblock_report.html`, regenerated from it by
`generate_report.py` — a single self-contained file (the report data is
inlined) that opens directly from disk, with filtering by status/file and
click-to-expand per-symbol findings. Both are gitignored — local, regenerated
output, not part of any commit.

## NightCoder — unattended overnight coding agent (bonus, experimental)

Pulls incomplete Asana tasks assigned to you from a given project, and for
each one runs branch → implement → code review (reusing the `code-review`
skill) → commit-if-clean / refine-and-retry, entirely locally. **Never
pushes and never opens an MR** — review the resulting branches yourself in
the morning, then push and open MRs by hand.
(`PROJECT/.claude/tools/night_coder/night_coder.py`)

### Prerequisites

- Python package: `claude-agent-sdk` (installed e.g. via
  `pip3 install --user claude-agent-sdk`)
- `git`, and `gh` if you want the review step's read-only GitHub inspection
  to work when reviewing against an existing MR
- The `asana` MCP server already registered and OAuth-authorized for this
  repo (`.mcp.json` + `.claude/settings.local.json`) — NightCoder reuses
  that same registration rather than a separate one
- `~/.claude/CLAUDE.md` installed with the conventions from
  `GLOBAL/.claude/CLAUDE.md` (branch-first, no force/push, no k8s, ...) —
  NightCoder's implement/review steps load it via `setting_sources=["user"]`
  instead of duplicating those rules; its own `PreToolUse` hooks enforce
  the hard safety limits (no push, no force, no k8s) regardless

### IMPORTANT: run once, live, before you leave

Overnight OAuth token refresh for the Asana MCP server can fail silently or
require re-authentication in a browser. Run this once while you're still
at your desk, right before you leave:
```
python3 night_coder.py --dry-run --asana-project <GID>
```
This only fetches and prints the matching task list — no git/code changes
— so any OAuth prompt surfaces now, not at 2am.

### Usage

Run from inside the target repo (it auto-detects the repo root via
`git rev-parse --show-toplevel`):
```
python3 night_coder.py --asana-project <GID> [--tag <tag>] \
    [--max-tasks 5] [--max-review-iterations 3] [--max-hours 8] \
    [--max-minutes-per-task 45] [--model sonnet]
```
Branches from whatever branch is currently checked out when it starts;
each task branches fresh from that same base as
`night-coder/<slug>-<asana-gid-suffix>`. Run it under `tmux`/`nohup` if you
want it to survive closing your terminal.

Output: `PROJECT/.claude/tools/night_coder/reports/night_coder_output_<date>.md`
— completed tasks with branch name + summary, tasks that hit the review
iteration cap with the reviewer's last Mandatory findings, and tasks
skipped as too ambiguous to implement safely.
