# System Architecture (v2)

## High-Level Overview

GraphCoder v2 follows the **Codex App Server** and **Maka** patterns: all
functionality (agent loop, tools, permissions, storage) lives in an embeddable
**GraphCoder Runtime**; clients are thin UIs over transports. The CLI/TUI and
Electron desktop spawn `graphcoder app-server` (JSON-RPC over stdio, Item/Turn/
Thread primitives); the web keeps only a thin transport process (static + SSE).
The execution engine is self-built (multi-provider streaming + tool loop),
modeled on Hermes/Codex/Maka design patterns; the five-role pipeline is a
scheduler on top of it. SQLite is the single authority for sessions and the
append-only runtime event log.

```
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  Web (React) │   │ Desktop      │   │ TUI / CLI    │
│  HTTP+SSE    │   │ Electron IPC │   │ stdio JSON-RPC│
└──────┬───────┘   └──────┬───────┘   └──────┬───────┘
       │                  │                  │
       └─────────┐        │        ┌─────────┘
                 ▼        ▼        ▼
        ┌─────────────────────────────────────┐
        │        graphcoder app-server         │
        │  JSON-RPC lite over stdio (JSONL)    │
        │  Item / Turn / Thread primitives     │
        └──────────────────┬──────────────────┘
                           ▼
        ┌─────────────────────────────────────┐
        │        GraphCoder Runtime            │
        │  Agent Engine + Orchestrator         │
        │  Permission Engine + Event Bus       │
        └──────────────────┬──────────────────┘
                           ▼
        ┌─────────────────────────────────────┐
        │        SQLite 权威存储               │
        │  sessions / runtime_events / tasks  │
        │  settings / permissions / usage     │
        └─────────────────────────────────────┘
```

## Core Concepts

### Runtime (`src/runtime/`)

- `engine.py` — self-built Agent Engine: multi-provider streaming
  (`src/providers`), tool-calling loop, permission gating before execution,
  async approval pause/resume, event projection to the bus.
- `approvals.py` — async approval hub (pending futures + `approval/requested`).
- `permission.py` + `permission_bridge.py` — allow/ask/deny policy engine and
  the shared bridge used by the Hermes `pre_tool_call` plugin.
- `orchestrator.py` — PM → Architect → Developer → Reviewer → QA scheduler with
  QA loop-back (each role is a Hermes agent with a role system prompt).
- `threads.py` — thread lifecycle, turn execution, durable task records.
- `context.py` — workspace instructions (AGENTS.md) + tool-result shaping.

### App Server (`src/api/app_server.py`)

JSON-RPC lite over stdio (JSONL). Primitives: Item (typed, lifecycle
`item/started → item/delta → item/completed`), Turn (`turn/started/completed`),
Thread (`threads/create|list|get|rename|archive|fork|delete|prompt|resume`).
The server can initiate `approval/requested` and pause a turn until the client
responds — matching Codex App Server semantics.

### Storage (`src/storage/`)

SQLite (`runtime.sqlite`) is the single authority: sessions, append-only
`runtime_events`, tasks, settings, permissions and usage. `migrate.py` imports
legacy v1 JSON data once on first start.

### Permission enforcement

The Agent Engine evaluates the policy (command patterns for shell args, tool
names, directory prefixes) **before** tool execution. `allow` proceeds; `deny`
blocks the tool; `ask` emits `approval/requested` and awaits the client (or a
watchdog timeout denies). Decisions can be remembered (`always`/`session`) as
policy rules in SQLite.

## Extension Points

- **New surface**: speak the app-server JSON-RPC protocol (see
  [API_REFERENCE.md](API_REFERENCE.md)); the TUI, Desktop and Web transport are
  all examples.
- **New tool**: extend the Hermes toolset or add a plugin; permission rules
  apply generically via the `pre_tool_call` hook.
- **New agent/role**: add a role prompt in `src/agents/roles.py` and a step in
  `src/runtime/orchestrator.py`.
