# CLAUDE.md

本文为在 GraphCoder 仓库中工作的 coding agent 提供代码库事实和验证要求。更高优先级的
仓库规则见根目录 `AGENTS.md`。

## 项目定位

GraphCoder 是 Python 3.13 + React/TypeScript + Electron 的本地优先 AI 编程工具。生产
Runtime 是 `src/runtime/engine.py` 的自研 Provider/工具循环，构建模式由
`src/runtime/orchestrator.py` 调度 PM、Architect、Developer、Reviewer 和 QA。

不要把项目描述成“最小 LLM skeleton”，也不要把 `src/core/graph.py` 当作 Desktop 的生产
执行链。该文件是仍保留的 LangGraph 兼容实现。

## 常用命令

```bash
conda activate graphcoder
pip install -r requirements.txt

# 默认 Textual TUI
python main.py

# 非交互 Runtime 任务
python main.py run "检查当前项目" --mode chat
python main.py run "实现需求并验证" --mode build

# Web bridge，只绑定回环地址
npm --prefix web run build
python main.py serve --host 127.0.0.1 --port 8000

# 质量检查
ruff check src/
mypy src/
pytest src/tests/ -v
npm --prefix web run build
node --check desktop/main.cjs
node --check desktop/preload.cjs
git diff --check
```

Desktop 联调和安装包命令见 `docs/DESKTOP.md`，不要在不需要时启动长期后台服务。

## 生产架构

- `desktop/main.cjs`：Electron 生命周期、Runtime 子进程、RPC IPC、原生文件操作。
- `desktop/preload.cjs`：向 sandbox Renderer 暴露有限 `window.graphcoder` API。
- `web/src/`：Desktop Renderer 与 Web 共用 React 界面，通过 `web/src/api.ts` 抽象 IPC
  和 HTTP/SSE 两种传输。
- `src/api/app_server.py`：JSONL/stdin/stdout RPC 分派和 Runtime 装配。
- `src/runtime/engine.py`：Provider 流式工具循环、JSON Schema 校验、权限和审批。
- `src/runtime/orchestrator.py`：生产五角色构建调度。
- `src/runtime/threads.py`：Thread/Turn/Task 生命周期和后台执行。
- `src/storage/sqlite_store.py`：`runtime.sqlite` 权威状态。
- `src/utils/settings.py`：`settings.json`、Provider 和工作区选项。
- `src/providers/`：OpenAI-compatible、Anthropic、Gemini、Ollama 统一接口。
- `src/tools/`：文件、Shell、Web、MCP 工具。

Web 使用 FastAPI bridge 的 `/api/v1/rpc` 和 `/api/v1/stream`。Desktop 不启动 FastAPI，
Electron main 直接管理 app-server Runtime。

## 兼容路径

- `src/core/graph.py`：LangGraph 五角色图，QA 失败回到 Developer。
- `src/core/chat.py`：传统 CLI 工具聊天实现。
- `src/nodes/simple_chain.py`：早期最小示例，不参与生产运行。
- `src/data/store.py`：旧 CLI session 命令使用的兼容 Store，不是 Runtime SQLite 主接口。

修改共享角色提示词、Provider 或工具时评估两条路径是否都受影响。生产行为的测试应优先
覆盖 `src/runtime/` 和 app-server。

## 数据与安全

- 源码运行默认数据目录为 `~/.graphcoder`；安装版 Desktop 使用 Electron `userData`。
- `runtime.sqlite` 保存会话、事件、任务、权限、用量、记忆和产物。
- `settings.json` 保存工作区、选项和自定义 Provider；内联 API Key 当前是本地明文。
- 公共 Provider RPC 响应不得包含 `api_key` 或 `api_key_env`。
- 文件路径使用 `safe_join()`；Shell 仍在宿主机执行，不存在 OS sandbox。
- `python main.py serve` 无认证且 CORS `*`，只能默认绑定 loopback。
- Renderer 保持 `contextIsolation: true`、`nodeIntegration: false`、`sandbox: true`。

## 开发约定

- 使用 `src.*` 绝对导入，不修改 `sys.path`。
- Python 公共函数添加类型提示和 Google 风格 docstring，行长不超过 100。
- Provider 通过统一抽象创建；LangChain 兼容代码使用 `build_llm()`。
- 新工具提供 JSON Schema，并通过 Runtime 权限引擎。
- 新 RPC 同步更新 `web/src/api.ts`、测试和 `docs/API_REFERENCE.md`。
- 新环境变量同步更新 `config.py`、`.env.example` 和开发文档。
- 数据 schema 变更必须考虑现有用户升级和迁移。
- 不回退工作区中与当前任务无关的未提交改动。

## 发布事实

Desktop 版本当前来自 `desktop/package.json`。生产包将 Vite 资源复制到
`resources/web`，将 PyInstaller Runtime 复制到 `resources/runtime`。PyInstaller 产物不能
跨操作系统构建。

macOS Apple Silicon DMG 已在本机完成构建和启动验证；Windows x64 workflow 已配置但仍需
Windows Runner 的真实安装验证。签名、公证和校验流程见 `docs/RELEASE.md`。

## 文档索引

- `readme.md`：用户入口和快速开始。
- `docs/DEVELOPMENT.md`：开发环境和工作流。
- `docs/DESKTOP.md`：Desktop 联调、进程、数据和打包。
- `docs/ARCHITECTURE.md`：系统边界和数据流。
- `docs/API_REFERENCE.md`：RPC、通知和 Web bridge。
- `docs/AGENTS.md`：角色和生产调度。
- `docs/NODES.md`：LangGraph 兼容流水线。
- `docs/RELEASE.md`：发布流程。
- `docs/TROUBLESHOOTING.md`：常见故障。
- `SECURITY.md`：安全边界和漏洞报告。
