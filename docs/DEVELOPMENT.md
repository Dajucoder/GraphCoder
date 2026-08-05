# Development Guide

本文档面向从源码开发 GraphCoder 的贡献者。桌面安装与打包细节见
[DESKTOP.md](DESKTOP.md)，发布流程见 [RELEASE.md](RELEASE.md)。

## Prerequisites

| Dependency | Supported baseline | Purpose |
|---|---:|---|
| Python | 3.13 | Runtime、CLI、API 和测试 |
| Node.js | 20 | Web 与 Electron 构建 |
| npm | 随 Node.js 安装 | 前端和桌面依赖 |
| Git | 当前稳定版 | 工作区分支信息和开发流程 |

macOS Apple Silicon 是当前已验证的本地桌面构建平台。Windows x64 安装包必须在
Windows 上构建；PyInstaller 产物不能跨平台生成。

## Bootstrap

```bash
git clone https://github.com/Dajucoder/GraphCoder.git
cd GraphCoder

conda create -n graphcoder python=3.13 -y
conda activate graphcoder
python -m pip install -r requirements.txt
cp .env.example .env

npm ci --prefix web
npm ci --prefix desktop
```

构建冻结 Runtime 时还需要：

```bash
python -m pip install -r packaging/requirements-build.txt
```

不要提交 `.env`、API Key、`release/`、`build/`、`desktop/runtime/` 或 Node 依赖目录。

## Configuration

Provider 由 `src/providers/registry.py:resolve_provider()` 按以下条件解析：

1. 调用方显式传入 active Provider ID 时，从内置和自定义 Provider 中查找该 ID。
2. 未传 active ID 且存在 `API_KEY` 或 `OPENAI_API_KEY` 时，使用兼容环境变量配置。
3. 前两项未命中时，查找 `ACTIVE_PROVIDER` 指定的内置或自定义 Provider。
4. 仍未命中时，按内置 Provider 声明顺序选择首个已有环境变量密钥的预设。
5. 最后回退到 OpenAI 内置预设，作为可能尚无密钥的默认配置。

Desktop 和 CLI 通常会把本地设置中的 active Provider ID 作为第一项传入。因此一旦
本地已选择 Provider，兼容的 `API_KEY` 配置不会覆盖该选择；清除本地选择后，
`API_KEY` / `OPENAI_API_KEY` 会先于 `ACTIVE_PROVIDER` 生效。

常用环境变量：

| Variable | Meaning |
|---|---|
| `API_KEY` | 通用 OpenAI-compatible API Key |
| `API_BASE_URL` | 通用 OpenAI-compatible Base URL |
| `OPENAI_API_KEY` | OpenAI 兼容别名 |
| `OPENAI_BASE_URL` | OpenAI 兼容别名 |
| `MODEL_NAME` | 环境变量 Provider 的模型名 |
| `ACTIVE_PROVIDER` | 内置或自定义 Provider ID |
| `TEMPERATURE` | 生成温度 |
| `MAX_TOKENS` | 最大输出 token 配置 |
| `GRAPHCODER_HOME` | CLI/TUI 数据目录，默认 `~/.graphcoder` |
| `GRAPHCODER_RUNTIME_PYTHON` | Electron/RpcClient 开发时使用的 Python |
| `LOG_LEVEL` | Python 日志级别 |

`.env.example` 是配置项的权威模板。新增配置时同步更新 `config.py`、`.env.example` 和
相关文档。

## Run Modes

### TUI and CLI

```bash
python main.py                         # 默认 Textual TUI
python main.py tui --thread-id s_xxx   # 打开指定会话
python main.py chat                    # Rich 交互聊天
python main.py doctor                  # 环境自检
python main.py run "任务" --mode chat
python main.py run "任务" --mode build --timeout 900
```

`run` 输出 JSONL。`--approve once|session|always` 会自动批准运行时审批，适合受控 CI；
对不可信仓库不要使用该选项。

### Web

一体化 Web 服务：

```bash
npm --prefix web run build
python main.py serve --host 127.0.0.1 --port 8000
```

前后端热更新：

```bash
# 终端 1
python main.py serve --host 127.0.0.1 --port 8000

# 终端 2
npm --prefix web run dev -- --host 127.0.0.1
```

Vite 将 `/api` 代理到 `http://127.0.0.1:8000`。使用其他端口时设置
`GRAPHCODER_API=http://127.0.0.1:<port>`。

### Desktop

桌面热更新需要 Vite 和 Electron 两个进程。Electron 自己启动 app-server：

```bash
# 终端 1
npm --prefix web run dev -- --host 127.0.0.1

# 终端 2
GRAPHCODER_RUNTIME_PYTHON=$(which python) \
GRAPHCODER_WEB_URL=http://127.0.0.1:5173 \
npm --prefix desktop run dev
```

不要为桌面开发另外启动 `python main.py serve`。Desktop 不经过 HTTP bridge。

## Project Layout

| Path | Responsibility |
|---|---|
| `src/api/` | CLI、stdio app-server、HTTP/SSE bridge |
| `src/runtime/` | 桌面主 Runtime、线程、事件、审批、权限和构建调度 |
| `src/providers/` | Provider 统一接口和 SDK 适配 |
| `src/tools/` | 文件、Shell、Web、MCP 工具 |
| `src/storage/` | Runtime SQLite schema、查询和 v1 迁移 |
| `src/core/` | 兼容 CLI 的 LangGraph 流水线和聊天实现 |
| `src/agents/roles.py` | 对话与五角色系统提示词 |
| `src/cli/` | TUI 和 stdio RPC 客户端 |
| `web/` | React/TypeScript Renderer/Web 客户端 |
| `desktop/` | Electron main、preload、图标和 builder 配置 |
| `packaging/` | PyInstaller entry/spec/build requirements |
| `scripts/` | 构建辅助脚本 |
| `src/tests/` | pytest 单元和集成测试 |

Desktop 的生产主链使用 `src/runtime/`；`src/core/graph.py` 保留给直接 CLI 构建路径。
修改共享行为时确认两条路径是否都需要调整。

## Development Rules

- 公共 Python 函数使用类型注解和简洁 Google-style docstring。
- 行长度不超过 100 字符；以仓库 Ruff 结果为准。
- 使用 `from src.*` 绝对导入，不修改 `sys.path`。
- Provider 实例统一从 `src.providers.registry.build_provider()` 创建。
- Runtime 状态写入 `SqliteStore`；不要为新桌面功能另建平行 JSON 数据源。
- Renderer 不得直接启用 Node.js；新增原生能力通过 preload 暴露最小 IPC API。
- 工作区路径必须经过 `safe_join()` 或等价的结构化路径校验。
- 新增 RPC 时同步更新 `initialize.capabilities`、`web/src/api.ts`、测试和 API 文档。

## Tests

完整本地检查：

```bash
ruff check src/
mypy src/
pytest src/tests/ -v
npm --prefix web run build
node --check desktop/main.cjs
node --check desktop/preload.cjs
git diff --check
```

若 mypy 只报告第三方包缺少类型桩：

```bash
python -m pip install types-jsonschema
```

测试策略：

- Provider、权限、存储和纯函数使用单元测试。
- RPC 生命周期使用临时 SQLite 和 `AppServer` 集成测试。
- 桌面主进程变更至少运行 Node 语法检查和生产 Web 构建。
- 打包链变更需要执行独立 Runtime JSONL 冒烟和对应平台安装包启动验证。
- UI 布局变更检查桌面、窄屏和深色主题，确认无横向溢出和遮挡。

## Adding Features

### Add a Provider

1. 在 `src/providers/` 实现统一流式接口。
2. 在 `PROVIDER_CLASSES` 注册 kind。
3. 如需内置条目，更新 `BUILTIN_PRESETS`。
4. 更新桌面 Provider 表单支持的 kind。
5. 增加无网络构造测试和协议脱敏测试。

### Add a Tool

1. 使用 `Tool` 和 JSON Schema 定义参数。
2. 注册到 `src/tools/registry.py` 或 Runtime 的内建工具集合。
3. 明确 `command`、`dir` 或 `tool` 权限分类。
4. 所有路径限制在工作区；限制输出大小和执行时间。
5. 增加参数错误、路径越界和拒绝权限测试。

### Add an RPC Method

1. 在 `AppServer` 添加 `rpc_<namespace>_<method>` 协程。
2. 返回 JSON 可序列化对象，不返回 API Key 等秘密。
3. 更新 Web TypeScript API 和需要的 UI 状态。
4. 添加成功、参数错误和权限边界测试。
5. 更新 [API_REFERENCE.md](API_REFERENCE.md)。

## Local Data Reset

开发时可用隔离目录，避免污染日常数据：

```bash
export GRAPHCODER_HOME="$PWD/.graphcoder-dev"
python main.py doctor
```

桌面版数据目录由 Electron `app.getPath("userData")` 决定，不读取
`GRAPHCODER_HOME` 作为 `--home`。具体目录和重置方式见 [DESKTOP.md](DESKTOP.md)。
