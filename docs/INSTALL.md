# GraphCoder Desktop 安装指南

GraphCoder Desktop 安装包已经包含 Electron、Web 界面和冻结后的 Python Runtime。
最终用户不需要另外安装 Python、Node.js 或下载源码。

## 下载

从 [GraphCoder Releases](https://github.com/Dajucoder/GraphCoder/releases/latest) 下载与
系统匹配的文件：

| 系统 | 安装包 | 支持范围 |
|---|---|---|
| macOS Apple Silicon | `GraphCoder-2.1.0-mac-arm64.dmg` | macOS 11+，M1/M2/M3/M4 |
| Windows x64 | `GraphCoder-2.1.0-win-x64.exe` | 64 位 Windows 10/11 |

当前没有 macOS Intel、Windows ARM 或 Linux 安装包。Release 附件中的
`SHA256SUMS.txt` 用于验证下载文件完整性。

## 校验安装包

macOS Terminal：

```bash
shasum -a 256 GraphCoder-2.1.0-mac-arm64.dmg
```

Windows PowerShell：

```powershell
Get-FileHash .\GraphCoder-2.1.0-win-x64.exe -Algorithm SHA256
```

命令输出必须与同一 Release 中 `SHA256SUMS.txt` 对应行完全一致。

## macOS 安装

1. 双击 `GraphCoder-2.1.0-mac-arm64.dmg` 挂载镜像。
2. 将 GraphCoder 拖入 `Applications` 文件夹。
3. 在 Finder 的“应用程序”中找到 GraphCoder。
4. 当前测试包未经过 Apple 公证。首次启动请右键 GraphCoder，选择“打开”，并在确认框中
   再次选择“打开”。后续可以正常双击启动。
5. 安装完成后可推出 GraphCoder 磁盘镜像并删除下载的 DMG。

如果系统仍然拦截应用，打开“系统设置 -> 隐私与安全性”，确认被拦截的应用确实为
GraphCoder，再选择“仍要打开”。不要对来源不明或校验失败的安装包绕过系统保护。

## Windows 安装

1. 双击 `GraphCoder-2.1.0-win-x64.exe`。
2. 当前安装器未配置 Authenticode 证书。如果 SmartScreen 出现提示，先确认文件来自本项目
   Release 且 SHA-256 校验正确，再选择“更多信息 -> 仍要运行”。
3. 按安装向导选择安装目录。安装器会创建开始菜单项，并可创建桌面快捷方式。
4. 安装完成后从开始菜单或桌面启动 GraphCoder。

## 首次配置

1. 打开“设置 -> 模型”。
2. 选择 OpenAI、Anthropic、Gemini、Ollama 或其他内置 Provider，也可以添加
   OpenAI-compatible 自定义 Provider。
3. 填写 API Key、Base URL 和模型名称，并保存为当前 Provider。
4. 选择一个工作区目录，然后新建会话开始使用。

API Key 只保存在本机应用数据目录的 `settings.json`，Runtime RPC 不会把明文返回给
Renderer。当前版本尚未接入系统钥匙串，因此应保护好本机账户和应用数据目录。

## 数据位置

| 系统 | 默认目录 |
|---|---|
| macOS | `~/Library/Application Support/GraphCoder/` |
| Windows | `%APPDATA%\GraphCoder\` |

`runtime.sqlite` 保存会话、任务、事件、权限、用量和记忆；`settings.json` 保存工作区、
界面设置和 Provider 配置。升级或重装前建议备份整个目录。

## 卸载

macOS：退出 GraphCoder，然后将 `/Applications/GraphCoder.app` 移到废纸篓。

Windows：打开“设置 -> 应用 -> 已安装的应用”，选择 GraphCoder 并执行卸载。

卸载应用通常不会自动删除上述用户数据。需要彻底清理时，先确认不再需要历史会话和
Provider 配置，再手工删除对应 GraphCoder 数据目录。

## 常见问题

应用白屏、Runtime 无法启动、Provider 连接失败或系统拦截安装包时，参阅
[故障排查](TROUBLESHOOTING.md)。开发者从源码运行和重新打包请参阅
[Desktop 开发与打包](DESKTOP.md)。
