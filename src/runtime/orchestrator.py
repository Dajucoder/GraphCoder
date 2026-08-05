"""Multi-agent build pipeline as a scheduler over Agent Engine runs.

Each role drives the self-built engine with a role system prompt; the scheduler
feeds each role the previous role's output and loops back on QA failure
(Maka: graph is a schedule, not a second runtime).
"""

from __future__ import annotations

import re
from typing import Any

from src.agents.roles import (
    ARCHITECT_SYSTEM,
    DEVELOPER_SYSTEM,
    PM_SYSTEM,
    QA_SYSTEM,
    REVIEWER_SYSTEM,
)
from src.runtime.engine import AgentEngine


async def run_build_pipeline(
    adapter: AgentEngine,
    *,
    thread_id: str,
    turn_id: str,
    request: str,
    workspace_instructions: str = "",
    max_attempts: int = 3,
) -> dict[str, Any]:
    """Run PM → Architect → Developer → Reviewer → QA with loop-back."""
    context = f"# 用户需求\n{request}"
    if workspace_instructions:
        context += f"\n\n# 工作区说明\n{workspace_instructions}"

    states: dict[str, str] = {}
    qa_pass = False
    attempts = 0
    while attempts < max_attempts:
        attempts += 1
        if attempts > 1:
            context += (
                f"\n\n# 上一轮审查意见（必须修复）\n{states.get('review', '')}\n\n"
                f"# 上一轮 QA 意见\n{states.get('qa_result', '')}"
            )

        prd = await adapter.run(
            thread_id=thread_id,
            turn_id=turn_id,
            user_message=context,
            role_prompt=PM_SYSTEM,
            role="pm",
        )
        states["prd"] = prd.text

        arch = await adapter.run(
            thread_id=thread_id,
            turn_id=turn_id,
            user_message=f"# 用户需求\n{request}\n\n# PRD\n{states['prd']}",
            role_prompt=ARCHITECT_SYSTEM,
            role="architect",
        )
        states["architecture"] = arch.text

        dev_context = (
            f"# 用户需求\n{request}\n\n# 架构设计\n{states['architecture']}"
            + (f"\n\n# 上一轮反馈\n{context.split('# 上一轮审查意见')[1]}" if attempts > 1 else "")
        )
        dev = await adapter.run(
            thread_id=thread_id,
            turn_id=turn_id,
            user_message=dev_context,
            role_prompt=DEVELOPER_SYSTEM,
            role="developer",
        )
        states["implementation"] = dev.text

        review = await adapter.run(
            thread_id=thread_id,
            turn_id=turn_id,
            user_message=f"# 实现\n{states['implementation']}",
            role_prompt=REVIEWER_SYSTEM,
            role="reviewer",
        )
        states["review"] = review.text

        qa = await adapter.run(
            thread_id=thread_id,
            turn_id=turn_id,
            user_message=f"# 实现\n{states['implementation']}\n\n# 审查意见\n{states['review']}",
            role_prompt=QA_SYSTEM,
            role="qa",
        )
        states["qa_result"] = qa.text
        match = re.search(r"结论[:：]\s*(PASS|FAIL)", qa.text.upper())
        qa_pass = match.group(1) == "PASS" if match else "FAIL" not in qa.text.upper()
        if qa_pass:
            break

    return {
        "prd": states.get("prd", ""),
        "architecture": states.get("architecture", ""),
        "implementation": states.get("implementation", ""),
        "review": states.get("review", ""),
        "qa_result": states.get("qa_result", ""),
        "qa_pass": qa_pass,
        "attempts": attempts,
    }
