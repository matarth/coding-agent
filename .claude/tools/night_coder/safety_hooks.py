"""
PreToolUse Bash safety guardrails for NightCoder (see night_coder.py).

NightCoder runs fully unattended overnight, so these are the *hard*
enforcement layer - unlike prompted conventions (see prompts.py /
~/.claude/CLAUDE.md), a PreToolUse "deny" cannot be talked out of by the
agent. Two hook factories, following the exact PreToolUse callback shape
from the course's 1_single_agent/6_agent_with_hooks.py:

- build_implement_bash_guard(): denylist for the implement/refine step,
  plus branch-gating git commit so it can only ever land on a NightCoder
  branch, never on a protected one.
- build_review_bash_guard(): default-deny allowlist for the review step,
  which only ever needs read-only inspection commands.
"""
import re
import subprocess
from pathlib import Path

from claude_agent_sdk.types import HookContext, HookInput, HookJSONOutput

PROTECTED_BRANCHES = {"main", "master", "dev"}

# Unanchored `search` (not `match`) on purpose, so chained commands like
# `foo && git push` or `bar; rm -rf x` are still caught.
_DENY_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bgit\s+push\b"), "git push is forbidden - NightCoder commits locally only, never pushes"),
    (re.compile(r"\bgit\s+reset\s+--hard\b"), "git reset --hard is forbidden - destructive to the working tree"),
    (re.compile(r"\bgit\s+clean\b.*-[a-z]*f"), "git clean -f is forbidden - destructively deletes untracked files"),
    (re.compile(r"\bgit\s+branch\s+-D\b"), "git branch -D (force delete) is forbidden"),
    (re.compile(r"\bgit\s+tag\b"), "git tag is forbidden - never create tags unless explicitly asked"),
    (re.compile(r"\bgit\s+checkout\s+\.(\s|$)"), "git checkout . is forbidden - discards uncommitted changes"),
    (re.compile(r"\bgit\s+restore\s+\."), "git restore . is forbidden - discards uncommitted changes"),
    (re.compile(r"\brm\s+-rf\b"), "rm -rf is forbidden"),
    (re.compile(r"\bkubectl\b"), "kubectl is forbidden - never touch a Kubernetes cluster"),
    (re.compile(r"\bk9s\b"), "k9s is forbidden - never touch a Kubernetes cluster"),
]

_COMMIT_PATTERN = re.compile(r"\bgit\s+commit\b")

_REVIEW_ALLOWED_PREFIXES = (
    "git diff", "git log", "git show", "git status", "git blame", "git branch",
    "gh pr view", "gh pr diff", "cat ", "ls", "ls ", "grep ", "rg ", "find ",
    "head", "tail", "wc ",
)


def _deny(reason: str) -> HookJSONOutput:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def _allow(reason: str) -> HookJSONOutput:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": reason,
        }
    }


def _current_branch(repo_root: Path) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo_root, capture_output=True, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def build_implement_bash_guard(repo_root: Path, branch_prefix: str):
    """PreToolUse hook for the implement/refine step: denylist of
    destructive/forbidden commands, plus a branch-gated `git commit`."""

    async def hook(input_data: HookInput, tool_use_id: str | None, context: HookContext) -> HookJSONOutput:
        if input_data.get("tool_name") != "Bash":
            return _allow("non-Bash tool")

        command = (input_data.get("tool_input", {}) or {}).get("command", "")
        lowered = command.lower()

        for pattern, reason in _DENY_PATTERNS:
            if pattern.search(lowered):
                return _deny(reason)

        if _COMMIT_PATTERN.search(lowered):
            branch = _current_branch(repo_root)
            if branch is None:
                return _deny("could not determine current git branch - refusing to allow a commit")
            if branch in PROTECTED_BRANCHES or not branch.startswith(branch_prefix):
                return _deny(
                    f"git commit blocked: current branch '{branch}' is not a NightCoder "
                    f"branch (expected prefix '{branch_prefix}')"
                )

        return _allow("passed safety checks")

    return hook


def build_review_bash_guard():
    """PreToolUse hook for the review step: default-deny allowlist, since a
    reviewer only ever needs read-only inspection commands."""

    async def hook(input_data: HookInput, tool_use_id: str | None, context: HookContext) -> HookJSONOutput:
        if input_data.get("tool_name") != "Bash":
            return _allow("non-Bash tool")

        command = (input_data.get("tool_input", {}) or {}).get("command", "").strip().lower()
        if any(command.startswith(p) for p in _REVIEW_ALLOWED_PREFIXES):
            return _allow("read-only inspection command")
        return _deny(f"review step may only run read-only inspection commands; got: {command!r}")

    return hook
