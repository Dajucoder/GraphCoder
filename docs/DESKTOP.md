# Desktop Development and Packaging

GraphCoder Desktop 由 Electron main/preload、React Renderer 和冻结后的 Python Runtime
组成。开发环境使用源码 Python，生产包使用 `resources/runtime` 中的原生可执行文件。

## Process Model

```text
Electron main
  |- BrowserWindow
  |    `- sandboxed Renderer (React)
  |         `- window.graphcoder (preload bridge)
  `- graphcoder-runtime child
       `- JSONL requests/responses/notifications over stdin/stdout
```

安全边界：

- `contextIsolation: true`
- `nodeIntegration: false`
- `sandbox: true`
- Renderer 只获得 RPC、通知订阅、目录选择、系统打开和文件定位能力
- 外部 HTTP(S) 链接交给系统浏览器，Renderer 不创建任意 Electron 窗口

## Development Start

先安装依赖：

```bash
conda activate graphcoder
python -m pip install -r requirements.txt
npm ci --prefix web
npm ci --prefix desktop
```

启动两个终端：

```bash
# Terminal A: Vite
npm --prefix web run dev -- --host 127.0.0.1

# Terminal B: Electron + Python app-server
GRAPHCODER_RUNTIME_PYTHON=$(which python) \
GRAPHCODER_WEB_URL=http://127.0.0.1:5173 \
npm --prefix desktop run dev
```

开发模式的 Electron 自动运行：

```text
python -m src.api.app_server --home <Electron userData>
```

不需要启动 FastAPI。若 Renderer 页面空白，先确认 Vite 的 `5173` 端口已监听。

## Production Resources

Electron Builder 将以下内容装入应用：

```text
Resources/
  app.asar                         # main.cjs, preload.cjs, package metadata
  web/index.html                   # Vite production output
  web/assets/*
  runtime/graphcoder-runtime       # macOS
  runtime/graphcoder-runtime.exe   # Windows
```

生产主进程使用 `process.resourcesPath` 定位资源，不读取源码目录，不调用系统 Python。

## Native IPC API

`desktop/preload.cjs` 暴露：

| API | Purpose |
|---|---|
| `request(method, params)` | 请求 stdio Runtime |
| `onNotification(callback)` | 接收 Runtime 通知，返回取消订阅函数 |
| `selectWorkspace()` | 原生目录选择器 |
| `revealPath(path)` | Finder/资源管理器中定位文件 |
| `openPath(path)` | 使用系统默认应用打开文件 |
| `platform` | `darwin`、`win32` 等平台标识 |

RPC 超时当前为 120 秒。长任务的 `threads/prompt` 只创建后台任务并立即响应，后续状态通过
通知发送，因此不会占用完整任务时长。

## Application Data

生产桌面版把 Electron `userData` 作为 Runtime 的 `--home`：

| Platform | Typical location |
|---|---|
| macOS | `~/Library/Application Support/GraphCoder/` |
| Windows | `%APPDATA%\GraphCoder\` |

目录中主要文件：

| File | Contents |
|---|---|
| `runtime.sqlite` | 会话、事件、任务、权限、用量、记忆、产物索引 |
| `settings.json` | 工作区、UI/Runtime 选项、自定义 Provider、API Key |

`settings.json` 中的内联 API Key 当前是本地明文 JSON。RPC 的 `models/list` 和
`settings/get` 不会返回明文，但磁盘访问者仍可读取。不要把该目录同步到公开位置。

重置桌面数据前先完全退出 GraphCoder，然后备份或删除上述应用数据目录。删除会永久
清除会话、设置和 API Key。

## Build Runtime Only

```bash
conda activate graphcoder
python -m pip install -r requirements.txt -r packaging/requirements-build.txt
python scripts/build_runtime.py
```

产物：

```text
desktop/runtime/graphcoder-runtime       # macOS/Linux
desktop/runtime/graphcoder-runtime.exe   # Windows
```

Runtime 必须在目标 OS 和架构上构建。可用下面的 JSONL 冒烟检查协议：

```bash
printf '%s\n' \
  '{"id":1,"method":"initialize","params":{}}' \
  '{"id":2,"method":"workspace/get","params":{}}' \
  | desktop/runtime/graphcoder-runtime --home /tmp/graphcoder-smoke
```

Windows PowerShell 可启动 Runtime 后逐行写入相同 JSON，并检查是否收到
`server/ready`、`id: 1` 和 `id: 2`。

## Build macOS DMG

要求：macOS Apple Silicon、Python 3.13、Node.js 20 和完整依赖。

```bash
npm --prefix desktop run dist:mac
```

该命令依次构建 Web、PyInstaller Runtime 和 DMG。输出位于：

```text
release/GraphCoder-<version>-mac-arm64.dmg
release/mac-arm64/GraphCoder.app
```

本机环境若设置了不兼容的 Electron 镜像变量，可临时清除：

```bash
cd desktop
env -u ELECTRON_CUSTOM_DIR -u ELECTRON_MIRROR \
  CSC_IDENTITY_AUTO_DISCOVERY=false \
  ./node_modules/.bin/electron-builder --mac dmg --arm64
```

这条命令只执行 Builder；首次完整构建仍应先运行 `npm run build`。

## Build Windows Installer

在 Windows x64 PowerShell 中：

```powershell
py -3.13 -m pip install -r requirements.txt -r packaging/requirements-build.txt
npm ci --prefix web
npm ci --prefix desktop
npm --prefix desktop run dist:win
```

输出为 `release/GraphCoder-<version>-win-x64.exe`。NSIS 安装器允许选择目录，并创建
桌面与开始菜单快捷方式。

也可手动触发 GitHub Actions 的 `Desktop Release` workflow。手动触发只上传构建
artifact；推送 `v*` tag 时还会自动创建（或复用）GitHub Release 并附加安装包和
SHA-256 校验和。代码签名当前不在 workflow 中执行。

## Verification Checklist

每个平台安装包至少验证：

1. 安装/挂载成功，应用图标和名称正确。
2. 应用可在没有 Python、Node.js 和源码路径的环境启动。
3. 进程使用包内 Runtime。
4. `initialize`、工作区读取、会话创建和 Provider 切换正常。
5. API Key 不出现在 RPC 响应和 Renderer 日志中。
6. 文件选择、系统打开和文件定位正常。
7. 浅色/深色、1360x880、1024x768 和窄窗口无溢出。
8. 退出应用后 Runtime 子进程结束。

## Signing

仓库默认生成未签名测试包：

- macOS 使用 ad-hoc 签名，未开启 hardened runtime 和公证。
- Windows 未配置 Authenticode 证书。

公开分发前参照 [RELEASE.md](RELEASE.md) 配置 Apple Developer ID、公证和 Windows
代码签名。未签名包可能触发 Gatekeeper、SmartScreen 或企业终端策略。
