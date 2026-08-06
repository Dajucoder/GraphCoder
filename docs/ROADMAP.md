# 路线图

本文记录当前能力、已知工程缺口和后续优先级，不承诺具体发布时间。发布事实以
[CHANGELOG.md](../CHANGELOG.md) 和 Git tag 为准。

## 当前能力

截至 2026-08-06，仓库已实现：

- 自研多 Provider Agent Engine，支持 OpenAI-compatible、Anthropic、Gemini、Ollama
  和自定义 Provider。
- 文件、Shell、网页、MCP 和 Runtime 记忆工具。
- PM -> Architect -> Developer -> Reviewer -> QA 构建调度和失败重试。
- stdio JSONL app-server，以及 Thread、Turn、Item、Task 事件模型。
- SQLite 会话、事件、任务、权限、用量、记忆和产物索引。
- `allow / ask / deny` 权限规则与异步人工审批。
- React Web 工作台、Textual TUI、非交互 CLI 和 Electron Desktop。
- Web 的 FastAPI HTTP RPC/SSE bridge。
- PyInstaller 独立 Runtime、electron-builder DMG/NSIS 构建配置。
- macOS Apple Silicon DMG 本机构建、挂载和启动验证。
- macOS arm64 与 Windows x64 的 GitHub Actions 桌面构建工作流。
- 全屏设置中心（通用、模型、用量、数据、权限、健康、关于），内置 Provider
  目录和连接测试探针。

`src/core/graph.py` 仍保留 LangGraph 兼容流水线，但 Desktop/Web 的生产任务使用
`src/runtime/` 自研执行链。Web 当前没有 WebSocket 传输，实时事件使用 SSE。

## 已知边界

| 领域 | 当前状态 |
|---|---|
| macOS arm64 | DMG 已构建并完成本地安装启动验证 |
| Windows x64 | NSIS workflow 已配置，仍需 Windows Runner 真实产物和安装验证 |
| macOS Intel | 未配置构建和验证 |
| Windows ARM | 未配置构建和验证 |
| Linux Desktop | 未配置发布包 |
| macOS 签名/公证 | 未配置正式 Developer ID 发布链 |
| Windows 签名 | 未配置 Authenticode |
| API Key | RPC 脱敏，但自定义内联 Key 在本地 JSON 明文保存 |
| Web 安全 | 无认证，CORS `*`，只适合 loopback |
| 工具隔离 | 有应用权限规则，没有 OS sandbox |
| 用量统计 | Token 为估算值，成本字段未接账单定价 |
| 自动更新 | 未实现 |

## P0：可分发版本

- [ ] 在 Windows x64 Runner 生成 EXE，完成安装、卸载、首次启动、Provider 和工作区验证。
- [ ] 为 macOS 配置 Developer ID、Hardened Runtime、entitlements 和公证。
- [ ] 为 Windows 配置 Authenticode 签名和时间戳服务。
- [ ] 将基础 Python 测试、Web build 和 Desktop 语法检查纳入发布工作流前置门禁。
- [ ] 为发布产物自动生成 SHA-256 并附加到 GitHub Release。
- [ ] 以 Desktop manifest 作为安装包版本来源，并自动同步 tag、产物名和发布说明。
- [ ] 增加安装版 Runtime 崩溃、升级和数据保留回归测试。

## P1：安全与可靠性

- [ ] 使用 macOS Keychain、Windows Credential Manager 等系统安全存储保护 API Key。
- [ ] 为 Web bridge 增加可选认证、严格 Origin 和安全的远程部署模式。
- [ ] 设计可选的容器或受限子进程工具执行后端。
- [ ] 让审批 `always` 语义真正持久化，并明确 `session` 生命周期。
- [ ] 改进 Runtime 异常退出后的 Task 恢复和状态修复。
- [ ] 为 SQLite 增加显式 schema version 和增量 migration。
- [ ] 加强符号链接、Shell 组合命令和 MCP 工具的安全测试。
- [ ] 使用 Provider 原生 usage 数据替换或校准 token 估算。

## P1：桌面体验

- [ ] 自动更新和可验证的更新清单。
- [ ] 大文件、二进制文件和图片的安全预览。
- [ ] 更完整的任务恢复、重试、导出和错误诊断界面。
- [ ] Provider 模型发现、错误提示一致性，以及连接测试探针的覆盖面扩展。
- [ ] Desktop 与 Web 双传输的端到端 UI 测试。
- [ ] Windows/macOS 快捷键、窗口状态和无障碍检查。

## P2：开发平台

- [ ] 稳定并版本化 app-server 协议，完整声明 capabilities。
- [ ] Provider、工具和角色的插件发现与隔离机制。
- [ ] MCP server 生命周期、权限和配置 UI。
- [ ] OpenAPI/协议 schema 和客户端代码生成。
- [ ] 文档站、架构决策记录和发布支持矩阵自动化。
- [ ] 基准测试，包括长会话、工具密集任务和大型仓库。

## 暂未实现

以下能力不应在说明中标为现有功能：

- OAuth 登录、多用户协作或云同步。
- 语音输入输出。
- Computer Use 或内嵌浏览器自动化。
- Telegram、Slack、Discord 等 Bot 接入。
- WebSocket 实时传输。
- VS Code/JetBrains 正式插件。
- Linux、macOS Intel、Windows ARM 安装包。
- PyPI 自动发布链。

## 优先级原则

1. 先保证可验证安装、数据不丢失和权限边界。
2. 再完善签名、公证、更新和跨平台发布。
3. 协议稳定后再扩展第三方插件与远程部署。
4. 新功能必须说明其 Desktop、Web、TUI 和 CLI 的支持范围，避免只实现一个表面入口。

功能建议可通过
[GitHub Discussions](https://github.com/Dajucoder/GraphCoder/discussions) 讨论，贡献流程见
[CONTRIBUTING.md](../CONTRIBUTING.md)。
