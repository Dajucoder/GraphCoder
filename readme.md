# 🕸️ GraphCoder v2 (图灵智开)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/downloads/)
[![Self-built](https://img.shields.io/badge/Engine-Self--built-green.svg)](src/runtime/)
[![TypeScript](https://img.shields.io/badge/Web-React%20%2B%20TypeScript-blue.svg)](web/)
[![Electron](https://img.shields.io/badge/Desktop-Electron-47848F.svg)](desktop/)

> GraphCoder v2 采用 **Codex App Server + Maka + Hermes** 的设计模式（参考其架构与
> 交互风格，引擎完全自研）：所有功能（Agent 循环、
> 工具、权限、存储）下沉到可嵌入的 **GraphCoder Runtime**；CLI/TUI 与 Desktop
> 通过 **app-server 子进程 + JSON-RPC over stdio** 接入（无 HTTP 后端），Web 仅保留
> 纯传输层。执行引擎为**自研多 Provider Agent 引擎**，多 Agent 构建流水线降为调度层，SQLite 为
> 唯一权威存储（追加式事件日志）。

## ✨ 功能特性

- **App Server 协议**（Codex 模式）：Item / Turn / Thread 三层原语，
  `item/started → delta → completed` 统一所有界面流式渲染；`approval/requested`
  可暂停回合等待客户端响应
- **自研 Agent 引擎**：多 Provider 原生流式（OpenAI 兼容 / Anthropic / Gemini /
  Ollama / 自定义）+ 工具调用循环（文件/Shell/Web）
- **多 Agent 调度层**：PM → 架构师 → 开发者 → 审查 → QA，QA 失败自动回环
- **细粒度权限引擎**：`allow / ask / deny` ×（命令模式/工具/目录），危险命令拦截、
  人工审批暂停/恢复、决策记忆、watchdog 超时拒绝
- **Maka 式存储**：SQLite 权威（sessions / runtime_events / tasks / settings /
  permissions / usage），v1 JSON 自动迁移
- **三端客户端**：Textual 全屏 TUI（Codex 语义配色 + slash 命令）、Electron
  Desktop（IPC 直连 app-server）、React Web（对话 + 工作台融合风格）

## 🚀 快速开始

### 1. 安装

```bash
conda create -n graphcoder python=3.13 -y && conda activate graphcoder
pip install -r requirements.txt
cp .env.example .env   # 填入 API 密钥

cd web && npm install && cd ../desktop && npm install
```

> app-server 与 TUI/Web 运行在同一 `graphcoder` 环境（无需额外运行时）。

### 2. 运行

```bash
# 全屏 TUI（默认，Codex 风格）
python main.py

# 非交互 exec 模式（JSONL 输出，退出码反映成败）
python main.py run "写一个 FastAPI 待办应用" --mode build

# Web 传输层（静态 + JSON-RPC/SSE 桥）
python main.py serve --port 8000

# 手动启动 app-server（stdio JSON-RPC）
python -m src.api.app_server

# Desktop（Electron，自动 spawn app-server 子进程）
cd desktop && npm start
```

TUI slash 命令：`/new` `/graph` `/chat` `/model <id>` `/permission allow|ask|deny <命令>`
`/resume` `/help` `/exit`。

## 🏗️ 架构

```
Web (HTTP+SSE)   Desktop (Electron IPC)   TUI/CLI (stdio JSON-RPC)
        \                 |                     /
         \                v                    /
          └──> graphcoder app-server (JSON-RPC lite over stdio)
                         |
                    GraphCoder Runtime
              Agent Engine + Orchestrator
              Permission Engine + Event Bus
                         |
                    SQLite 权威存储（事件日志）
```

详细设计见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## 📡 App Server 协议摘要

请求：`{"id": 1, "method": "threads/prompt", "params": {...}}`

| 方法 | 说明 |
|---|---|
| `initialize` | 握手，返回 capabilities 与默认值 |
| `threads/create/list/get/rename/archive/fork/delete` | 线程生命周期 |
| `threads/prompt` | 提交回合（chat / build） |
| `threads/resume` | 续跑中断任务 |
| `approvals/respond` | 审批响应（once/session/always） |
| `models/list` | 模型 Provider 列表 |
| `permissions/add/remove/list` | 权限策略管理 |

通知：`thread/started`、`turn/started|completed`、`item/started|delta|completed`、
`approval/requested`、`error`。完整协议见 [docs/API_REFERENCE.md](docs/API_REFERENCE.md)。

## 🧪 测试

```bash
conda run -n graphcoder pytest src/tests/ -v
conda run -n graphcoder ruff check src/ main.py config.py
conda run -n graphcoder mypy src/ --ignore-missing-imports
```
