"""
Deterministic git operations for NightCoder (see night_coder.py).

Everything here is a plain `subprocess` call driven by Python, not by an
LLM - these are the *only* code paths allowed to actually create branches
and commit. The implement/review agents are additionally hook-gated (see
safety_hooks.py) to never push, force, or discard work themselves; this
module is the trusted counterpart that performs the real git actions.
"""
import re
import subprocess
from pathlib import Path

from asana_tasks import AsanaTask

PROTECTED_BRANCHES = {"main", "master", "dev"}


def _run(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def get_repo_root(start: Path | None = None) -> Path:
    cwd = start or Path.cwd()
    return Path(_run(["git", "rev-parse", "--show-toplevel"], cwd=cwd))


def get_current_branch(repo_root: Path) -> str:
    return _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root)


def checkout(repo_root: Path, branch: str) -> None:
    _run(["git", "checkout", branch], cwd=repo_root)


def create_and_checkout_branch(repo_root: Path, branch: str) -> None:
    _run(["git", "checkout", "-b", branch], cwd=repo_root)


def make_branch_name(task: AsanaTask, prefix: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", task.name.lower()).strip("-")[:40]
    gid_suffix = task.gid[-6:] if task.gid else "task"
    return f"{prefix}{slug}-{gid_suffix}"


def _has_changes(repo_root: Path) -> bool:
    _run(["git", "add", "-A"], cwd=repo_root)
    # everything is staged by the `git add -A` above, so a plain porcelain
    # status now reflects exactly what a commit would include
    status = _run(["git", "status", "--porcelain"], cwd=repo_root)
    return bool(status)


def commit_final(repo_root: Path, task: AsanaTask, summary: str) -> bool:
    """Commit the finished, cleanly-reviewed task. Returns False if nothing to commit."""
    if not _has_changes(repo_root):
        return False
    message = f"{task.name}\n\nAsana: {task.permalink_url}\n\n{summary.strip()}"
    _run(["git", "commit", "-m", message], cwd=repo_root)
    return True


def commit_wip(repo_root: Path, task: AsanaTask, reason: str) -> bool:
    """Commit whatever partial work exists so the branch is never left dirty
    (and so returning to the base branch never needs a destructive discard).
    Returns False if there was genuinely nothing to commit."""
    if not _has_changes(repo_root):
        return False
    message = f"night-coder: WIP - {reason}\n\n{task.name}\nAsana: {task.permalink_url}"
    _run(["git", "commit", "-m", message], cwd=repo_root)
    return True
