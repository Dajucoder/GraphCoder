# API Reference (v2)

## App Server Protocol

`graphcoder app-server` speaks **JSON-RPC lite over stdio** (JSONL): one request
per line in, one response per request plus notifications out.

### Primitives

- **Item** — typed atomic unit (`user_message`, `agent_message`, `tool_call`),
  lifecycle `item/started → item/delta* → item/completed`
- **Turn** — one unit of agent work per user input (`turn/started`,
  `turn/completed`)
- **Thread** — durable conversation (`threads/create|list|get|rename|archive|
  fork|delete`), persisted in SQLite

### Requests

| Method | Params | Result |
|---|---|---|
| `initialize` | — | `{protocolVersion, capabilities, defaults, workspace}` |
| `threads/create` | `{title?, parent_id?, branch_point?}` | thread |
| `threads/list` | `{include_archived?}` | `{threads}` |
| `threads/get` | `{thread_id}` | thread + events + tasks |
| `threads/rename` | `{thread_id, title}` | `{ok}` |
| `threads/archive` | `{thread_id, archived?}` | `{ok}` |
| `threads/fork` | `{thread_id, branch_point?}` | thread |
| `threads/delete` | `{thread_id}` | `{ok}` |
| `threads/prompt` | `{thread_id, content, mode: chat\|build, budgets?}` | `{task}` |
| `threads/resume` | `{task_id}` | `{task}` |
| `tasks/get` | `{task_id}` | task |
| `tasks/list` | `{thread_id?}` | `{tasks}` |
| `tasks/stop` | `{task_id}` | `{ok}` |
| `approvals/list` | — | `{approvals}` |
| `approvals/respond` | `{id, approved, scope?: once\|session\|always}` | `{ok}` |
| `models/list` | — | `{models, active}` |
| `settings/get` | — | settings + permissions |
| `settings/set` | `{options}` | `{ok}` |
| `permissions/list` | — | `{permissions}` |
| `permissions/add` | `{kind, pattern, action}` | `{ok}` |
| `permissions/remove` | `{id}` | `{ok}` |

### Notifications

```json
{"method": "item/started",    "params": {"thread_id": "...", "turn_id": "...", "item_id": "...", "kind": "tool_call", "name": "write_file", "arguments": {}}}
{"method": "item/delta",      "params": {"item_id": "...", "delta": "token text"}}
{"method": "item/completed",  "params": {"item_id": "...", "kind": "agent_message", "payload": {"content": "..."}}}
{"method": "approval/requested", "params": {"id": "ap-...", "kind": "tool", "target": "write_file", "reason": "..."}}
{"method": "turn/completed",  "params": {"turn_id": "...", "status": "completed|error", "content": "..."}}
```

## Web Transport (HTTP)

`python main.py serve` exposes a thin bridge (functionality lives in the
app-server child):

- `POST /api/v1/rpc` `{method, params}` → `{result}` or `{error}`
- `GET /api/v1/stream` — SSE of all notifications
- `GET /api/v1/health` — health check
- v1 REST adapters (`/api/v1/sessions*`, `/api/v1/providers`, `/api/v1/approvals/*`,
  `/api/v1/settings`) retained for transition
- `/` — serves the built React web app

## CLI

| Command | Description |
|---|---|
| `python main.py` | Fullscreen Textual TUI |
| `python main.py run "任务" --mode chat\|build` | Non-interactive exec (JSONL) |
| `python main.py serve --port 8000` | Web transport |
| `python main.py app-server` | Stdio JSON-RPC runtime server |
| `python main.py providers list\|add\|remove\|use\|test` | Provider management |
| `python main.py doctor` | Environment self-check |

## Python API

```python
from src.cli.rpc_client import RpcClient

client = RpcClient(workspace=Path.cwd())
await client.start()
info = await client.request("initialize")
thread = await client.request("threads/create", {"title": "x"})
task = await client.request("threads/prompt", {"thread_id": thread["id"], "content": "hi", "mode": "chat"})
```

## Environment Variables

| Variable | Description |
|---|---|
| `API_KEY` / `OPENAI_API_KEY` | API key (unified) |
| `API_BASE_URL` / `OPENAI_BASE_URL` | OpenAI-compatible base URL |
| `ACTIVE_PROVIDER` | Built-in provider id |
| `GRAPHCODER_HOME` | Data dir (default `~/.graphcoder`; `runtime.sqlite`) |
| `GRAPHCODER_RUNTIME_PYTHON` | Python for the app-server child |
| `GRAPHCODER_RUNTIME_DEBUG` | `1` → inherit runtime stderr |
