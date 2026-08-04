# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GraphCoder (图灵智开) is a multi-agent automated coding system built on LangGraph. It orchestrates a graph of specialized agents — PM, Architect, Developer, Reviewer, QA — to generate software from user requirements through a traceable, loopable pipeline.

Currently a minimal skeleton validating the LLM call chain; full multi-agent graph will be built incrementally in `src/agents/` and `src/nodes/`.

## Commands

```bash
# Activate environment (conda, required for running)
conda activate graphcoder

# Install dependencies
pip install -r requirements.txt

# Run the app
python main.py

# Lint (ruff)
ruff check src/

# Type check (mypy)
mypy src/

# Tests (skips when no test files exist)
pytest src/tests/
```

## Architecture

- **Entry:** `main.py` delegates to `src/api/cli.py`, which reads a topic from stdin and invokes a LangChain chain.
- **LLM factory:** `src/utils/llm.py:build_llm()` creates a `ChatOpenAI` instance. All LLM consumers should call this factory, not instantiate `ChatOpenAI` directly.
- **Config:** `config.py` reads env vars via `python-dotenv`. Active vars: `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `MODEL_NAME`, `TEMPERATURE`; `MAX_TOKENS` is loaded but not yet consumed by the LLM factory. Add new env-driven settings here.
- **Nodes:** `src/nodes/` holds LangGraph node implementations. Currently only `simple_chain.py` exists as a placeholder.
- **Agents / Prompts / Data / Core / Tests:** package directories ready for expansion — no concrete implementations yet.
- **Package import style:** absolute imports from `src.*` (e.g. `from src.utils.llm import build_llm`). The project is run from the repo root.
- **CI:** `.github/workflows/ci.yml` runs ruff, mypy, pytest, and a truffleHog secret scan on pushes and pull requests.

## Conventions

- Target Python 3.13+.
- Use absolute `src.*` imports; do not rely on `sys.path` manipulation.
- New agent/node code lives in `src/agents/` or `src/nodes/`, not at the top level.
- `.env` is gitignored; copy `.env.example` and fill in keys.

## Docs

- Architecture: `docs/ARCHITECTURE.md`
- Agent specs: `docs/AGENTS.md`
- Node guide: `docs/NODES.md`
- API reference: `docs/API_REFERENCE.md`
- Roadmap: `docs/ROADMAP.md`
