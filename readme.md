# GraphCoder

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/Python-3.13%2B-blue.svg)](https://www.python.org/)
[![React](https://img.shields.io/badge/Web-React%20%2B%20TypeScript-149eca.svg)](web/)
[![Electron](https://img.shields.io/badge/Desktop-Electron-47848f.svg)](desktop/)

GraphCoder 是一个本地优先的多 Provider AI 编程工具。它提供 Electron 桌面端、
React Web 端、Textual TUI 和非交互 CLI，并通过统一的 GraphCoder Runtime 执行
对话、工具调用、权限审批和多 Agent 构建任务。

桌面界面与交互参考 Apache-2.0 项目
[maka-agent](https://github.com/maka-agent/maka-agent)，实现代码、品牌和应用资源均由
GraphCoder 独立维护。

## 功能

- OpenAI 兼容接口、Anthropic、Gemini、Ollama 和自定义 Provider
- 对话模式，以及 PM -> Architect -> Developer -> Reviewer -> QA 构建模式
- 工作区文件读取、搜索、写入、Shell、网页和长期记忆工具
- `allow / ask / deny` 权限规则与运行时审批
- 会话、分支、任务、事件、产物、记忆和用量的本地持久化
- Electron 原生目录选择、文件打开和 Finder/资源管理器定位
- macOS Apple Silicon DMG 和 Windows x64 NSIS 安装包构建链

## 桌面安装

已打包的桌面应用包含 Electron、Web 资源和冻结后的 Python Runtime。最终用户无需
安装 Python、Node.js，也不需要保留源码。

当前正式版本为 `v2.0.0`，安装包从
[GitHub Releases](https://github.com/Dajucoder/GraphCoder/releases/latest) 下载：

```text
GraphCoder-2.0.0-mac-arm64.dmg
GraphCoder-2.0.0-win-x64.exe
```

macOS 首次打开未签名测试包时，在 Finder 中右键 GraphCoder 并选择“打开”。公开分发
必须配置 Apple Developer ID 签名和公证。Windows 安装包需要在 Windows x64 或项目的
GitHub Actions Windows Runner 上构建。

完整的下载、校验、安装、配置和卸载说明见 [安装指南](docs/INSTALL.md)。开发与打包细节
见 [桌面开发指南](docs/DESKTOP.md)。

## 从源码运行

要求：Python 3.13、Node.js 20、npm，以及可用的模型 Provider。

```bash
conda create -n graphcoder python=3.13 -y
conda activate graphcoder
pip install -r requirements.txt
cp .env.example .env
npm ci --prefix web
npm ci --prefix desktop
```

配置 `.env` 后可运行：

```bash
# 默认启动全屏 TUI
python main.py

# 环境和 Provider 自检
python main.py doctor

# 非交互任务，按 JSONL 输出事件
python main.py run "检查这个项目并修复测试" --mode build

# Web 服务，内置 HTTP/SSE 传输层
npm --prefix web run build
python main.py serve --host 127.0.0.1 --port 8000
```

桌面开发需要两个终端：

```bash
# 终端 1
npm --prefix web run dev -- --host 127.0.0.1

# 终端 2；Conda 环境已激活时 $(which python) 即可
GRAPHCODER_RUNTIME_PYTHON=$(which python) \
GRAPHCODER_WEB_URL=http://127.0.0.1:5173 \
npm --prefix desktop run dev
```

Electron 会自动启动 stdio Runtime，不要再单独运行 `main.py serve` 或 app-server。

## 模型配置

推荐通过桌面端“设置 -> 模型”添加 Provider。也可以通过 `.env` 或 CLI 配置：

```bash
python main.py providers list
python main.py providers use deepseek
python main.py providers test deepseek
```

内置 Provider ID：`openai`、`anthropic`、`gemini`、`ollama`、`deepseek`、
`moonshot`、`zhipu`、`qwen`、`stepfun`。

桌面端自定义 API Key 保存在本机应用数据目录的 `settings.json` 中，RPC 响应不会返回
明文，但该文件当前不是系统钥匙串加密存储。详见 [安全策略](SECURITY.md)。

## 架构

```text
React Web ---- HTTP/SSE ---- FastAPI bridge ---+
                                                 |
Electron ---- sandbox preload / IPC ------------+--> app-server (JSONL/stdin/stdout)
                                                 |        |
TUI / CLI ---- RpcClient ------------------------+        v
                                                  Agent Engine
                                                  Tools + Permissions
                                                  SQLite + settings.json
```

桌面生产包中的 app-server 被 PyInstaller 冻结为原生 Runtime，并由 Electron 主进程管理。
Renderer 开启 sandbox、关闭 Node integration，只能通过 preload 暴露的有限 IPC 接口访问
Runtime 和原生能力。

## 文档

| 文档 | 内容 |
|---|---|
| [开发指南](docs/DEVELOPMENT.md) | 环境、运行方式、测试、目录和开发工作流 |
| [安装指南](docs/INSTALL.md) | DMG/EXE 下载、校验、安装、配置和卸载 |
| [桌面指南](docs/DESKTOP.md) | Electron/Web/Runtime 联调、数据目录、打包与排障 |
| [架构说明](docs/ARCHITECTURE.md) | 进程模型、Runtime、存储、权限和扩展点 |
| [API 参考](docs/API_REFERENCE.md) | stdio RPC、通知、HTTP/SSE 和 CLI |
| [Agent 规范](docs/AGENTS.md) | 对话引擎和五角色构建调度 |
| [节点指南](docs/NODES.md) | LangGraph 兼容流水线与 Runtime 调度器 |
| [发布指南](docs/RELEASE.md) | DMG/EXE、CI、签名、公证和校验和 |
| [故障排查](docs/TROUBLESHOOTING.md) | 常见启动、Provider、Runtime 和构建问题 |
| [路线图](docs/ROADMAP.md) | 已完成能力、已知边界和后续计划 |
| [贡献指南](CONTRIBUTING.md) | 代码规范、测试和 PR 流程 |

## 质量检查

```bash
ruff check src/
mypy src/
pytest src/tests/ -v
npm --prefix web run build
node --check desktop/main.cjs
node --check desktop/preload.cjs
git diff --check
```

当前测试基线为 `40 passed`。CI 的 mypy 仍采用 best-effort 策略；本地严格检查需要安装
缺失的第三方类型桩，例如 `types-jsonschema`。

## 数据与安全

- CLI/TUI 默认数据目录：`~/.graphcoder`
- 桌面安装版使用 Electron 的 `userData` 目录
- `runtime.sqlite` 保存会话、事件、任务、权限、用量、记忆和产物索引
- `settings.json` 保存工作区、选项、自定义 Provider 和 API Key
- Agent 的 Shell 和文件工具在宿主机执行，不是容器或虚拟机沙箱
- `python main.py serve` 当前无用户认证，只应绑定回环地址

## License

[MIT](LICENSE)
