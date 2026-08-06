# API 参考

GraphCoder app-server 使用基于 stdin/stdout 的 JSON-RPC lite 协议。每一行是一个完整 JSON
对象，因此也称 JSONL 协议。Desktop、TUI、非交互 CLI 和 Web bridge 均复用该协议。

当前协议版本为 `1.0`。它借用了 JSON-RPC 的 request/result/error 结构，但没有
`jsonrpc: "2.0"` 字段，不应直接假设通用 JSON-RPC 客户端可以无适配接入。

## 启动

源码模式：

```bash
python main.py app-server --home ~/.graphcoder
```

也可以直接运行：

```bash
python -m src.api.app_server --workspace /path/to/project --home ~/.graphcoder
```

app-server 就绪后首先输出：

```json
{"method":"server/ready","params":{"workspace":"/path/to/project","protocol":"1.0"}}
```

stdout 只用于协议帧，日志写入 stderr。嵌入客户端必须持续读取 stdout，否则大量流式通知
可能填满子进程管道。

## 帧格式

请求：

```json
{"id":1,"method":"initialize","params":{}}
```

成功响应：

```json
{"id":1,"result":{"protocolVersion":"1.0"}}
```

错误响应：

```json
{"id":1,"error":{"code":-32602,"message":"'任务不存在'"}}
```

通知没有 `id`：

```json
{"method":"item/delta","params":{"thread_id":"s_x","turn_id":"t_x","item_id":"item-x","delta":"..."}}
```

## 错误码

| Code | 含义 |
|---|---|
| `-32601` | 方法不存在 |
| `-32602` | 缺少参数、资源不存在或输入不满足方法要求 |
| `-32000` | 未分类的 Runtime 异常 |

非法 JSON 行和不含 `method` 的对象会被忽略，不会生成错误响应。当前协议没有请求取消帧；
运行任务通过 `tasks/stop` 停止。

## 初始化

### `initialize`

参数：空对象。

返回：

```json
{
  "protocolVersion": "1.0",
  "capabilities": {
    "threads": ["create", "list", "get", "rename", "archive", "fork", "delete", "prompt", "resume"],
    "approvals": ["list", "respond"],
    "models": ["list"],
    "providers": ["upsert", "delete", "test"],
    "permissions": ["list", "add", "remove"],
    "settings": ["get", "set"],
    "usage": ["stats", "daily"],
    "health": ["summary"],
    "data": ["summary"],
    "workspace": ["get", "set", "files"]
  },
  "defaults": {
    "mode": "chat",
    "model": "gpt-4o",
    "provider": "OpenAI"
  },
  "workspace": "/path/to/project"
}
```

当前 `capabilities` 是简化的兼容声明，未列出已经实现的 `threads/regenerate`、`tasks/*`、
`artifacts/*` 和 `memory/*`。客户端可调用本文列出的实际方法，但做协议协商时不要把未声明
能力当作跨版本稳定承诺。

## Thread 方法

| Method | Params | Result |
|---|---|---|
| `threads/create` | `{title?, parent_id?, branch_point?}` | Thread |
| `threads/list` | `{include_archived?: boolean}` | `{threads: Thread[]}` |
| `threads/get` | `{thread_id}` | Thread + `{events, tasks}` |
| `threads/rename` | `{thread_id, title}` | `{ok}` |
| `threads/archive` | `{thread_id, archived?: boolean}` | `{ok}` |
| `threads/fork` | `{thread_id, branch_point?}` | 新 Thread |
| `threads/delete` | `{thread_id}` | `{ok}` |
| `threads/prompt` | `{thread_id, content, mode?, budgets?}` | `{task}` |
| `threads/resume` | `{task_id}` | `{task}` |
| `threads/regenerate` | `{thread_id, mode?}` | `{task}` |

Thread 对象：

```json
{
  "id": "s_0123456789ab",
  "title": "新会话",
  "created_at": 1785900000.0,
  "updated_at": 1785900000.0,
  "archived": 0,
  "parent_id": null,
  "branch_point": null
}
```

`branch_point` 是 Runtime event 的 `seq` 字符串。未提供时 `threads/fork` 复制父 Thread 的
全部现有事件；提供时复制到该序号为止。任务记录不会复制到新 Thread。

### 提交任务

```json
{"id":2,"method":"threads/prompt","params":{"thread_id":"s_0123456789ab","content":"检查测试失败原因","mode":"chat","budgets":{"max_iterations":20}}}
```

`mode` 支持 `chat` 和 `build`。`chat` 运行通用工具循环；`build` 运行五角色构建调度。
`budgets.max_iterations` 限制单次 Agent 工具循环，其他预算字段会原样保存在 Task 中，但
只有 Runtime 显式读取的字段才生效。

响应中的 Task 初始状态通常为 `pending`。执行在后台继续，完成状态通过通知和
`tasks/get` 获取。

`threads/resume` 读取原 Task 的内容和模式，创建一个新 Task，并在新 Task 的 budgets 中
记录 `resumed_from`。`threads/regenerate` 查找该 Thread 最后一个用户消息并创建新 Task；
它不会删除原回合。

## Task、产物和用量

| Method | Params | Result |
|---|---|---|
| `tasks/get` | `{task_id}` | Task |
| `tasks/list` | `{thread_id?}` | `{tasks: Task[]}` |
| `tasks/stop` | `{task_id}` | `{ok}` |
| `tasks/export` | `{task_id}` | `{task, events, artifacts}` |
| `artifacts/list` | `{task_id}` | `{artifacts}` |
| `artifacts/preview` | `{path}` | `{path, content, truncated}` |
| `usage/stats` | `{thread_id?}` | 用量汇总 |

Task 状态为 `pending`、`running`、`completed`、`error` 或 `cancelled`：

```json
{
  "id": "t_0123456789ab",
  "session_id": "s_0123456789ab",
  "mode": "build",
  "status": "running",
  "content": "实现健康检查",
  "budgets": {},
  "created_at": 1785900000.0,
  "updated_at": 1785900001.0
}
```

`tasks/stop` 只对当前 app-server 进程中仍在运行的 Task 返回 `ok: true`。它取消 asyncio
任务并把状态写为 `cancelled`。

产物由成功的 `write_file` 和 `apply_patch` 工具调用登记。`artifacts/preview` 的路径相对
当前工作区，经过路径边界校验，返回最多 20,000 个字符；更长内容设置
`truncated: true`。它按 UTF-8 文本读取，不适合二进制文件。

用量响应：

```json
{"input_tokens":1200,"output_tokens":540,"total_tokens":1740,"cost":0,"calls":3,"tasks":2}
```

当前 token 是按文本长度估算，`cost` 默认是 `0`，不应直接用于账单核对。

## 工作区和记忆

| Method | Params | Result |
|---|---|---|
| `workspace/get` | `{}` | `{path, name, branch, is_git}` |
| `workspace/set` | `{path}` | Workspace info |
| `workspace/files` | `{path?}` | `{path, entries}` |
| `memory/add` | `{thread_id?, key, value}` | Memory entry |
| `memory/list` | `{thread_id?, query?}` | `{memory}` |
| `memory/delete` | `{id}` | `{ok}` |

任务运行时 `workspace/set` 会失败，以防正在执行的工具在中途切换根目录。成功后会发送
`workspace/changed`。`workspace/files` 最多检查排序后的 500 个直接子项，并忽略
`.git`、缓存、虚拟环境、构建目录和 `node_modules` 等目录；它不递归。

提供 `thread_id` 时，`memory/list` 只返回该 Thread 的记忆；不提供时返回所有记忆。查询
在读取后按 key/value 做不区分大小写的包含匹配。

## Provider 和设置

| Method | Params | Result |
|---|---|---|
| `models/list` | `{}` | `{models, active}` |
| `providers/upsert` | Provider input | 脱敏 Provider |
| `providers/delete` | `{id}` | `{ok}` |
| `providers/test` | Provider id 或内联字段 | `{ok, latency_ms, detail, error}` |
| `usage/daily` | `{days?}` | `{daily, by_model, today_tasks}` |
| `health/summary` | `{}` | Runtime 版本、系统、数据目录、运行时长等健康摘要 |
| `data/summary` | `{}` | 数据目录、`settings.json` 大小和各表记录数 |
| `settings/get` | `{}` | settings + permissions |
| `settings/set` | `{options}` | `{ok}` |

`models/list` 会依次返回环境变量配置的 Provider（存在时）、内置 Provider 预置和自定义
Provider。`providers/test` 接受已有 Provider 的 `id`（`env` 表示环境变量 Provider），或
直接接受 Provider 内联字段做一次性探测；探针失败时返回错误信息而不是抛出异常。
`usage/daily` 的 `days` 取值 1-90，默认 14。

Provider input 字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string，可选 | 新建时自动生成 `custom-N`；提供时只能编辑已有自定义 Provider |
| `name` | string | 必填显示名称 |
| `kind` | string | `openai-compatible`, `anthropic`, `gemini`, `ollama` |
| `base_url` | string/null | 自定义 API 根地址 |
| `api_key` | string/null | 内联密钥 |
| `api_key_env` | string/null | 从指定环境变量解析密钥 |
| `model` | string | 必填模型名 |
| `temperature` | number | 默认 `0.7` |
| `max_tokens` | integer | 默认 `8192` |
| `extra` | object | Provider 扩展字段 |

示例：

```json
{"id":10,"method":"providers/upsert","params":{"name":"Local API","kind":"openai-compatible","base_url":"http://127.0.0.1:8080/v1","api_key":"local-key","model":"my-model"}}
```

Provider 返回值不会包含 `api_key` 或 `api_key_env`，而是提供：

```json
{"id":"custom-1","name":"Local API","kind":"openai-compatible","base_url":"http://127.0.0.1:8080/v1","model":"my-model","temperature":0.7,"max_tokens":8192,"has_key":true,"key_source":"inline","extra":{},"custom":true}
```

脱敏只保护协议响应。内联 API Key 当前仍以明文写入本机 `settings.json`。

`settings/set` 的 `options.active_provider` 会被提升为顶层 active Provider，其余 option 会
合并到运行选项。例如：

```json
{"id":11,"method":"settings/set","params":{"options":{"active_provider":"deepseek","max_attempts":3,"max_iterations":30,"enable_shell":true,"enable_web":true}}}
```

## 权限和审批

| Method | Params | Result |
|---|---|---|
| `permissions/list` | `{}` | `{permissions}` |
| `permissions/add` | `{kind, pattern, action}` | `{ok}` |
| `permissions/remove` | `{id}` | `{ok}` |
| `approvals/list` | `{}` | `{approvals}` |
| `approvals/respond` | `{id, approved, scope?}` | `{ok}` |

持久规则的 `kind` 为 `command`、`tool` 或 `dir`，`action` 为 `allow`、`ask` 或 `deny`。
`command`/`tool` 使用通配符匹配，`dir` 使用路径前缀匹配。

当决策为 `ask` 时 Runtime 发出：

```json
{"method":"approval/requested","params":{"id":"ap-1","kind":"tool","target":"write_file","reason":"需要审批写入: src/app.py","rule_key":"dir:src/app.py","task_id":"t_0123456789ab"}}
```

客户端响应：

```json
{"id":12,"method":"approvals/respond","params":{"id":"ap-1","approved":true,"scope":"once"}}
```

`scope` 为 `once`、`session` 或 `always`。当前 `session` 和 `always` 都只记入当前 Runtime
进程的内存 PermissionEngine；需要跨重启保留时应调用 `permissions/add`。拒绝时
`approved=false`，scope 可省略。

## 通知

常见通知如下：

| Method | 关键字段 | 说明 |
|---|---|---|
| `server/ready` | `workspace`, `protocol` | Runtime 已完成初始化 |
| `workspace/changed` | workspace info | 当前工作区已切换 |
| `thread/started` | `thread_id` | Thread 有新回合 |
| `turn/started` | `thread_id`, `turn_id`, `input` | Task 开始 |
| `item/started` | IDs、`kind`、role/tool 字段 | 消息或工具项开始 |
| `item/delta` | IDs、`delta` | Agent 文本增量 |
| `item/completed` | IDs、`kind`, `payload` | 消息或工具项结束 |
| `approval/requested` | 审批对象 | 回合暂停等待客户端 |
| `turn/completed` | IDs、`status`, `content` | Task 结束 |
| `error` | IDs、`message` | 运行错误 |
| `server/error` | `message` | Desktop main 生成的 Runtime 进程错误，不是 app-server 原生通知 |

`item/completed.payload` 随 kind 变化：Agent/User 消息使用 `{content}`，工具调用使用
`{result, blocked?}`。客户端应忽略未知字段和未知通知，以保持向前兼容。

## Web HTTP/SSE

`python main.py serve --host 127.0.0.1 --port 8000` 提供：

### RPC

```http
POST /api/v1/rpc
Content-Type: application/json

{"method":"threads/list","params":{"include_archived":false}}
```

成功：

```json
{"result":{"threads":[]}}
```

失败时 HTTP 状态为 `400`：

```json
{"error":{"code":-32000,"message":"RuntimeError: ..."}}
```

### SSE

`GET /api/v1/stream` 返回 `text/event-stream`：

```text
data: {"method":"item/delta","params":{"item_id":"item-x","delta":"hello"}}

```

空闲 15 秒发送 SSE 注释 `: keep-alive`。

### 其他端点

- `GET /api/v1/health`
- `GET|POST /api/v1/sessions`
- `GET|DELETE /api/v1/sessions/{sid}`
- `POST /api/v1/sessions/{sid}/messages`
- `GET /api/v1/providers`
- `POST /api/v1/approvals/{aid}`
- `GET /api/v1/settings`
- `/` 在 `web/dist` 存在时托管 React 静态资源

这些 REST 路由是兼容适配器，新客户端优先使用 `/api/v1/rpc`。Web 服务无认证且 CORS
允许任意 Origin，只应监听 `127.0.0.1` 或 `localhost`。

## Python 客户端

```python
from pathlib import Path

from src.cli.rpc_client import RpcClient

client = RpcClient(workspace=Path.cwd())
await client.start()
await client.request("initialize")
thread = await client.request("threads/create", {"title": "示例"})
result = await client.request(
    "threads/prompt",
    {"thread_id": thread["id"], "content": "检查项目", "mode": "chat"},
)
```

`RpcClient.request()` 默认响应超时是 15 秒。这个超时仅等待 RPC 响应；提交后的后台任务
通过通知完成。退出前调用 `await client.close()`。

## CLI

| 命令 | 说明 |
|---|---|
| `python main.py` | Textual 全屏 TUI |
| `python main.py tui --thread-id ID` | 打开指定 Thread |
| `python main.py chat` | 传统终端交互模式 |
| `python main.py run "任务" --mode chat\|build` | 非交互 JSONL 执行 |
| `python main.py app-server --home PATH` | 启动 stdio Runtime |
| `python main.py serve --host 127.0.0.1 --port 8000` | 启动 Web bridge |
| `python main.py providers list\|add\|remove\|use\|test` | Provider 管理 |
| `python main.py sessions list\|show\|rm` | 旧会话 Store 管理命令 |
| `python main.py doctor` | 环境与 Provider 自检 |

`run --approve once|session|always` 会自动响应该任务收到的审批，请仅在可信工作区使用。

## 环境变量

完整列表见 [DEVELOPMENT.md](DEVELOPMENT.md)。协议相关变量包括：

| 变量 | 说明 |
|---|---|
| `GRAPHCODER_HOME` | 默认 Runtime 数据目录 |
| `GRAPHCODER_RUNTIME_PYTHON` | `RpcClient` 和 Desktop 开发模式使用的 Python |
| `GRAPHCODER_RUNTIME_DEBUG=1` | 让 `RpcClient` 继承 Runtime stderr |
| `GRAPHCODER_V1_HOME` | 首次迁移时读取旧版 JSON 数据的目录 |
| `ACTIVE_PROVIDER` | 未在设置中选择时的 Provider ID |
| `API_KEY` / `OPENAI_API_KEY` | 快速配置 OpenAI-compatible Provider |
| `API_BASE_URL` / `OPENAI_BASE_URL` | 快速配置 API 根地址 |
