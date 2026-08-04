# Contributing to GraphCoder

感谢你对 GraphCoder（图灵智开）的关注！🎉 我们欢迎任何形式的贡献，无论是代码、文档、Bug 报告还是功能建议。

---

## 目录

- [行为准则](#行为准则)
- [如何贡献](#如何贡献)
  - [报告 Bug](#报告-bug)
  - [建议新功能](#建议新功能)
  - [提交代码](#提交代码)
  - [改进文档](#改进文档)
- [开发环境搭建](#开发环境搭建)
- [代码规范](#代码规范)
- [提交信息规范](#提交信息规范)
- [Pull Request 流程](#pull-request-流程)
- [发布流程](#发布流程)

---

## 行为准则

本项目遵循 [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/)。请尊重每一位社区成员。

---

## 如何贡献

### 报告 Bug

如果你发现了一个 Bug，请在提交 Issue 前确认：

1. [搜索现有 Issues](https://github.com/Dajucoder/GraphCoder/issues) 确认未被报告过
2. 使用 **Bug Report** 模板，包含：
   - 复现步骤（尽可能简洁）
   - 预期行为 vs 实际行为
   - 环境信息（Python 版本、OS、依赖版本）
   - 相关日志或截图

### 建议新功能

功能建议请使用 **Feature Request** 模板，说明：

- 要解决什么问题
- 你期望的解决方案
- 可选的替代方案
- 该功能是否涉及多个 Agent 或工作流变更

### 提交代码

1. Fork 本项目到你的 GitHub 账户
2. 创建功能分支：`git checkout -b feat/my-new-feature`
3. 编写代码，确保通过 lint 和测试：`ruff check src/`
4. 提交并推送：`git push origin feat/my-new-feature`
5. 从你的 Fork 向 `main` 分支提交 Pull Request

### 改进文档

文档改进与代码同等重要！你可以：

- 修正现有文档中的错误
- 补充缺失的说明
- 翻译文档到其他语言
- 添加使用示例或教程

---

## 开发环境搭建

```bash
# 1. Clone 仓库
git clone https://github.com/Dajucoder/GraphCoder.git
cd GraphCoder

# 2. 创建并激活环境（推荐 conda）
conda create -n graphcoder python=3.13 -y
conda activate graphcoder

# 3. 安装依赖
pip install -r requirements.txt

# 4. 复制环境变量模板
cp .env.example .env
# 编辑 .env，填入你的 API Key

# 5. 验证安装
python main.py
```

### 推荐工具

| 工具 | 用途 |
|------|------|
| [ruff](https://docs.astral.sh/ruff/) | Linting（已配置） |
| [mypy](https://mypy.readthedocs.io/) | 类型检查（可选） |
| [pytest](https://docs.pytest.io/) | 测试框架（可选） |
| [PyCharm](https://www.jetbrains.com/pycharm/) | IDE（推荐） |

---

## 代码规范

- **Python 版本：** 3.13
- **导入风格：** 使用绝对导入（`from src.utils.llm import build_llm`），不使用 `sys.path` 修改
- **代码位置：**
  - 新 Agent 代码 → `src/agents/`
  - 新节点代码 → `src/nodes/`
  - 提示词模板 → `src/prompts/`
  - 辅助函数 → `src/utils/`
- **类型提示：** 所有公共函数应包含类型注解
- **文档字符串：** 公共 API 使用 Google 风格 docstring
- **行长度：** 不超过 100 字符（ruff 会自动检查）
- **命名：** 类使用 `PascalCase`，函数/变量使用 `snake_case`，常量使用 `UPPER_SNAKE_CASE`

### 示例

```python
from typing import TypedDict
from src.utils.llm import build_llm


class AgentState(TypedDict):
    """LangGraph state for the Developer agent."""
    task: str
    code: str
    review_feedback: str


def run_developer(state: AgentState) -> AgentState:
    """Execute the developer node.

    Args:
        state: Current graph state containing task and feedback.

    Returns:
        Updated state with generated code.
    """
    llm = build_llm()
    # ... implementation
    return state
```

---

## 提交信息规范

遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### Type 枚举

| Type | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `docs` | 文档变更 |
| `style` | 代码格式（不影响逻辑） |
| `refactor` | 重构（非功能变更） |
| `perf` | 性能优化 |
| `test` | 测试相关 |
| `chore` | 构建/工具链变更 |

### 示例

```
feat(agents): add PM agent with PRD generation node

Implement the Product Manager agent that takes user requirements
and produces a structured PRD document with acceptance criteria.

Closes #12
```

---

## Pull Request 流程

1. **确保 CI 通过：** 你的 PR 必须通过 GitHub Actions 检查
2. **PR 描述模板：** 按 PR 模板填写，包括变更摘要、关联 Issue、测试说明
3. **保持精简：** 每个 PR 聚焦一个功能或修复
4. **代码审查：** 至少一位 Maintainer 审查通过后合并
5. **Squash 合并：** 合并时使用 Squash and Merge

### PR 检查清单

- [ ] 代码通过 `ruff check src/`
- [ ] 新功能包含对应测试
- [ ] 相关文档已更新
- [ ] `CHANGELOG.md` 已更新（如适用）
- [ ] `.env.example` 已同步新变量（如适用）

---

## 发布流程

（由 Maintainer 执行）

1. 更新 `CHANGELOG.md` 和版本号
2. 创建 Git tag：`git tag v0.x.0 && git push --tags`
3. GitHub Actions 自动构建并发布到 PyPI

---

## 社区

- **GitHub Issues：** [Bug 报告 & 功能请求](https://github.com/Dajucoder/GraphCoder/issues)
- **GitHub Discussions：** [问答 & 讨论](https://github.com/Dajucoder/GraphCoder/discussions)

再次感谢你的贡献！ 🙏
