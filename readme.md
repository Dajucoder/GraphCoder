# 🕸️ GraphCoder (图灵智开)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![Powered by LangGraph](https://img.shields.io/badge/Powered%20by-LangGraph-orange.svg)](https://python.langchain.com/docs/langgraph/)

> **GraphCoder（图灵智开）** 是基于 LangGraph 的多智能体自动化编程系统。  
> 通过“需求分析 / 架构设计 / 编码 / 审查 / 测试”的图状协作，实现可追溯、可扩展、可回环的软件生成流。  
> 中文名双关“图灵”与“图（Graph）”，既致敬 AI 源头，也强调核心抽象是“图驱动”。

## 🎯 近期目标（长文先给概述）

近期目标是把 GraphCoder 从“脚本示例”重构为**可运行最小骨架 + 可扩展真实分模块项目**，不中断现有演示脚本。

1. 让 README 精确对应目录与运行方式。
2. 将核心代码分层为：
   - `src/core`
   - `src/agents`
   - `src/nodes`
   - `src/data`
   - `src/api`
   - `src/prompts`
   - `src/utils`
   - `src/tests`
3. 给出最小运行入口，并可持续接入 LangGraph 工作流。

## 📂 项目结构（当前可预期）

```
GraphCoder/
├── .env
├── .env.example
├── .gitignore
├── README.md
├── config.py
├── main.py
├── requirements.txt
│
└── src/
    ├── core/          # 状态 schema、图构建、入口封装
    ├── agents/        # PM / Architect / Coder / Reviewer / QA 定义
    ├── nodes/         # LangGraph 节点实现
    ├── data/          # 需求读取 / 产出落盘 / 日志
    ├── api/           # CLI / 脚本 / 未来 HTTP 入口（逐步接入）
    ├── prompts/       # 提示词模板
    ├── utils/         # 辅助函数
    └── tests/         # 单元与集成测试
```

## 🏗️ 架构概览（核心图谱）

```
[User Request]
      │
      ▼
┌──────────────────────────────────────────────────┐
│                 GraphCoder Core                   │
│          LangGraph State Machine Mesh             │
│  ┌────────────┐   ┌────────────┐   ┌───────────┐  │
│  │  PM 节点    │──▶│  AD 节点   │──▶│ Dev 节点  │  │
│  └────────────┘   └────────────┘   └─────┬─────┘  │
│        ▲                                │        │
│        │                    ┌────────────┴──────┐ │
│        └────────────────────│ Reviewer 节点    │◀┘
│                              └───────┬─────────┘
│                                      │
│                              ┌───────▼─────────┐
│                              │  QA 节点        │
│                              └───────┬─────────┘
│                                      │
│                            [可回环修复流程]
└──────────────────────────────────────────────────┘
                        │
                        ▼
                 [Final Output]
```

- **PM：** 需求澄清、输出 PRD 与成功标准；
- **AD：** 系统设计、技术选型与架构分片；
- **Dev：** 编码实现、修改建议时的重写；
- **Reviewer：** 静态审查与结构化反馈；
- **QA：** 测试定义、质量门禁、是否放行。

## 🚀 快速开始（Getting Started）

### 前置要求

- Python 3.13（[下载地址](https://www.python.org/downloads/)）
- pip 包管理器

> **Windows 用户注意：** 安装 Python 时务必勾选 **"Add Python to PATH"**。

---

### 1. 创建 Python 环境

#### macOS / Linux

**方式 A：conda（推荐）**
```bash
conda create -n graphcoder python=3.13 -y
conda activate graphcoder
```

**方式 B：venv（系统自带）**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### Windows

**PowerShell**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

> 如果执行 `Activate.ps1` 报错（禁止加载脚本），先运行：
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```

**CMD**
```cmd
.venv\Scripts\activate.bat
```

---

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 配置环境变量
```bash
cp .env.example .env
```

最小必须配置：
```
API_BASE_URL=https://api.openai.com/v1
API_KEY=
MODEL_NAME=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=
TEMPERATURE=0.2
MAX_TOKENS=4096
LOG_LEVEL=INFO
DEBUG=false
```

## 🏃 运行

### 运行最小示例
```bash
python main.py
```

当前最小示例用于验证 LLM 调用链路，后续会替换为完整的 LangGraph 运行入口。

## 🔧 常见问题

### 依赖报 `No module named`
确认已进入 `graphcoder` 环境后，重新执行第二步安装。

### 当前还不能直接生成完整项目
当前为最小骨架；完整自动化能力会逐步在 `src/agents`、`src/nodes`、`src/api` 中落地。
