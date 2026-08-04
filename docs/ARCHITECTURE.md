# System Architecture

## High-Level Overview

GraphCoder is a **multi-agent automated coding system** built on [LangGraph](https://python.langchain.com/docs/langgraph/). It orchestrates a directed graph of specialized AI agents — PM, Architect, Developer, Reviewer, and QA — to transform natural-language requirements into tested, reviewed code.

> **Status:** This is the target architecture. The current repository is a
> minimal skeleton: `src/api/cli.py` drives a single LangChain chain via
> `src/nodes/simple_chain.py`, and the full agent mesh (`StateGraph`, agents,
> data layer) is planned but not yet implemented.

```
┌──────────────┐
│  User Input  │  (natural-language requirement)
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────────────────────┐
│                  GraphCoder Core                      │
│                                                      │
│  ┌─────────┐   ┌───────────┐   ┌─────────────────┐  │
│  │  PM     │──▶│ Architect │──▶│   Developer     │  │
│  │ Agent   │   │  Agent    │   │    Agent        │  │
│  └────┬────┘   └─────┬─────┘   └────────┬────────┘  │
│       │              │                  │           │
│       ▼              ▼                  ▼           │
│  ┌──────────────────────────────────────────────────┐│
│  │                    State Graph                   ││
│  │   (TypedDict state shared across all agents)     ││
│  └──────────────────────┬───────────────────────────┘│
│                         │                            │
│              ┌──────────▼──────────┐                 │
│              │   Reviewer Agent   │                 │
│              └──────────┬──────────┘                 │
│                         │                            │
│              ┌──────────▼──────────┐                 │
│              │     QA Agent       │                 │
│              └──────────┬──────────┘                 │
│                         │                            │
│              ┌──────────▼──────────┐                 │
│              │  Loop-back? (yes)  │──────────────────┘│
│              └────────────────────┘                   │
└───────────────────────┬──────────────────────────────┘
                        │
                        ▼
                 ┌───────────────┐
                 │ Final Output  │
                 │ (code + docs) │
                 └───────────────┘
```

## Core Concepts

### State Graph

The central abstraction is a **LangGraph `StateGraph`** with a shared `TypedDict` state. Every node (agent) reads from and writes to the same state object, enabling clean data flow without explicit message passing. *(Target design — not yet implemented.)*

### Agents

Each agent is a LangGraph node function that:
1. Receives the current state
2. Builds an LLM call with role-specific prompt
3. Updates the state with its output

| Agent | Role | Input | Output |
|-------|------|-------|--------|
| PM | Requirements analysis, PRD drafting | User request | PRD document |
| Architect | System design, tech selection | PRD | Architecture spec |
| Developer | Code implementation | Architecture + Review feedback | Source code |
| Reviewer | Code review, feedback | Source code | Review comments |
| QA | Test design, quality gate | Code + Review | Test plan + Pass/Fail |

The agents above are specifications only; see [AGENTS.md](AGENTS.md). Their
modules do not exist yet and will be added under `src/agents/`.

### Looping

If QA fails, the graph loops back to the Developer with QA feedback. This continues until: *(Target design — not yet implemented.)*
- QA passes (max iterations enforced), or
- Max retries reached → escalation to user

---

## Directory Structure

```
GraphCoder/
├── main.py                  # Entry point → src.api.cli
├── config.py                # Env config (OPENAI_API_KEY, etc.)
├── requirements.txt         # Python dependencies
├── .env.example             # Env variable template
├── CHANGELOG.md             # Version history
├── CONTRIBUTING.md          # Contribution guide
├── SECURITY.md              # Security policy
├── LICENSE                  # MIT License
│
├── docs/                    # 📖 This documentation folder
│   ├── ARCHITECTURE.md      # This file
│   ├── AGENTS.md            # Agent specifications
│   ├── NODES.md             # Node implementation guide
│   ├── API_REFERENCE.md     # API docs
│   └── ROADMAP.md           # Project roadmap
│
├── .github/                 # Community templates & CI
│   ├── ISSUE_TEMPLATE/
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── workflows/ci.yml
│
├── src/
│   ├── __init__.py
│   ├── api/                 # Entry points
│   │   ├── __init__.py
│   │   └── cli.py           # CLI runner (implemented)
│   ├── nodes/               # LangGraph nodes
│   │   ├── __init__.py
│   │   └── simple_chain.py  # Placeholder chain node (implemented)
│   ├── utils/               # Utilities
│   │   ├── __init__.py
│   │   └── llm.py           # LLM factory (implemented)
│   ├── core/                # Planned: state schema, graph builder
│   │   └── __init__.py
│   ├── agents/              # Planned: PM / Architect / Developer / Reviewer / QA
│   │   └── __init__.py
│   ├── data/                # Planned: I/O layer
│   │   └── __init__.py
│   ├── prompts/             # Planned: prompt templates
│   │   └── __init__.py
│   └── tests/               # Planned: unit and integration tests
│       └── __init__.py
```

---

## Data Flow

The flow below is the target design. Today the CLI only invokes the simple
chain; the `GraphCore` state builder and agent loop are not implemented yet.

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│ User        │────▶│ CLI (cli.py) │────▶│ GraphCore   │
│ Requirement │     │              │     │ builds state│
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                 │
                    ┌────────────────────────────┘
                    ▼
              ┌─────────────┐
              │ Agent Loop  │
              │ PM → AD →   │
              │ Dev → Rev   │
              │ → QA        │
              └──────┬──────┘
                     │ pass / loop-back
                     ▼
              ┌─────────────┐
              │ Output      │
              │ - code/     │
              │ - docs/     │
              │ - test/     │
              └─────────────┘
```

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Orchestration | [LangGraph](https://python.langchain.com/docs/langgraph/) |
| LLM Interface | [LangChain](https://python.langchain.com/) + [langchain-openai](https://python.langchain.com/docs/integrations/chat/openai/) |
| LLM Provider | OpenAI-compatible API (configurable) |
| Configuration | [python-dotenv](https://saurabh-kumar.com/python-dotenv/) |
| Terminal UI | [Rich](https://rich.readthedocs.io/) |
| Linting | [Ruff](https://docs.astral.sh/ruff/) |

---

## Extension Points

To add a new agent:
1. Define agent logic in `src/agents/<name>.py`
2. Add corresponding node in `src/nodes/<name>_node.py`
3. Register in the graph builder (future `src/core/graph.py`)
4. Add prompt template in `src/prompts/<name>_prompt.py`

To add a new output format:
1. Implement serializer in `src/data/output.py`
2. Register in the output pipeline

To add a new LLM provider:
1. Extend `src/utils/llm.py:build_llm()` with a provider selector
2. Add provider-specific config keys to `config.py`
