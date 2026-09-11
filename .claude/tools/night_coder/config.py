"""
CLI configuration for NightCoder (see night_coder.py).

All defaults are deliberately conservative (small --max-tasks, hard
wall-clock and per-task budgets) since this runs fully unattended - see
README.md "NightCoder" section for the required --dry-run warm-up run.
"""
import argparse
from dataclasses import dataclass


@dataclass
class NightCoderArgs:
    asana_project: str
    tag: str | None
    max_tasks: int
    max_review_iterations: int
    max_hours: float
    max_minutes_per_task: int
    model: str
    branch_prefix: str
    dry_run: bool


def parse_args(argv: list[str] | None = None) -> NightCoderArgs:
    parser = argparse.ArgumentParser(
        description=(
            "Pull incomplete Asana tasks assigned to you and, for each one, run "
            "branch -> implement -> code review -> commit-if-clean (else refine and "
            "re-review). Never pushes, never opens an MR - review PROJECT/.claude/"
            "tools/night_coder/reports/ in the morning."
        ),
    )
    parser.add_argument(
        "--asana-project",
        required=True,
        help="GID of the Asana project to pull incomplete tasks assigned to you from.",
    )
    parser.add_argument(
        "--tag",
        default=None,
        help="Optional extra filter: only tasks that also have this Asana tag.",
    )
    parser.add_argument(
        "--max-tasks",
        type=int,
        default=5,
        help="Maximum number of tasks to process this run (default: 5).",
    )
    parser.add_argument(
        "--max-review-iterations",
        type=int,
        default=3,
        help="Max implement<->review loops per task before giving up (default: 3).",
    )
    parser.add_argument(
        "--max-hours",
        type=float,
        default=8.0,
        help="Wall-clock budget for the whole run, checked between tasks (default: 8.0).",
    )
    parser.add_argument(
        "--max-minutes-per-task",
        type=int,
        default=45,
        help="Hard timeout for a single implement/refine step (default: 45).",
    )
    parser.add_argument(
        "--model",
        default="sonnet",
        help="Model alias to use for every step (default: sonnet).",
    )
    parser.add_argument(
        "--branch-prefix",
        default="night-coder/",
        help="Prefix for created branch names (default: night-coder/).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Only fetch and print the matching Asana task list - no git/code changes. "
            "Run this once, live, before leaving your desk (see README)."
        ),
    )

    ns = parser.parse_args(argv)
    return NightCoderArgs(
        asana_project=ns.asana_project,
        tag=ns.tag,
        max_tasks=ns.max_tasks,
        max_review_iterations=ns.max_review_iterations,
        max_hours=ns.max_hours,
        max_minutes_per_task=ns.max_minutes_per_task,
        model=ns.model,
        branch_prefix=ns.branch_prefix,
        dry_run=ns.dry_run,
    )
