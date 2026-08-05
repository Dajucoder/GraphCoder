"""LangGraph state schema."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class GraphState(TypedDict, total=False):
    """Shared state flowing through the agent mesh."""

    request: str
    session_id: str
    task_id: str
    prd: str
    architecture: str
    implementation: str
    review: str
    test_plan: str
    qa_result: str
    qa_pass: bool
    attempts: int
    max_attempts: int
    events: Annotated[list[dict[str, Any]], operator.add]
    history: list[dict[str, Any]]
