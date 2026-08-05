"""Build pipeline scheduler tests with a fake agent engine."""

from __future__ import annotations

import asyncio

from src.runtime.engine import TurnResult
from src.runtime.orchestrator import run_build_pipeline


class FakeAdapter:
    def __init__(self, qa_text: str) -> None:
        self.qa_text = qa_text
        self.calls: list[str] = []

    async def run(self, **kwargs) -> TurnResult:
        role = kwargs.get("role", "assistant")
        self.calls.append(role)
        if role == "qa":
            return TurnResult(self.qa_text, [], ok=True)
        return TurnResult(f"[{role}] 输出", [], ok=True)


def _run(qa_text: str, max_attempts: int = 3) -> dict:
    async def run() -> dict:
        adapter = FakeAdapter(qa_text)
        result = await run_build_pipeline(
            adapter,  # type: ignore[arg-type]
            thread_id="t",
            turn_id="turn",
            request="做计算器",
            max_attempts=max_attempts,
        )
        return result

    return asyncio.run(run())


def test_pipeline_passes_on_first_attempt() -> None:
    result = _run("## 结论：PASS")
    assert result["qa_pass"] is True
    assert result["attempts"] == 1
    assert result["prd"] and result["architecture"] and result["implementation"]


def test_pipeline_loops_back_on_fail() -> None:
    result = _run("## 结论：FAIL", max_attempts=2)
    assert result["qa_pass"] is False
    assert result["attempts"] == 2
