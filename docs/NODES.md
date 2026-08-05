# Node Implementation Guide

This document explains how to implement LangGraph nodes for GraphCoder.

> **Status:** Implemented. The production agent mesh lives in `src/core/graph.py`
> (PM → Architect → Developer → Reviewer → QA with loop-back) plus the chat
> tool-loop runner in `src/core/chat.py`. The examples below describe the
> implementation patterns used.

## What is a Node?

In LangGraph, a **node** is a Python function that:
1. Receives the current graph state
2. Performs some computation (typically an LLM call)
3. Returns an updated state

```python
from typing import TypedDict
from src.utils.llm import build_llm


class GraphState(TypedDict):
    task: str
    result: str


def my_node(state: GraphState) -> GraphState:
    llm = build_llm()
    response = llm.invoke(f"Process: {state['task']}")
    return {**state, "result": response.content}
```

## Node Structure

Every node should follow this pattern:

1. **Import `build_llm` from `src.utils.llm`** — never instantiate `ChatOpenAI` directly
2. **Accept a `TypedDict` state** — match the graph's state schema
3. **Return the same `TypedDict`** — spread existing state and update changed fields
4. **Keep side effects minimal** — nodes should be pure functions of state

## Registering a Node

When the graph builder is added (planned in `src/core/graph.py`), nodes will be registered like this:

```python
from langgraph.graph import StateGraph, END
from src.core.state import GraphState
from src.agents.developer import run_developer
from src.agents.qa import run_qa

builder = StateGraph(GraphState)
builder.add_node("developer", run_developer)
builder.add_node("qa", run_qa)
builder.add_edge("developer", "qa")
builder.add_edge("qa", END)
graph = builder.compile()
```

## Error Handling

Nodes should catch and handle errors gracefully:

```python
def safe_node(state: GraphState) -> GraphState:
    try:
        result = do_work(state)
        return {**state, "result": result, "error": None}
    except Exception as e:
        return {**state, "error": str(e), "result": None}
```

## Testing Nodes

Each node should have a corresponding test in `src/tests/`:

```python
# src/tests/test_developer_node.py
import pytest
from src.agents.developer import run_developer


def test_developer_basic():
    state = {"architecture": "...", "review_feedback": None}
    result = run_developer(state)
    assert "code_files" in result
    assert len(result["code_files"]) > 0
```

---

## Current Nodes

| Node | File | Status |
|------|------|--------|
| Simple Chain | `src/nodes/simple_chain.py` | Placeholder — validates LLM call chain |
| PM | `src/agents/pm.py` | Planned |
| Architect | `src/agents/architect.py` | Planned |
| Developer | `src/agents/developer.py` | Planned |
| Reviewer | `src/agents/reviewer.py` | Planned |
| QA | `src/agents/qa.py` | Planned |
