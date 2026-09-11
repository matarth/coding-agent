#!/usr/bin/env python3
"""
NightCoder: unattended overnight coding agent.

Pulls incomplete Asana tasks assigned to you from a given project and, for
each one, runs: new branch -> implement -> code review (reusing the
existing `code-review` skill) -> commit if clean, otherwise back to
implementation with the reviewer's feedback. Commits locally only - never
pushes, never opens an MR. Writes a summary to
reports/night_coder_output_<date>.md for you to review in the morning.

IMPORTANT: run once, live, with --dry-run before you leave your desk (see
README.md "NightCoder" section) - overnight Asana OAuth refresh can fail
silently, and this surfaces that immediately instead of at 2am.

Usage:
    python3 night_coder.py --asana-project <GID> [options]
    python3 night_coder.py --dry-run --asana-project <GID>

Run from inside the target repo - it self-detects the repo root via
`git rev-parse --show-toplevel` and branches from whatever branch is
currently checked out when it starts.
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import anyio

import config
import git_ops
import implement
import report
import review
import safety_hooks
from asana_tasks import AsanaTask, fetch_tasks
from config import NightCoderArgs
from report import RunMeta, TaskOutcome


async def run_task_cycle(
    task: AsanaTask, branch_name: str, base_branch: str, repo_root: Path, args: NightCoderArgs,
) -> TaskOutcome:
    implement_hook = safety_hooks.build_implement_bash_guard(repo_root, args.branch_prefix)
    review_hook = safety_hooks.build_review_bash_guard()

    try:
        with anyio.fail_after(args.max_minutes_per_task * 60):
            result = await implement.run_implement_step(task, repo_root, args.model, implement_hook)
    except TimeoutError:
        git_ops.commit_wip(repo_root, task, "implement step timed out")
        return TaskOutcome.needs_attention(task, branch_name, 0, "", reason="implement step timed out")

    if result.status == "skipped":
        git_ops.commit_wip(repo_root, task, "implement step reported skipped")
        return TaskOutcome.skipped(task, branch_name, result.skip_reason or result.summary)

    review_text = ""
    for iteration in range(1, args.max_review_iterations + 1):
        review_text = await review.run_review_step(
            repo_root, base_branch, branch_name, task, args.model, review_hook,
        )

        if review.mandatory_section_is_empty(review_text):
            git_ops.commit_final(repo_root, task, result.summary)
            return TaskOutcome.completed(task, branch_name, iteration, result.summary)

        if iteration == args.max_review_iterations:
            break

        result = await implement.run_refine_step(
            task, repo_root, args.model, implement_hook, review.extract_mandatory(review_text),
        )

    git_ops.commit_wip(repo_root, task, "max review iterations reached")
    return TaskOutcome.needs_attention(
        task, branch_name, args.max_review_iterations, review.extract_mandatory(review_text),
    )


async def main() -> None:
    args = config.parse_args()
    repo_root = git_ops.get_repo_root()
    base_branch = git_ops.get_current_branch(repo_root)
    run_started = datetime.now()
    deadline = run_started + timedelta(hours=args.max_hours)

    print(f"NightCoder: fetching Asana tasks from project {args.asana_project}...")
    tasks = await fetch_tasks(args.asana_project, args.tag, args.max_tasks, repo_root)

    if not tasks:
        print("No matching Asana tasks found (assigned to you, incomplete"
              + (f", tag={args.tag}" if args.tag else "") + "). Exiting.")
        return

    if args.dry_run:
        print(f"{len(tasks)} matching task(s):")
        for t in tasks:
            print(f"- {t.name} ({t.permalink_url})")
        return

    outcomes: list[TaskOutcome] = []
    for task in tasks:
        if datetime.now() >= deadline:
            print(f"Time budget ({args.max_hours}h) exhausted - skipping remaining tasks.")
            outcomes.append(TaskOutcome.time_budget_exhausted(task))
            continue

        print(f"\n=== {task.name} ===")
        git_ops.checkout(repo_root, base_branch)
        branch_name = git_ops.make_branch_name(task, args.branch_prefix)
        git_ops.create_and_checkout_branch(repo_root, branch_name)
        print(f"Branch: {branch_name}")

        outcome = await run_task_cycle(task, branch_name, base_branch, repo_root, args)
        print(f"Status: {outcome.status}")
        outcomes.append(outcome)

        git_ops.checkout(repo_root, base_branch)

    run_meta = RunMeta(
        started=run_started, finished=datetime.now(), base_branch=base_branch,
        args=args, tasks_fetched=len(tasks), outcomes=outcomes,
    )
    path = report.report_path(repo_root, run_started)
    report.write_report(run_meta, path)
    print(f"\nReport written to {path}")


if __name__ == "__main__":
    anyio.run(main)
