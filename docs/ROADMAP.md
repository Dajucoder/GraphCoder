# Roadmap

## Vision

GraphCoder aims to become a **production-grade multi-agent coding platform** that transforms natural-language requirements into production-ready software through a transparent, traceable, and iterable agent pipeline.

## Current Status

As of August 2026, GraphCoder v1.0.0 is a full-featured multi-agent coding
platform: multi-provider LLM access, a LangGraph agent mesh with QA loop-back,
agent tools (files/shell/web/MCP), a FastAPI server with REST/SSE/WebSocket
streaming, a React + TypeScript web client, an Electron desktop app, and a Rich
CLI. GitHub Actions CI runs lint, type checking, tests, and a verified-secret
scan.

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

### v1.0.0 — Multi-Agent Platform (2026-08-05)

**Goal:** Build the first functional LangGraph state machine with the full agent mesh.

| Task | Priority | Status |
|------|----------|--------|
| Define `GraphState` TypedDict schema | P0 | ✅ |
| Implement `GraphBuilder` in `src/core/graph.py` | P0 | ✅ |
| Implement PM node (PRD generation) | P0 | ✅ |
| Implement Architect node (system design) | P0 | ✅ |
| Implement Developer node (code generation) | P0 | ✅ |
| Implement Reviewer node (code review) | P0 | ✅ |
| Implement QA node (test design + gate) | P0 | ✅ |
| Wire up full graph with loop-back | P0 | ✅ |
| Max iteration guard (prevent infinite loops) | P1 | ✅ |
| Multi-provider LLM support | P1 | ✅ |
| Web (React + TS) client | P0 | ✅ |
| Desktop (Electron) client | P0 | ✅ |
| Rich CLI (chat/run/serve/providers) | P0 | ✅ |
| REST + SSE + WebSocket streaming API | P0 | ✅ |
| Command approval (human-in-the-loop) | P1 | ✅ |
| MCP client extension | P2 | ✅ |

**Deliverable:** End-to-end pipeline from user input to reviewed code.

---

### v0.4.0 — Output & Persistence

**Goal:** Persist all outputs and support artifact management.

| Task | Priority | Status |
|------|----------|--------|
| Code artifact writer (`src/data/output.py`) | P0 | ✅ |
| Markdown report generator (PRD, architecture, review) | P1 | ⬜ |
| Test file writer | P1 | ⬜ |
| Session logging (full trace of agent interactions) | P1 | ✅ |
| JSON state export for debugging | P2 | ✅ |
| File diff viewer for review feedback | P2 | ⬜ |

**Deliverable:** Full audit trail and downloadable artifacts.

---

### v0.5.0 — HTTP API Layer

**Goal:** Expose GraphCoder as a REST API for integration with IDEs and other tools.

| Task | Priority | Status |
|------|----------|--------|
| FastAPI server scaffold (`src/api/server.py`) | P0 | ✅ |
| `/api/v1/sessions/{id}/messages` — submit a task | P0 | ✅ |
| `/api/v1/tasks/{id}` — task status & events | P0 | ✅ |
| SSE + WebSocket streaming | P0 | ✅ |
| Command approval API | P1 | ✅ |

**Deliverable:** REST API that IDEs and CI systems can call.

---

### v1.1.0 — Production Hardening *(target: Q4 2026)*

**Goal:** First stable release with all core features.

| Task | Priority | Status |
|------|----------|--------|
| Comprehensive test suite (>80% coverage) | P0 | ⬜ |
| Performance benchmarks | P1 | ⬜ |
| Docker deployment | P1 | ⬜ |
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
