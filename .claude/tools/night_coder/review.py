"""
Code review step for NightCoder (see night_coder.py).

Reuses the existing PROJECT/.claude/skills/code-review/SKILL.md verbatim
as the reviewer's system prompt - single source of truth, no forked/
duplicated review checklist. Pass/fail is decided by parsing that skill's
own "## Mandatory" section rather than inventing a redundant custom
verdict line, since the skill already documents "empty section is a
valid outcome" as its own contract.
"""
import re
from pathlib import Path

from asana_tasks import AsanaTask
from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient, HookMatcher, TextBlock
from prompts import build_review_prompt

_FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
_MANDATORY_SECTION_RE = re.compile(r"^##\s+Mandatory\s*\n(.*?)(?=^##\s+\S|\Z)", re.DOTALL | re.MULTILINE)
_EMPTY_TOKENS = {"", "none", "none.", "n/a", "no issues", "no issues.", "no findings", "no findings.", "-"}

# night_coder.py -> tools/ -> .claude/ -> skills/code-review/SKILL.md
_SKILL_PATH = Path(__file__).resolve().parents[2] / "skills" / "code-review" / "SKILL.md"


def load_code_review_skill_prompt() -> str:
    text = _SKILL_PATH.read_text(encoding="utf-8")
    return _FRONTMATTER_RE.sub("", text, count=1).strip()


def extract_mandatory(review_text: str) -> str:
    m = _MANDATORY_SECTION_RE.search(review_text)
    return m.group(1).strip() if m else ""


def mandatory_section_is_empty(review_text: str) -> bool:
    return extract_mandatory(review_text).strip().lower() in _EMPTY_TOKENS


async def run_review_step(
    repo_root: Path, base_branch: str, branch_name: str, task: AsanaTask, model: str, hook,
) -> str:
    options = ClaudeAgentOptions(
        cwd=str(repo_root),
        allowed_tools=["Read", "Grep", "Glob", "Bash"],
        system_prompt=load_code_review_skill_prompt(),
        hooks={"PreToolUse": [HookMatcher(matcher="Bash", hooks=[hook])]},
        model=model,
        setting_sources=["user"],
    )

    prompt = build_review_prompt(task, base_branch, branch_name)
    parts: list[str] = []
    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        parts.append(block.text)

    return "\n".join(parts)
