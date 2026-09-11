"""
System/task prompt builders for NightCoder (see night_coder.py).

Conventions (branch-first, no unrelated refactors, commit message style,
...) are intentionally NOT duplicated here - the implement/refine step
loads them from the always-installed ~/.claude/CLAUDE.md via
setting_sources=["user"] (see implement.py), which is the single source
of truth the user maintains via GLOBAL/.claude/CLAUDE.md in this repo.
"""
from asana_tasks import AsanaTask

IMPLEMENT_SYSTEM_PROMPT = """You are implementing one Asana task, unattended, overnight.
Nobody is available to answer clarifying questions, so:

- If the task is concrete enough to implement safely, implement it fully:
  follow the nearest existing pattern in this codebase, run the smallest
  relevant test/lint commands if you can find them, and report status
  "implemented" with a short summary of what changed.
- If the task's requirements or expected behavior are too ambiguous to
  implement safely without guessing, do NOT guess and do NOT leave a
  half-finished change. Report status "skipped" with a clear skip_reason
  instead.
- You are on a dedicated branch already. Do not create branches, do not
  commit, do not push - the orchestrator handles branching and committing.
  Just edit files."""

REFINE_SYSTEM_PROMPT = IMPLEMENT_SYSTEM_PROMPT + """

You are revising your previous implementation based on code review
feedback. Address every point raised under "Mandatory" below - do not
introduce unrelated changes."""


def build_implement_prompt(task: AsanaTask) -> str:
    return (
        f"Implement this Asana task in the current repository.\n\n"
        f"Task: {task.name}\n"
        f"Asana link: {task.permalink_url}\n"
        f"Description / acceptance criteria: {task.notes_summary or '(none provided)'}"
    )


def build_refine_prompt(task: AsanaTask, mandatory_findings: str) -> str:
    return (
        f"A code reviewer found the following Mandatory (blocking) issues with your "
        f"implementation of this task. Fix them.\n\n"
        f"Task: {task.name}\n"
        f"Asana link: {task.permalink_url}\n\n"
        f"Mandatory findings:\n{mandatory_findings}"
    )


def build_review_prompt(task: AsanaTask, base_branch: str, branch_name: str) -> str:
    return (
        f"Review the local diff on branch '{branch_name}' against base branch "
        f"'{base_branch}' in this repository (e.g. `git diff {base_branch}...HEAD`).\n\n"
        f"Linked Asana task:\n"
        f"Name: {task.name}\n"
        f"URL: {task.permalink_url}\n"
        f"Description / acceptance criteria: {task.notes_summary or '(none provided)'}"
    )
