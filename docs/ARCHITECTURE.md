# 系统架构

GraphCoder 是本地优先的多客户端编程系统。业务能力集中在 GraphCoder Runtime，客户端
负责界面、输入输出和少量平台集成。生产 Desktop 不依赖 HTTP 服务；Web 才通过 FastAPI
桥接 Runtime。

## 总览

```text
Desktop Renderer (React) -- preload IPC -- Electron main ----+
                                                             |
Web Browser --------------- HTTP/SSE ---- FastAPI bridge -----+-- JSONL/stdin/stdout
                                                             |          |
TUI / exec CLI ------------------------- RpcClient -----------+          v
                                                                  app-server
                                                                       |
                                     +---------------------------------+----+
                                     | Agent Engine / Build Orchestrator    |
                                     | Tools / Permissions / Approvals      |
                                     | Threads / Events / Providers         |
                                     +------------------+-------------------+
                                                        |
                                           runtime.sqlite + settings.json
```

## 进程模型

### Desktop

Desktop 由三个运行单元组成：

1. Electron main 进程创建窗口、管理 Runtime 子进程和原生文件操作。
2. sandbox Renderer 加载 Vite 构建的 React 应用。
3. PyInstaller 冻结的 `graphcoder-runtime` 子进程运行 app-server。

Renderer 不启用 Node integration，通过 `desktop/preload.cjs` 暴露的有限 API 调用 main
进程。main 将 `gc:request` 转为一行 JSON 请求写入 Runtime stdin，并把 stdout 中的响应
或通知转发给 Renderer。应用退出时 main 向 Runtime 发送 `SIGTERM`。

开发模式仍使用相同进程边界，但 Runtime 由配置的 Python 解释器执行
`python -m src.api.app_server`，Renderer 从 Vite 开发服务器加载。

### Web

`python main.py serve` 启动 `src/api/server.py`。FastAPI 创建一个 `RpcClient` 子进程，
`POST /api/v1/rpc` 转发请求，`GET /api/v1/stream` 通过 SSE 广播 Runtime 通知。FastAPI
不实现 Agent、权限或存储业务逻辑。

### TUI 与非交互 CLI

Textual TUI 和 `python main.py run` 使用 `src/cli/rpc_client.py` 启动 app-server 子进程并
直接交换 JSONL。传统 `chat`/构建 CLI 代码仍可调用 `src/core/` 的兼容实现，详见
[NODES.md](NODES.md)。

## Runtime 组件

| 组件 | 文件 | 职责 |
|---|---|---|
| App Server | `src/api/app_server.py` | RPC 分派、客户端通知、组件装配 |
| Agent Engine | `src/runtime/engine.py` | Provider 流式响应、工具循环、参数校验和权限门控 |
| Build Orchestrator | `src/runtime/orchestrator.py` | PM -> Architect -> Developer -> Reviewer -> QA 调度 |
| Thread Manager | `src/runtime/threads.py` | Thread、Turn、Task 生命周期和后台任务 |
| Event Bus | `src/runtime/events.py` | 运行事件投影到持久化和客户端 |
| Approval Hub | `src/runtime/approvals.py` | 暂停工具调用并等待客户端审批 |
| Permission Engine | `src/runtime/permission.py` | `command/tool/dir` 规则匹配与决策 |
| Context | `src/runtime/context.py` | 加载工作区说明和裁剪工具结果 |

## 请求与事件流

普通对话的生命周期如下：

```text
threads/prompt
  -> 创建 pending Task
  -> thread/started
  -> turn/started
  -> user item/started + item/completed
  -> Task 状态更新为 running
  -> Agent item/started
  -> item/delta ...
  -> tool item/started（可选）
  -> approval/requested（策略为 ask 时）
  <- approvals/respond
  -> tool item/completed
  -> Agent item/completed
  -> Task completed|error
  -> turn/completed
```

`threads/prompt` 只确认任务已创建，不等待模型完成。客户端必须订阅通知或轮询
`tasks/get`。审批也是双向流程：Runtime 主动通知，客户端再发普通 RPC 请求响应。

## Provider 解析

统一 Provider 配置位于 `src/providers/`，支持：

- `openai-compatible`
- `anthropic`
- `gemini`
- `ollama`

内置预设与自定义 Provider 最终都转换为 `ProviderConfig`。解析顺序为：

1. 未显式选择 active Provider 时，优先使用 `API_KEY` 或 `OPENAI_API_KEY` 构造环境配置。
2. 使用 `settings.json` 中选中的自定义或内置 Provider。
3. 使用 `ACTIVE_PROVIDER` 指定的内置或自定义 Provider。
4. 选择第一个已配置对应环境变量的内置预设。
5. 回退到 OpenAI 预设；此时可能仍缺少 API Key。

Provider 公共响应只包含 `has_key` 和 `key_source`，不返回明文 API Key。自定义 Provider
的内联 Key 当前仍以明文 JSON 保存在本机 `settings.json`，未接入系统钥匙串。

## 工具与权限

工具注册表提供工作区文件读写、目录列表、代码搜索、补丁、Shell、DuckDuckGo 搜索、URL
抓取和可选 MCP 工具。Runtime 额外注册记忆写入、读取和删除工具。

模型给出的工具参数先经过 JSON Schema 校验，再执行权限决策：

- `command`：匹配 Shell 命令模式。
- `tool`：匹配工具名称。
- `dir`：匹配写入路径前缀。
- `allow`：立即执行。
- `ask`：通知客户端并等待，默认超时 300 秒后拒绝。
- `deny`：返回阻止结果，不执行工具。

SQLite 中保存用户创建的策略规则。审批的 `session` 和 `always` 选择当前都只添加到该
Runtime 进程的内存规则中；进程重启后不会保留。这个行为不同于通过
`permissions/add` 创建的持久规则。

文件工具使用 `safe_join()` 限制路径到当前工作区，但 Shell 工具直接在宿主机工作区执行。
GraphCoder 没有容器、虚拟机或操作系统级沙箱。

## 存储模型

`src/storage/sqlite_store.py` 管理 `runtime.sqlite`，保存：

- sessions：Thread 元数据、归档和分支关系。
- runtime_events：追加式 Item/Turn/错误事件。
- tasks：任务内容、模式、预算和状态。
- permissions：持久权限规则。
- usage：Provider 调用的估算 token 和成本字段。
- memory：会话或全局长期记忆。
- artifacts：写文件和补丁操作登记的产物索引。

`settings.json` 单独保存自定义 Provider、active Provider、工作区和运行选项。旧版 JSON
数据可在首次启动时由 `src/storage/migrate.py` 导入。

默认源码运行目录为 `~/.graphcoder`，可用 `GRAPHCODER_HOME` 覆盖。安装版 Desktop 将
Electron `app.getPath("userData")` 作为 Runtime 的 `--home`，具体平台路径见
[DESKTOP.md](DESKTOP.md)。

## 桌面分发

生产包包含：

```text
resources/
  web/                         Vite 静态资源
  runtime/
    graphcoder-runtime         macOS
    graphcoder-runtime.exe     Windows
```

PyInstaller 产物与构建操作系统和 CPU 架构绑定。当前工作流分别在 macOS arm64 和 Windows
x64 Runner 上构建；不能在 macOS 上直接交叉生成 Windows Runtime。安装版不要求用户安装
Python、Node.js或保留源码。

## 已知边界

- `python main.py serve` 当前无认证且 CORS 允许任意 Origin，只能绑定回环地址。
- Desktop 安装包尚未默认启用 Apple Developer ID、公证或 Windows Authenticode。
- 自定义 API Key 未使用系统安全存储。
- 工具在宿主机执行，权限规则不是 OS sandbox。
- Runtime token 用量目前按文本长度估算，并非所有 Provider 的账单级精确值。
- `initialize.capabilities` 是简化握手声明，不完整枚举所有已实现 RPC。

安全部署与报告流程见 [SECURITY.md](../SECURITY.md)，构建细节见
[DESKTOP.md](DESKTOP.md) 和 [RELEASE.md](RELEASE.md)。

## 扩展原则

- 新客户端应复用 [API_REFERENCE.md](API_REFERENCE.md) 中的 RPC 和通知协议。
- 新 Provider 应实现 `src/providers/base.py` 的统一流式接口。
- 新工具应通过 `Tool` 注册并提供 JSON Schema，不绕开权限门控。
- 新角色应同步生产 Orchestrator 和需要保留的 LangGraph 兼容路径。
- 新持久数据应通过 SQLite migration 管理，不在 Renderer 中建立第二事实源。
