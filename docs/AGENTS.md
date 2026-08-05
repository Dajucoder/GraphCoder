# Agent 角色与构建调度

GraphCoder 提供一个通用对话角色和五个构建角色。角色定义集中在
`src/agents/roles.py`，生产 Runtime 通过 `src/runtime/orchestrator.py` 调度这些角色。

这里的“角色”是系统提示词和调度步骤，不是五个独立进程，也不是五套独立模型配置。
所有角色共享当前 Provider、工作区、工具、权限引擎、事件总线和持久化存储。

## 运行路径

GraphCoder 目前保留两条构建路径：

| 路径 | 入口 | 用途 |
|---|---|---|
| 生产 Runtime | `src/runtime/orchestrator.py` | Desktop、Web、TUI 和 `run` 命令使用的持久化任务路径 |
| LangGraph 兼容实现 | `src/core/graph.py` | 传统 CLI 构建流程、测试和二次开发 |

生产 Desktop 不导入或启动 LangGraph。PyInstaller Runtime 也显式排除了 `langgraph`、
`langchain` 和 `langchain_openai`。

## 对话角色

`CHAT_SYSTEM` 用于普通 `chat` 回合。`AgentEngine` 将会话历史、用户输入和工具定义交给
当前 Provider，并在模型请求工具时执行以下循环：

1. 校验工具参数 JSON Schema。
2. 计算 `allow / ask / deny` 权限决策。
3. 必要时发送 `approval/requested` 并暂停回合。
4. 执行工具，将结果加入模型上下文。
5. 继续请求模型，直到没有工具调用或达到迭代上限。

可用工具由 `src/tools/registry.py` 组装，包括文件、Shell、网页和可选 MCP 工具；
Runtime 还会增加长期记忆工具。

## 构建角色

### PM

- 提示词：`PM_SYSTEM`
- 输入：用户需求、工作区说明，以及重试时的上一轮反馈
- 输出：需求背景、功能需求、非功能需求、成功标准、边界和假设
- 目标：把原始请求整理为可供架构设计使用的 PRD

### Architect

- 提示词：`ARCHITECT_SYSTEM`
- 输入：用户需求和 PM 输出的 PRD
- 输出：技术选型、模块划分、接口与数据流、关键决策、风险与对策
- 目标：提供 Developer 可执行的技术设计

### Developer

- 提示词：`DEVELOPER_SYSTEM`
- 输入：用户需求、架构设计，以及重试时的 Reviewer/QA 反馈
- 输出：在工作区中的实际修改，以及实现摘要、文件清单和验证结果
- 目标：通过文件和 Shell 工具完成并验证实现

### Reviewer

- 提示词：`REVIEWER_SYSTEM`
- 输入：用户需求、架构设计和 Developer 的实现摘要
- 输出：按严重级别组织的正确性、安全性、可维护性和测试问题
- 目标：形成 QA 判定和下一轮修复所需的审查反馈

### QA

- 提示词：`QA_SYSTEM`
- 输入：实现摘要和 Reviewer 意见
- 输出：测试计划、质量门禁结果，以及明确的 `PASS` 或 `FAIL`
- 目标：决定本次构建尝试能否结束

## 生产调度语义

生产调度器执行：

```text
PM -> Architect -> Developer -> Reviewer -> QA
 ^                                      |
 |-------- 下一次完整尝试（FAIL） -------|
```

`src/runtime/orchestrator.py` 当前在 QA 失败时重新运行下一次完整尝试，包括 PM 和
Architect，并把上一轮 Reviewer/QA 反馈加入上下文。默认最多尝试 3 次，可通过设置中的
`max_attempts` 调整。达到上限时返回最后一次结果，即使 `qa_pass` 仍为 `false`。

QA 结果解析优先识别 `结论：PASS` 或 `结论：FAIL`。若没有标准结论行，则以输出中是否
包含 `FAIL` 作为兜底判断。因此修改 QA 提示词时必须保留明确结论格式。

## LangGraph 兼容语义

`src/core/graph.py` 使用同一组角色提示词，但其状态和回环方式不同：

```text
PM -> Architect -> Developer -> Reviewer -> QA
                    ^                         |
                    |------ FAIL -------------|
```

这条路径中的 QA 失败只回到 Developer，然后再次执行 Reviewer 和 QA。共享状态定义见
`src/core/state.py`，详细说明见 [NODES.md](NODES.md)。不要把这条路径描述为 Desktop 的
生产 Runtime。

## 事件与持久化

每个 Runtime 角色调用都会产生 `item/started`、`item/delta` 和 `item/completed` 事件，
其中 Agent 消息包含 `role` 字段。一个用户请求对应一个 Turn；构建中的多个角色调用仍
属于同一个 Turn。

事件由 app-server 通知客户端，并写入 `runtime.sqlite`。任务状态由
`ThreadManager` 在 `pending -> running -> completed|error|cancelled` 之间更新。

## 扩展角色

新增角色时：

1. 在 `src/agents/roles.py` 添加系统提示词常量。
2. 在 `src/runtime/orchestrator.py` 增加调度步骤并明确输入、输出和失败语义。
3. 若需要兼容 LangGraph，同步更新 `src/core/graph.py` 和 `GraphState`。
4. 为调度顺序、上下文传递和最大尝试次数补充 `src/tests/` 下的测试。
5. 更新本文、[ARCHITECTURE.md](ARCHITECTURE.md) 和 [ROADMAP.md](ROADMAP.md)。

角色逻辑应继续通过 Provider 抽象和工具注册表工作，不要在角色模块中直接实例化某个
模型 SDK。
