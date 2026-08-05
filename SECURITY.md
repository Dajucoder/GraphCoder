# 安全策略

GraphCoder 是可在本机读取和修改代码、执行 Shell 命令并访问模型与网页服务的开发工具。
权限提示能降低误操作风险，但不能替代操作系统沙箱、最小权限账户和代码审查。

## 支持范围

项目当前以最新发布版本和 `main` 分支为主要修复目标。尚未承诺为旧版维护固定周期的
安全补丁分支。报告问题时请提供受影响的版本号、commit 和安装包平台。

## 报告漏洞

请不要为未修复漏洞创建公开 Issue。优先使用：

- [GitHub Private Security Advisory](https://github.com/Dajucoder/GraphCoder/security/advisories/new)
- 邮件：`dajucoder@users.noreply.github.com`

报告应包含漏洞描述、影响范围、复现步骤、概念验证、受影响版本和建议修复。请先删除
API Key、私有源码、个人路径和其他敏感信息。

维护者目标是在 48 小时内确认收到报告，7 天内给出初步评估。修复和披露时间取决于影响
和发布验证成本，通常目标为 30 天内完成。

## 信任边界

### Desktop Renderer

Electron Renderer 设置为：

- `contextIsolation: true`
- `nodeIntegration: false`
- `sandbox: true`

Renderer 只能通过 `desktop/preload.cjs` 暴露的 RPC、目录选择、文件打开和文件定位接口
访问原生能力。外部 HTTP(S) 链接由系统浏览器打开，窗口内导航被拒绝。

preload 隔离可以减少 Renderer 直接访问 Node.js 的风险，但 main 进程和 Runtime 仍拥有
当前用户权限。对 IPC 增加新方法时必须校验方法参数、路径和可调用范围。

### Runtime 与工具

Agent 工具在宿主机执行，没有容器、虚拟机、seccomp 或 macOS App Sandbox：

- 文件工具使用 `safe_join()` 将路径限制在当前工作区。
- `workspace/files` 和产物预览同样进行路径边界校验。
- Shell 命令以当前用户身份、当前工作区为 cwd 执行。
- Web 搜索和 URL 抓取会访问外部网络。
- MCP server 可能引入额外工具和外部进程，其信任模型由对应 server 决定。

路径校验不限制 Shell 命令读取工作区之外的文件，也不能阻止已批准命令启动其他进程。
在不可信仓库中运行前，应使用权限受限的操作系统账户或隔离环境。

### 权限与审批

Runtime 在工具执行前应用 `command`、`tool` 和 `dir` 规则，决策为 `allow`、`ask` 或
`deny`。未知目标默认询问，部分低风险命令有内置 allow 规则，明显破坏性命令有内置 deny
规则。

规则匹配是应用层保护，不是安全边界。模型可能使用被允许的通用 Shell 命令完成更广泛的
操作，命令字符串的通配符规则也不能理解所有 shell 语义。

通过 `permissions/add` 创建的规则保存在 SQLite。审批中的 `session` 和 `always` 当前都
只在该 Runtime 进程内存中保留；重启后失效。自动执行模式
`python main.py run --approve ...` 只应用于可信任务。

### API Key 与设置

- 环境变量中的 Key 由 Provider 在运行时解析。
- 自定义 Provider 的内联 Key 当前以明文 JSON 保存在 `settings.json`。
- `models/list` 和 `providers/upsert` 的响应不会返回 Key，只返回 `has_key` 和
  `key_source`。
- RPC 脱敏不等于磁盘加密；本地用户、备份软件和恶意进程仍可能读取设置文件。

不要提交 `.env`、`settings.json`、日志或包含凭据的任务导出。生产使用应优先选择环境
变量或操作系统级秘密管理，并限制配置文件权限。Key 暴露后立即在 Provider 侧撤销和轮换。

### 模型数据

用户输入、工作区片段、工具结果和会话历史可能发送到选中的远程 Provider。使用前应检查
Provider 的数据保留、训练、地区和合规政策。敏感项目建议使用经过审查的本地模型或私有
端点，并关闭不需要的 Web/MCP 工具。

### Web 服务

`python main.py serve` 当前：

- 没有身份认证或授权。
- CORS 允许任意 Origin。
- 暴露 Runtime RPC、会话、设置和审批能力。

只能绑定 `127.0.0.1` 或 `localhost`。不要绑定 `0.0.0.0`、公网地址或未经保护的局域网
接口。需要远程访问时，应先在可信反向代理中增加强认证、TLS、Origin 限制和请求审计。

### 本地数据

Runtime 数据包括 `runtime.sqlite` 和 `settings.json`。Desktop 使用 Electron `userData`
目录，源码运行默认使用 `~/.graphcoder`。这些文件可能包含：

- 用户输入和 Agent 输出。
- 工具调用、命令和结果摘要。
- 工作区路径、权限规则和任务状态。
- 自定义 Provider Key。
- 长期记忆和产物路径。

备份、共享问题复现材料和删除应用前，应按敏感开发数据处理这些文件。

## 安装包安全

当前本地 macOS 测试 DMG 未配置 Developer ID 签名和 Apple 公证；Windows workflow 也未
配置 Authenticode。未签名产物可能触发 Gatekeeper 或 SmartScreen，且不能向最终用户
提供发布者身份保证。

正式分发前应完成 [docs/RELEASE.md](docs/RELEASE.md) 中的签名、公证、SHA-256 和干净
环境安装验证。只从项目官方 Release 或可信构建渠道下载产物，并核对校验和。

## 依赖与 CI

CI 运行 Ruff、best-effort mypy、pytest 和 truffleHog `--only-verified` 扫描。已验证密钥
扫描不能发现所有自定义格式、无效但敏感的 token、私有数据或依赖漏洞。贡献者仍需检查
diff，并在升级 Python/npm 依赖时审查 changelog、锁文件和供应链风险。

## 安全开发清单

- 新 IPC/RPC 方法验证类型、资源所有权和路径。
- 新工具提供 JSON Schema，并经过权限引擎。
- 不在错误消息、日志、事件或测试快照中返回 API Key。
- 网络服务默认仅监听回环地址。
- 文件和归档操作防止路径穿越及符号链接逃逸。
- 任务取消、超时和 Runtime 崩溃后保持一致状态。
- 处理来自模型、网页、MCP 和工作区文件的内容时按不可信输入对待。
