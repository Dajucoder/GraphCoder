# LangGraph 兼容流水线

GraphCoder 的生产 Desktop/Web Runtime 使用 `src/runtime/engine.py` 和
`src/runtime/orchestrator.py`。`src/core/graph.py` 是保留的 LangGraph 兼容流水线，供传统
CLI 构建模式、测试和嵌入式 Python 调用使用。

## 状态结构

`src/core/state.py:GraphState` 是 `TypedDict(total=False)`，包含以下字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `request` | `str` | 用户的原始构建需求 |
| `session_id` | `str` | 调用方提供的会话标识 |
| `task_id` | `str` | 当前任务标识，用于事件关联 |
| `prd` | `str` | PM 输出 |
| `architecture` | `str` | Architect 输出 |
| `implementation` | `str` | Developer 输出摘要 |
| `review` | `str` | Reviewer 输出 |
| `test_plan` | `str` | 预留的测试计划字段 |
| `qa_result` | `str` | QA 输出 |
| `qa_pass` | `bool` | QA 是否放行 |
| `attempts` | `int` | 已执行 QA 的次数 |
| `max_attempts` | `int` | 最大 QA 尝试次数 |
| `events` | `list[dict]` | 使用 `operator.add` 合并的事件列表 |
| `history` | `list[dict]` | 兼容调用方提供的历史字段 |

并非每个节点都会写入所有字段。新增节点读取字段前应使用明确的必填约束，或通过
`state.get()` 提供合理默认值。

## 当前节点

节点实现在 `src/core/graph.py` 中，以私有异步函数组织：

| 节点 | 主要输入 | 写入状态 | 是否使用工具 |
|---|---|---|---|
| `_pm_node` | `request` | `prd` | 否 |
| `_architect_node` | `request`, `prd` | `architecture` | 否 |
| `_developer_node` | request、architecture、反馈 | `implementation` | 是 |
| `_reviewer_node` | request、architecture、implementation | `review` | 否 |
| `_qa_node` | implementation、review | `qa_result`, `qa_pass`, `attempts` | 否 |

`build_graph()` 闭包为节点注入 Provider、工具、工作区、审批管理器和事件回调，最终返回
编译后的 `StateGraph`。

## 图与回环

```text
START -> PM -> Architect -> Developer -> Reviewer -> QA
                              ^                    |
                              |----- QA FAIL ------|
                                                   |
                                      PASS/到达上限 -> END
```

`route_after_qa()` 在 `qa_pass=true` 或 `attempts >= max_attempts` 时结束，否则回到
Developer。回环不会重新生成 PRD 和架构。

Developer 的单次节点调用最多进行 15 轮模型工具交互，由 `MAX_DEV_TOOL_ROUNDS` 控制；
这与整个图的 `max_attempts` 是两个不同限制。

## 调用示例

```python
from pathlib import Path

from src.core.graph import build_graph
from src.providers.registry import build_provider, resolve_provider
from src.tools.registry import all_tools

config = resolve_provider()
graph = build_graph(
    provider=build_provider(config),
    tools=all_tools(),
    workspace=Path.cwd(),
    max_attempts=3,
)

initial_state = {
    "request": "为当前项目增加健康检查",
    "session_id": "example-session",
    "task_id": "example-task",
    "attempts": 0,
    "max_attempts": 3,
    "events": [],
    "history": [],
}

final_state = await graph.ainvoke(
    initial_state,
    config={"recursion_limit": 100},
)
```

Provider 调用会访问真实模型。单元测试应注入假 Provider 和假工具，不应依赖外部 API。

## 节点开发约定

- Provider 和工具由 `build_graph()` 注入，不在节点中硬编码某家 SDK。
- 节点返回本次变更的字段字典，不需要复制整个状态。
- 工具路径必须基于 `ToolContext.workspace`，并使用项目的安全路径辅助函数。
- 异常通过事件回调暴露给调用方；不要吞掉会影响图状态的异常。
- 修改 QA 结论格式时同步修改结果解析和测试。
- 修改回环边时设置合理的 `recursion_limit` 和最大尝试次数。

## 遗留节点

`src/nodes/simple_chain.py` 是早期 LLM 链路的最小示例，不参与生产 Runtime，也不参与当前
五角色图。可以用于教学或连通性验证，但新业务能力不应继续堆叠在该文件中。

## 测试重点

相关测试位于 `src/tests/`。对图和节点的修改至少应覆盖：

- 正常顺序为 PM、Architect、Developer、Reviewer、QA。
- QA PASS 后结束。
- QA FAIL 后从 Developer 回环。
- 达到 `max_attempts` 后终止。
- Developer 工具调用和异常结果能进入后续上下文。

生产调度器的测试应单独针对 `src/runtime/orchestrator.py`，因为它的失败重试语义与此图
不同。
