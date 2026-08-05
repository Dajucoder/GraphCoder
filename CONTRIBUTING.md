# 贡献指南

GraphCoder 接受代码、测试、文档、问题报告和功能建议。提交变更前请先阅读本文以及
[开发指南](docs/DEVELOPMENT.md)。

## 报告问题

提交 Issue 前请先搜索已有问题，并尽量包含：

- 可重复执行的复现步骤。
- 预期行为与实际行为。
- GraphCoder 版本或 commit、操作系统和 CPU 架构。
- Python、Node.js、npm 版本；桌面问题还需 Electron 版本。
- 已脱敏的日志、截图和 Provider 类型。
- 问题发生在 Desktop、Web、TUI、CLI 或独立 Runtime 中的哪一层。

安全问题不要公开提交 Issue，请按 [SECURITY.md](SECURITY.md) 私下报告。

## 开发环境

要求 Python 3.13、Node.js 20、npm 和 Git。基础环境：

```bash
git clone https://github.com/Dajucoder/GraphCoder.git
cd GraphCoder

conda create -n graphcoder python=3.13 -y
conda activate graphcoder
pip install -r requirements.txt
cp .env.example .env

npm ci --prefix web
npm ci --prefix desktop
```

不要提交 `.env`、真实 API Key、Runtime 数据库或本地构建产物。Provider 配置、各入口的
启动方法和数据隔离方式见 [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)。

## 目录职责

| 目录 | 职责 |
|---|---|
| `src/runtime/` | 生产 Agent Engine、任务编排、权限、审批和事件 |
| `src/api/` | CLI 入口、stdio app-server 和 FastAPI Web bridge |
| `src/providers/` | Provider 抽象和 OpenAI/Anthropic/Gemini/Ollama 适配 |
| `src/tools/` | 文件、Shell、Web、MCP 工具及安全路径辅助函数 |
| `src/storage/` | SQLite schema、查询和旧数据迁移 |
| `src/core/` | LangGraph 兼容流水线和传统聊天实现 |
| `src/agents/` | 角色系统提示词 |
| `src/cli/` | Textual TUI 和 stdio RPC 客户端 |
| `web/` | React、TypeScript、Vite Renderer |
| `desktop/` | Electron main/preload 和 electron-builder 配置 |
| `packaging/`, `scripts/` | PyInstaller Runtime 和打包脚本 |
| `src/tests/` | pytest 测试 |

生产 Desktop 不使用 `src/core/graph.py`。修改代理调度前先确认目标是生产 Runtime、
LangGraph 兼容层，还是两者都需要同步。

## 开发流程

1. Fork 仓库并从最新 `main` 创建聚焦的功能分支，例如 `feat/runtime-recovery`。
2. 阅读相关实现和测试，确认进程边界与数据所有权。
3. 完成功能和对应测试，更新受影响的文档与环境变量模板。
4. 执行本地质量检查。
5. 使用 Conventional Commits 提交，并向 `main` 创建 Pull Request。

维护者或自动化 coding agent 使用的本地分支可采用 `codex/` 前缀；外部贡献者无需强制
使用该前缀。

## 代码规范

- Python 公共函数使用类型提示和 Google 风格 docstring。
- 类名使用 `PascalCase`，函数和变量使用 `snake_case`，常量使用
  `UPPER_SNAKE_CASE`。
- 使用 `from src.*` 绝对导入，不修改 `sys.path`。
- Python 行长度不超过 100 个字符。
- Provider 使用 `src/providers/` 的统一抽象；兼容 LangChain 的代码使用
  `src/utils/llm.py:build_llm()`，不要在业务模块直接实例化某家 SDK。
- 文件访问使用 `safe_join()` 和工作区上下文，不拼接未校验路径。
- 新工具必须提供 JSON Schema，并通过 Runtime 权限门控。
- 新环境设置同步更新 `config.py`、`.env.example` 和相关文档。
- 不在 Electron Renderer 暴露 Node.js；原生能力通过受限 preload IPC 提供。

手工编辑文件后运行格式化工具即可，不要借格式化提交无关的大范围改动。

## 测试与检查

基础检查：

```bash
ruff check src/
mypy src/
pytest src/tests/ -v
git diff --check
```

Web 或 Desktop 变更还应运行：

```bash
npm --prefix web run build
node --check desktop/main.cjs
node --check desktop/preload.cjs
```

涉及独立 Runtime 或安装包时，按 [桌面开发指南](docs/DESKTOP.md) 执行 JSONL 冒烟，
并在目标操作系统构建和启动安装包。PyInstaller 不能跨操作系统生成可用 Runtime。

测试应与风险匹配：

- Provider 变更覆盖请求映射、流式文本、工具调用和错误响应。
- Runtime 变更覆盖事件顺序、任务状态、审批暂停/恢复和取消。
- 存储变更覆盖 schema 初始化、读写和迁移。
- Web/Desktop 变更检查 Desktop IPC 与 HTTP/SSE 两种传输。
- 构建调度变更分别测试生产 Orchestrator 和需要保留的 LangGraph 兼容路径。

## CI

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) 在 push 和 Pull Request 上运行：

- Ruff lint。
- mypy type check，目前为 best-effort，不阻断 CI。
- pytest；存在测试文件时执行。
- truffleHog `--only-verified` 密钥扫描。

Desktop 安装包由 [`.github/workflows/desktop-release.yml`](.github/workflows/desktop-release.yml)
在 tag 或手动触发时分别于 macOS arm64 和 Windows x64 Runner 构建。该工作流不是基础
CI 的替代品。

## 提交信息

遵循 [Conventional Commits](https://www.conventionalcommits.org/)：

```text
<type>[optional scope]: <description>
```

常用类型：`feat`、`fix`、`docs`、`refactor`、`test`、`chore`、`perf`。例如：

```text
fix(runtime): keep approval responses readable during streaming
docs(desktop): document Windows packaging validation
```

每个 commit 聚焦一个逻辑变更；不要混入本地配置、依赖缓存或不相关格式化。

## Pull Request

PR 描述应说明：

- 解决的问题和主要实现。
- 影响的客户端、Runtime 模块和数据格式。
- 执行过的测试及结果。
- UI 变更的桌面和窄窗口截图。
- 新配置、迁移、兼容性或安全影响。

提交前检查：

- [ ] Ruff、pytest 和适用的 mypy 检查已执行。
- [ ] Web build 和 Desktop 语法检查已按变更范围执行。
- [ ] 新行为有聚焦测试。
- [ ] API、架构、开发或发布文档已同步。
- [ ] `.env.example` 已同步新增环境变量。
- [ ] `CHANGELOG.md` 已记录面向用户的变化。
- [ ] Diff 中不包含密钥、个人数据、数据库或构建缓存。

## 发布

发布由维护者执行。版本、DMG/EXE 构建、SHA-256、tag、平台签名和回滚流程以
[docs/RELEASE.md](docs/RELEASE.md) 为准，不再使用早期 PyPI 发布流程作为桌面版发布入口。

## 行为准则

参与项目即表示同意遵守
[Contributor Covenant 2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/)。
