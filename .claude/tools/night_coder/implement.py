"""
Implement + refine step for NightCoder (see night_coder.py).

Mirrors the course's 3_workflows/4_loop_workflow.py generate/refine shape:
a fresh isolated ClaudeSDKClient session per call, structured JSON output
(status: implemented|skipped) instead of free-text parsing, so the
orchestrator's loop/branching logic never has to guess at intent.
"""
from dataclasses import dataclass
from pathlib import Path

from asana_tasks import AsanaTask
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, HookMatcher, ResultMessage
from prompts import (
    IMPLEMENT_SYSTEM_PROMPT,
    REFINE_SYSTEM_PROMPT,
    build_implement_prompt,
    build_refine_prompt,
)

IMPLEMENT_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["implemented", "skipped"]},
        "summary": {"type": "string", "description": "1-4 sentences: what changed (or why skipped)."},
        "skip_reason": {"type": "string"},
    },
    "required": ["status", "summary"],
    "additionalProperties": False,
}


@dataclass
class ImplementResult:
    status: str  # "implemented" | "skipped"
    summary: str
    skip_reason: str = ""


async def _run(prompt: str, system_prompt: str, repo_root: Path, model: str, hook) -> ImplementResult:
    options = ClaudeAgentOptions(
        cwd=str(repo_root),
        allowed_tools=["Read", "Write", "Edit", "Bash", "Grep", "Glob"],
        system_prompt=system_prompt,
        hooks={"PreToolUse": [HookMatcher(matcher="Bash", hooks=[hook])]},
        output_format={"type": "json_schema", "schema": IMPLEMENT_RESULT_SCHEMA},
        model=model,
        setting_sources=["user"],
    )

    structured = None
    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)
        async for msg in client.receive_response():
            if isinstance(msg, ResultMessage) and msg.structured_output:
                structured = msg.structured_output

    if structured is None:
        return ImplementResult(
            status="skipped",
            summary="No structured result from the implement step.",
            skip_reason="Implement step ended without returning the required structured output.",
        )

    return ImplementResult(
        status=structured.get("status", "skipped"),
        summary=structured.get("summary", ""),
        skip_reason=structured.get("skip_reason", ""),
    )


async def run_implement_step(task: AsanaTask, repo_root: Path, model: str, hook) -> ImplementResult:
    return await _run(build_implement_prompt(task), IMPLEMENT_SYSTEM_PROMPT, repo_root, model, hook)


async def run_refine_step(
    task: AsanaTask, repo_root: Path, model: str, hook, mandatory_findings: str,
) -> ImplementResult:
    prompt = build_refine_prompt(task, mandatory_findings)
    return await _run(prompt, REFINE_SYSTEM_PROMPT, repo_root, model, hook)
