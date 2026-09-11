"""
night_coder_output_<date>.md report writer (see night_coder.py).

Written to reports/ inside this tool's own folder - self-contained like
db_readonly's .env/log file, gitignored, never auto-committed by
NightCoder itself (it's run metadata for the user to read, not part of
any single task's branch).
"""
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from asana_tasks import AsanaTask
from config import NightCoderArgs

REPORTS_DIR = Path(__file__).resolve().parent / "reports"


@dataclass
class TaskOutcome:
    task: AsanaTask
    branch_name: str
    status: str  # "completed" | "needs_attention" | "skipped" | "time_budget_exhausted"
    review_iterations: int = 0
    summary: str = ""
    mandatory_findings: str = ""
    reason: str = ""

    @classmethod
    def completed(cls, task: AsanaTask, branch_name: str, iterations: int, summary: str) -> "TaskOutcome":
        return cls(task, branch_name, "completed", review_iterations=iterations, summary=summary)

    @classmethod
    def needs_attention(
        cls, task: AsanaTask, branch_name: str, iterations: int, mandatory_findings: str, reason: str = "",
    ) -> "TaskOutcome":
        return cls(
            task, branch_name, "needs_attention",
            review_iterations=iterations, mandatory_findings=mandatory_findings, reason=reason,
        )

    @classmethod
    def skipped(cls, task: AsanaTask, branch_name: str, reason: str) -> "TaskOutcome":
        return cls(task, branch_name, "skipped", reason=reason)

    @classmethod
    def time_budget_exhausted(cls, task: AsanaTask) -> "TaskOutcome":
        return cls(task, "", "time_budget_exhausted")


@dataclass
class RunMeta:
    started: datetime
    finished: datetime
    base_branch: str
    args: NightCoderArgs
    tasks_fetched: int
    outcomes: list[TaskOutcome] = field(default_factory=list)


def report_path(repo_root: Path, run_started: datetime) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return REPORTS_DIR / f"night_coder_output_{run_started.strftime('%Y-%m-%d')}.md"


def _task_header(index: int, outcome: TaskOutcome) -> str:
    return f"### {index}. {outcome.task.name}\n- Asana: {outcome.task.permalink_url}"


def _render_completed(outcomes: list[TaskOutcome]) -> str:
    if not outcomes:
        return "(none)\n"
    parts = []
    for i, o in enumerate(outcomes, 1):
        parts.append(
            f"{_task_header(i, o)}\n"
            f"- Branch: `{o.branch_name}`\n"
            f"- Review iterations: {o.review_iterations}\n"
            f"- Summary: {o.summary}\n"
            f"- **Not pushed — review the diff, then push and open the MR yourself.**\n"
        )
    return "\n".join(parts)


def _render_needs_attention(outcomes: list[TaskOutcome]) -> str:
    if not outcomes:
        return "(none)\n"
    parts = []
    for i, o in enumerate(outcomes, 1):
        findings = o.mandatory_findings or o.reason or "(no details captured)"
        parts.append(
            f"{_task_header(i, o)}\n"
            f"- Branch: `{o.branch_name}` (contains a WIP commit)\n"
            f"- Review iterations: {o.review_iterations}\n"
            f"- Last reviewer Mandatory findings:\n> {findings}\n"
        )
    return "\n".join(parts)


def _render_skipped(outcomes: list[TaskOutcome]) -> str:
    if not outcomes:
        return "(none)\n"
    parts = []
    for i, o in enumerate(outcomes, 1):
        parts.append(f"{_task_header(i, o)}\n- Reason: {o.reason or '(no reason captured)'}\n")
    return "\n".join(parts)


def _render_not_started(outcomes: list[TaskOutcome]) -> str:
    if not outcomes:
        return "(none)\n"
    parts = []
    for i, o in enumerate(outcomes, 1):
        parts.append(f"### {i}. {o.task.name}\n- Asana: {o.task.permalink_url}\n")
    return "\n".join(parts)


def write_report(run_meta: RunMeta, path: Path) -> None:
    completed = [o for o in run_meta.outcomes if o.status == "completed"]
    needs_attention = [o for o in run_meta.outcomes if o.status == "needs_attention"]
    skipped = [o for o in run_meta.outcomes if o.status == "skipped"]
    not_started = [o for o in run_meta.outcomes if o.status == "time_budget_exhausted"]

    args = run_meta.args
    content = f"""# NightCoder Run Report — {run_meta.started.strftime('%Y-%m-%d')}

**Started:** {run_meta.started.strftime('%Y-%m-%d %H:%M')}  **Finished:** {run_meta.finished.strftime('%Y-%m-%d %H:%M')}
**Base branch:** `{run_meta.base_branch}`
**Asana project:** {args.asana_project}  **Tag filter:** {args.tag or "none"}
**Params:** max-tasks={args.max_tasks}, max-review-iterations={args.max_review_iterations}, max-hours={args.max_hours}, max-minutes-per-task={args.max_minutes_per_task}, model={args.model}
**Tasks fetched:** {run_meta.tasks_fetched}  **Completed:** {len(completed)}  **Needs attention:** {len(needs_attention)}  **Skipped:** {len(skipped)}  **Not started:** {len(not_started)}

## Completed

{_render_completed(completed)}
## Needs attention (not cleanly reviewed)

{_render_needs_attention(needs_attention)}
## Skipped

{_render_skipped(skipped)}
## Not started (time budget exhausted)

{_render_not_started(not_started)}"""

    path.write_text(content, encoding="utf-8")
