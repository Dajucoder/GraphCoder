# CHANGELOG

All notable changes to GraphCoder will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] — 2025-08-04

### Added
- **Package restructuring:** reorganized codebase into modular `src/` layout:
  - `src/core/` — state schema and graph builder
  - `src/agents/` — agent definitions (PM, Architect, Developer, Reviewer, QA)
  - `src/nodes/` — LangGraph node implementations
  - `src/data/` — I/O layer for requirements and artifacts
  - `src/api/` — CLI entry point and future HTTP server
  - `src/prompts/` — reusable prompt templates
  - `src/utils/` — helper utilities (LLM factory, logging)
  - `src/tests/` — unit and integration test suite
- **LLM factory:** `src/utils/llm.py:build_llm()` — centralized, config-driven `ChatOpenAI` factory
- **Simple chain node:** `src/nodes/simple_chain.py` — minimal LLM call chain for validating the pipeline
- **CLI entry point:** `src/api/cli.py` — stdin-driven interactive prompt
- **Configuration module:** `config.py` — env-var loading via `python-dotenv`
- **Environment template:** `.env.example` with all supported variables

### Changed
- Main entry (`main.py`) now delegates to `src.api.cli.main()`

### Planned
- Full LangGraph state machine with 5-agent mesh
- Multi-round iteration and loop-back on QA failure
- Output artifact persistence (code, docs, test reports)
- REST API layer

---

## [0.1.0] — 2025-07-28

### Added
- Initial project scaffold
- Single-file LLM call chain via LangChain
- README with architecture overview
