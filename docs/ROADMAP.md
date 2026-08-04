# Roadmap

## Vision

GraphCoder aims to become a **production-grade multi-agent coding platform** that transforms natural-language requirements into production-ready software through a transparent, traceable, and iterable agent pipeline.

## Current Status

As of August 2026, GraphCoder is a runnable minimal skeleton: modular `src/`
layout, environment-driven configuration, an LLM factory, a simple question
chain, and a CLI entry point. GitHub Actions CI runs lint, type checking,
tests, and a verified-secret scan.

---

## Release History

### v0.1.0 — Project Scaffold (Jul 2026)
- [x] Initial repository setup
- [x] Single-file LLM call chain
- [x] README with architecture overview

### v0.2.0 — Modular Skeleton (Aug 2026)
- [x] Reorganized into `src/` package structure
- [x] LLM factory (`build_llm`)
- [x] Simple chain node (placeholder)
- [x] CLI entry point
- [x] Configuration via `.env`
- [x] Open-source documentation (LICENSE, CHANGELOG, CONTRIBUTING, SECURITY)
- [x] GitHub community templates and CI

---

## Upcoming Releases

### v0.3.0 — State Graph Foundation *(target: Q4 2026)*

**Goal:** Build the first functional LangGraph state machine with the full agent mesh.

| Task | Priority | Status |
|------|----------|--------|
| Define `GraphState` TypedDict schema | P0 | ⬜ |
| Implement `GraphBuilder` in `src/core/graph.py` | P0 | ⬜ |
| Implement PM node (PRD generation) | P0 | ⬜ |
| Implement Architect node (system design) | P0 | ⬜ |
| Implement Developer node (code generation) | P0 | ⬜ |
| Implement Reviewer node (code review) | P0 | ⬜ |
| Implement QA node (test design + gate) | P0 | ⬜ |
| Wire up full graph with loop-back | P0 | ⬜ |
| Max iteration guard (prevent infinite loops) | P1 | ⬜ |

**Deliverable:** End-to-end pipeline from user input to reviewed code.

---

### v0.4.0 — Output & Persistence *(target: Q1 2027)*

**Goal:** Persist all outputs and support artifact management.

| Task | Priority | Status |
|------|----------|--------|
| Code artifact writer (`src/data/output.py`) | P0 | ⬜ |
| Markdown report generator (PRD, architecture, review) | P1 | ⬜ |
| Test file writer | P1 | ⬜ |
| Session logging (full trace of agent interactions) | P1 | ⬜ |
| JSON state export for debugging | P2 | ⬜ |
| File diff viewer for review feedback | P2 | ⬜ |

**Deliverable:** Full audit trail and downloadable artifacts.

---

### v0.5.0 — HTTP API Layer *(target: Q2 2027)*

**Goal:** Expose GraphCoder as a REST API for integration with IDEs and other tools.

| Task | Priority | Status |
|------|----------|--------|
| FastAPI server scaffold (`src/api/server.py`) | P0 | ⬜ |
| `/api/v1/run` — submit a coding task | P0 | ⬜ |
| `/api/v1/status/{task_id}` — poll progress | P0 | ⬜ |
| `/api/v1/result/{task_id}` — fetch result | P1 | ⬜ |
| WebSocket support for real-time streaming | P2 | ⬜ |
| Authentication (API key) | P1 | ⬜ |

**Deliverable:** REST API that IDEs and CI systems can call.

---

### v1.0.0 — Production Ready *(target: Q4 2027)*

**Goal:** First stable release with all core features.

| Task | Priority | Status |
|------|----------|--------|
| Comprehensive test suite (>80% coverage) | P0 | ⬜ |
| Performance benchmarks | P1 | ⬜ |
| Docker deployment | P1 | ⬜ |
| Multi-provider LLM support | P1 | ⬜ |
| Plugin system for custom agents | P2 | ⬜ |
| Documentation site (docsite) | P1 | ⬜ |
| PyPI package release | P0 | ⬜ |

**Deliverable:** Stable v1.0.0 tagged release on PyPI.

---

## Feature Backlog (Post-v1.0)

- **IDE Integration:** VS Code / JetBrains plugin for in-editor GraphCoder
- **Parallel Agents:** Run multiple candidate implementations in parallel, pick the best
- **Memory Layer:** Long-term memory of past projects for better context
- **Multi-language Support:** Beyond Python — TypeScript, Rust, Go
- **Self-Improvement:** Agents that learn from past reviews and improve
- **Human-in-the-Loop:** Approval gates at key pipeline stages
- **Benchmark Suite:** Standardized coding benchmarks (SWE-bench, HumanEval, etc.)

---

## Contributing to the Roadmap

Feature requests and roadmap discussions are welcome! Please:
1. Open a [GitHub Discussion](https://github.com/Dajucoder/GraphCoder/discussions)
2. Describe the use case and expected behavior
3. Community votes will help prioritize

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contribution guide.
