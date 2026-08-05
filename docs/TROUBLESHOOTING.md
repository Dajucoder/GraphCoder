# Troubleshooting

## Desktop Opens a Blank Window

开发模式下确认 Vite 已启动：

```bash
lsof -nP -iTCP:5173 -sTCP:LISTEN
curl http://127.0.0.1:5173/
```

然后确保 Electron 使用同一地址：

```bash
GRAPHCODER_WEB_URL=http://127.0.0.1:5173 npm --prefix desktop run dev
```

生产包不使用 Vite；检查应用内是否存在 `resources/web/index.html`。

## Runtime Cannot Start

开发模式显式指定 Conda Python：

```bash
GRAPHCODER_RUNTIME_PYTHON=/absolute/path/to/graphcoder/bin/python \
npm --prefix desktop run dev
```

并验证：

```bash
/absolute/path/to/python -m src.api.app_server --workspace "$PWD"
```

生产包检查 `resources/runtime/graphcoder-runtime`，Windows 检查同目录的 `.exe`。最终用户
不应被要求安装 Python；若生产包调用系统 Python，说明资源路径或打包配置有误。

## Port Already in Use

```bash
lsof -nP -iTCP:5173 -iTCP:8000 -sTCP:LISTEN
```

Vite 可换端口：

```bash
npm --prefix web run dev -- --host 127.0.0.1 --port 5174
GRAPHCODER_WEB_URL=http://127.0.0.1:5174 npm --prefix desktop run dev
```

Web API 可换端口，并同步设置 Vite 的 `GRAPHCODER_API`。

## Provider Has No Key

```bash
python main.py doctor
python main.py providers list
python main.py providers test <provider-id>
```

检查 `.env` 的变量名与 [DEVELOPMENT.md](DEVELOPMENT.md) 一致。桌面端添加的自定义
Provider 写入 Electron `userData/settings.json`，与 CLI 默认的 `~/.graphcoder/settings.json`
可能不是同一份文件。

若设置了通用 `API_KEY`，它可能优先形成环境变量 Provider。需要明确切换时，在桌面设置
中选择 Provider，或清理冲突环境变量后重启应用。

## Provider Request Fails

- 确认 Base URL 是否包含服务端要求的 `/v1`。
- 确认模型名是服务端真实模型 ID，不是显示名称。
- 检查系统代理、证书和企业网络策略。
- Ollama 默认连接 `http://127.0.0.1:11434`，先运行 `ollama list`。
- PyInstaller 的 `sentencepiece`、Pillow、HTTP/2 等告警多为 SDK 可选功能；只有实际使用
  对应本地 tokenizer、图片或 HTTP/2 路径时才需要纳入 Runtime。

## Approval Never Resolves

默认审批超时是 300 秒。确认当前会话仍打开，并在审批卡片选择允许或拒绝。未知工具、
Shell 命令和写入目录默认采用 `ask`；可在设置的权限页面添加精确规则。

`always`/`session` 目前会加入当前 Runtime 内存规则；通过权限设置页面添加的策略会写入
SQLite 并跨启动保留。

## Cannot Switch Workspace

运行中的任务会阻止工作区切换。先在任务面板停止任务，等待 `turn/completed`，再选择新目录。

工作区必须存在且是目录。文件浏览器会隐藏 `.git`、`node_modules`、构建缓存等目录，并将
单次列表限制为 500 个条目。

## File Preview Is Truncated

`artifacts/preview` 只返回前 20,000 个字符，并使用 UTF-8 容错解码。二进制文件不适合
内置文本预览，请使用“系统打开”。

## macOS Says the App Is Damaged or Unverified

当前本地包未做 Developer ID 签名和 Apple 公证。可信的本地测试包可在 Finder 中右键
GraphCoder，选择“打开”。不要对来源不明的应用绕过 Gatekeeper。

面向用户发布时应完成签名与公证，而不是要求用户长期关闭系统安全检查。

## Electron Download Returns 404

检查环境变量：

```bash
env | rg '^ELECTRON_(MIRROR|CUSTOM_DIR)='
```

若镜像变量不适配当前 Electron 版本，可对单次构建取消：

```bash
cd desktop
env -u ELECTRON_CUSTOM_DIR -u ELECTRON_MIRROR npm run dist:mac
```

## PyInstaller Warnings

警告文件位于 `build/runtime-work/graphcoder-runtime/warn-graphcoder-runtime.txt`。平台专属
模块（如 `_winapi`、`winreg`）和 SDK 可选依赖不一定是错误。判断标准是：

1. 目标平台 Runtime 能启动并返回 `server/ready`。
2. `initialize` 和工作区 RPC 正常。
3. 所有内置 Provider 可构造。
4. 实际支持的工具路径可运行。
5. 安装后的应用不访问源码 Python 环境。

不要为了消除警告无差别打包测试、Notebook、图片和云平台扩展，这会显著增大安装包。

## mypy Reports Missing Stubs

```bash
python -m pip install types-jsonschema
mypy src/
```

CI 当前把 mypy 作为 best-effort；本地严格检查应安装实际报告缺少的类型桩。

## Stop Development Processes

正常停止方式是在 Vite 和 Electron 终端按 `Ctrl+C`，桌面应用使用 `Command+Q` 或退出菜单。
检查残留：

```bash
pgrep -af 'vite|src.api.app_server|GraphCoder.app'
lsof -nP -iTCP:5173 -iTCP:8000 -sTCP:LISTEN
```

只终止确认属于当前工作区的 PID，避免使用宽泛的系统级 kill 命令。
