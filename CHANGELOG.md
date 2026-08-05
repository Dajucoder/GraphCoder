# CHANGELOG

All notable changes to GraphCoder will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- Chat system prompt now answers greetings and self-introduction requests
  directly instead of deflecting with "state your task first".

## [2.0.1] — 2026-08-05

### Changed
- Switch the project license from MIT to a custom non-commercial license based
  on the Apache License 2.0 text with additional non-commercial terms.

## [2.0.0] — 2026-08-05

### Added
- Add a Maka-inspired desktop shell with collapsible sessions, conversation
  workspace, task/file/activity workbar, settings, themes, and responsive layouts.
- Add native workspace selection, Git metadata, bounded file browsing, and OS
  reveal/open integration for Electron.
- Add desktop model connection management with local API-key storage and
  secret-free protocol responses.
- Add a PyInstaller runtime, Electron Builder DMG/NSIS packaging, and native
  macOS arm64/Windows x64 GitHub Actions release jobs. Installed users no longer
  need Python, Node.js, or a source checkout.
- Add development, desktop packaging, release, troubleshooting, runtime API,
  agent orchestration, and security documentation for the current architecture.

### Changed
- Align `.env.example`, README, and API docs with the environment variables
  actually read by `config.py`.
- Replace obsolete scaffold and planned-module descriptions with the production
  Runtime, Electron IPC, HTTP/SSE bridge, and LangGraph compatibility boundaries.
- Document that Windows x64 packaging is configured but still requires a native
  runner installation test, while macOS arm64 has been built and launched locally.

### Fixed
- CI: create a uv virtual environment before installing dependencies so the
  Lint, Type Check, and Tests jobs no longer fail at install time.
- Lint and typecheck: remove an unused import, sort imports, and pass `api_key`
  to `ChatOpenAI` as a `SecretStr`.
- SECURITY.md: reflect that CI now runs a verified-secret scan with truffleHog.

### Runtime and agent platform
- **App Server 架构**（Codex 模式）：`graphcoder app-server` 以 JSON-RPC lite over stdio
  提供 Item / Turn / Thread 三层原语（initialize 握手、`item/started→delta→completed`、
  `approval/requested` 双向暂停），CLI/TUI 与 Desktop 均以子进程方式接入，无 HTTP 依赖。
- **自研 Agent 引擎**（`src/runtime/engine.py`）：多 Provider 原生流式 + 工具调用循环，
  权限门控在工具执行前完成（异步审批暂停/恢复）；参考 Hermes/Codex/Maka 设计，无外部
  Agent 框架依赖。
- **Maka 式权威存储**：SQLite（sessions / runtime_events / tasks / settings / permissions /
  usage）为唯一事实源，追加式事件日志；v1 JSON 数据首次启动自动迁移。
- **细粒度权限引擎**：allow/ask/deny × 命令模式/工具/目录；引擎在工具执行前拦截，
  ask 走人工审批门（TUI/Web/CLI 均可响应），watchdog 超时拒绝；
  决策记忆（始终允许/会话允许）写入策略库。
- **Textual 全屏 TUI**：Codex 语义配色（青/绿/红/品红）、会话区（用户/Agent/工具卡片/
  审批/流式增量）、底部输入栏与状态、slash 命令（/new /graph /chat /model /permission
  /resume /help /exit）。
- **融合前端重设计**：Codex 式对话（item 生命周期、工具卡片、审批内联）+ Maka 式工作台
  （会话搜索/归档/分支/重试、模型选择器、权限策略面板）。

### Added (Maka 功能对齐)
- **模块化工作台**：左侧模块导航（会话/任务/产物/记忆/设置）+ 会话面板 + 主视图 + 右侧详情面板。
- **Markdown 渲染**：消息按 Markdown/GFM 渲染（代码块、表格、链接），工具结果可折叠展开。
- **任务账本**：stat-tile 统计（已完成/运行中/失败/Tokens/调用次数）+ 任务卡片 + JSON 导出。
- **用量统计**：引擎按回合估算 input/output tokens 并入库，`usage/stats` 汇总。
- **产物管理**：write_file/apply_patch 自动登记产物，`artifacts/list` + `artifacts/preview` 预览。
- **长期记忆**：SQLite memory 表 + memory_write/read/forget 工具 + `memory/list|delete`。
- **工具参数校验**：工具调用前 jsonschema 校验，参数非法直接返回错误不崩溃。
- **构建图面板**：PM→架构→编码→审查→QA 流程图，当前角色高亮。
- **回合重建修复**：历史会话消息内容正确还原（payload 嵌套层级）。
- **会话增强**：重命名、重新生成（regenerate）、相对时间显示、Toast 提示。
- **Web 纯传输层**：FastAPI 仅托管静态资源并桥接 JSON-RPC/SSE 到 app-server 子进程，
  业务逻辑全部位于 Runtime；v1 REST 契约保留为薄适配器。
- **多 Agent 调度器**：PM→架构→开发→审查→QA 以角色提示词驱动自研引擎，QA 回环；
  LangGraph 运行时依赖移除。

### Changed
- `graphcoder` 无子命令默认进入全屏 TUI；`run` 改为非交互 exec 模式（JSONL 输出）。
- Desktop（Electron）不再依赖 HTTP 服务：main 进程 spawn app-server 子进程，经 IPC 桥接。

## [1.0.0] — 2026-08-05

### Added
- **多 Provider 接入层**（`src/providers/`）：统一异步接口，支持 OpenAI 兼容端点、
  Anthropic、Gemini、Ollama 及任意自定义 API；密钥支持环境变量引用；内置 9 个常见
  Provider 预设（OpenAI/Claude/Gemini/Ollama/DeepSeek/Kimi/智谱/通义/StepFun）。
- **Agent 工具层**（`src/tools/`）：文件读写/搜索/补丁、Shell 执行（危险命令人工审批）、
  网页搜索/抓取、MCP（Model Context Protocol）客户端扩展。
- **LangGraph 多 Agent 流水线**（`src/core/graph.py`）：PM → 架构师 → 开发者 → 审查 →
  QA 质量门禁，QA 失败自动回环修复，含最大尝试次数保护。
- **聊天引擎**（`src/core/chat.py`）：带原生工具调用循环的流式聊天。
- **FastAPI 服务端**（`src/api/server.py`）：REST + SSE + WebSocket 实时流、会话/任务
  持久化、命令审批、产物文件与修改文件追踪、静态 Web 托管。
- **Web 前端**（`web/`）：React + TypeScript + Vite，流式聊天、工具调用卡片、命令审批、
  Provider 设置抽屉、会话管理、修改文件展示。
- **Desktop 应用**（`desktop/`）：Electron 封装，自动拉起后端服务。
- **Rich CLI**（`src/api/cli.py`）：`chat` / `run` / `serve` / `providers` / `sessions` / `doctor`。
- **测试套件**：21 个单元/集成测试覆盖 provider、工具、存储、流水线回环、HTTP API。

> Historical note: the original 1.0.0 server included a WebSocket path. The
> current Runtime architecture uses JSONL over stdio and HTTP/SSE for Web; do
> not treat WebSocket as a current transport contract.

---

## [0.2.0] — 2026-08-04

### Added
- **Package restructuring:** reorganized codebase into modular `src/` layout:
  - `src/core/` — state schema and graph builder
  - `src/agents/` — agent definitions (PM, Architect, Developer, Reviewer, QA)
  - `src/nodes/` — LangGraph node implementations
  - `src/data/` — I/O layer for requirements and artifacts
  - `src/api/` — CLI entry point and future HTTP server
  - `src/prompts/` — reusable prompt templates
  - `src/utils/` — helper utilities (LLM factory)
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

## [0.1.0] — 2026-07-30

### Added
- Initial project scaffold
- Single-file LLM call chain via LangChain
- README with architecture overview
