# Release Guide

本文档描述 GraphCoder Desktop 的可重复发布流程。当前 CI 生成 macOS arm64 DMG 和
Windows x64 NSIS EXE；不自动发布到 PyPI，也不自动创建 GitHub Release。

## Version Sources

安装包版本和产物文件名以 `desktop/package.json` 的 `version` 为准。发布前同步检查：

- `desktop/package.json` 的应用版本
- `web/package.json` 的前端构建元数据
- `CHANGELOG.md` 的发布标题和日期
- 文档中的示例产物名

`src/api/server.py` 暴露的 `2.0.0` 是 Web transport/API 实现版本。当前 `v2.0.0`
发布恰好与该协议版本一致，但两者仍是独立版本来源；未来发布安装包时，不要仅为了
对齐安装包而修改独立协议的版本号。

## Preflight

```bash
ruff check src/
mypy src/
pytest src/tests/ -v
npm --prefix web run build
node --check desktop/main.cjs
node --check desktop/preload.cjs
git diff --check
```

检查：

- 工作树只包含本次发布需要的变更。
- `.env`、API Key、应用数据和测试凭据未被提交。
- `CHANGELOG.md` 已从 `Unreleased` 整理到目标版本。
- `.env.example`、API 和架构文档与代码一致。
- 安装器图标 `desktop/assets/icon.icns` 和 `icon.ico` 可用。

## Local macOS Build

```bash
conda activate graphcoder
python -m pip install -r requirements.txt -r packaging/requirements-build.txt
npm ci --prefix web
npm ci --prefix desktop
npm --prefix desktop run dist:mac
```

校验产物：

```bash
shasum -a 256 release/*.dmg
hdiutil attach release/GraphCoder-*-mac-arm64.dmg
codesign -dv --verbose=2 release/mac-arm64/GraphCoder.app
```

测试完成后通过 Finder 推出卷，或使用 `hdiutil detach <mount-point>`。

## Windows Build

在 Windows x64 Runner 或本机执行：

```powershell
py -3.13 -m pip install -r requirements.txt -r packaging/requirements-build.txt
npm ci --prefix web
npm ci --prefix desktop
npm --prefix desktop run dist:win
Get-FileHash release\*.exe -Algorithm SHA256
```

Windows 产物必须在真实 Windows 环境安装和启动验证。不要把 macOS 上运行
`electron-builder --win` 生成的壳视为完整验证，因为冻结 Runtime 是平台原生的。

## GitHub Actions

`.github/workflows/desktop-release.yml` 支持：

- Actions 页面手动 `workflow_dispatch`
- 推送 `v*` tag
- `macos-14` 构建 arm64 DMG
- `windows-latest` 构建 x64 NSIS EXE
- 两个平台分别上传 Actions artifact

从 Desktop manifest 读取版本并推送 tag：

```bash
VERSION=$(node -p "require('./desktop/package.json').version")
git tag -a "v${VERSION}" -m "GraphCoder v${VERSION}"
git push origin "v${VERSION}"
```

项目允许 Git 推送走本地 `7890` 代理时，可为单次命令配置：

```bash
HTTPS_PROXY=http://127.0.0.1:7890 git push origin "v${VERSION}"
```

不要在仓库中提交个人代理配置。

## macOS Signing and Notarization

公开发布建议：

1. 使用 Developer ID Application 证书签名所有嵌套二进制和 `.app`。
2. 启用 hardened runtime，并按 Runtime 所需能力维护 entitlements。
3. 使用 `notarytool` 提交 Apple 公证。
4. 对 `.app` 或 DMG 执行 staple。
5. 在一台未安装开发工具的干净 macOS 上下载并启动验证。

当前 `desktop/package.json` 明确关闭 hardened runtime 和 Gatekeeper assess，仅适合本地
未签名构建。接入签名前要修改这些配置并验证 PyInstaller Runtime 的签名链。

常见 electron-builder CI 变量包括 `CSC_LINK`、`CSC_KEY_PASSWORD` 和 Apple 公证凭据。
具体变量随 electron-builder 版本和认证方式变化，应以当次官方文档为准，Secrets 只能
配置在 CI 密钥库中。

## Windows Signing

公开发布应对安装器和应用二进制执行 Authenticode 签名。证书私钥和密码存入 GitHub
Actions Secrets，不写入 `.env` 或仓库文件。签名后在干净 Windows x64 机器验证：

- 安装和卸载
- SmartScreen/签名发布者信息
- 用户数据升级保留
- Runtime 启动和 Provider HTTPS 请求
- 路径包含空格和非 ASCII 字符的安装目录

## Release Publication

建议发布附件：

- macOS arm64 DMG
- Windows x64 NSIS EXE
- 每个产物的 SHA-256 文件
- Release notes，包含变更、迁移、已知限制和最低系统要求

当前支持矩阵：

| Target | Build chain | Local verification |
|---|---|---|
| macOS 11+ arm64 | 已完成 | 已验证 DMG 挂载和应用启动 |
| Windows x64 | 已完成 | 需 Windows Runner/机器验证 EXE |
| macOS Intel | 未配置 | 不支持 |
| Windows arm64 | 未配置 | 不支持 |
| Linux | 未配置 | 不支持 |

## Rollback

桌面数据存储在应用 `userData` 目录，通常不会随应用卸载删除。回滚前备份
`runtime.sqlite` 和 `settings.json`。如果新版本修改数据库 schema，应提供前向迁移，
不要依赖用户手工降级数据库。
