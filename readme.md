# 🕸️ GraphCoder (图灵智开)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![Powered by LangGraph](https://img.shields.io/badge/Powered%20by-LangGraph-orange.svg)](https://python.langchain.com/docs/langgraph/)

> **GraphCoder (图灵智开)** 是一款基于 `LangGraph` 构建的多智能体协同编程系统（Multi-Agent AI Coding System）。  
> 
> 💡 **寓意**：英文名直指 **Graph + Coder**；中文名“图灵”一语双关，既致敬计算机科学之父图灵（代表 AI），又点出核心底层“图（Graph）”架构，“智开”即智能开发。

## 参考项目
[easy-langent](https://github.com/datawhalechina/easy-langent)
[hello-agents](https://github.com/datawhalechina/hello-agents)
[opencode](https://github.com/anomalyco/opencode)

## 🚀 快速开始 (Getting Started)

本项目推荐使用 `conda` 创建环境；作者当前使用 `Python 3.13`。

```bash
conda create -n graphcoder python=3.13
conda activate graphcoder
```

---

## 📖 简介 (Introduction)

传统的 AI 编程助手通常是单向对话式的，而在真实的软件开发中，我们需要**需求分析、架构设计、编码、代码审查（Code Review）和测试**等多角色的不断循环与反馈。

**GraphCoder** 充分利用了 [LangGraph](https://python.langchain.com/docs/langgraph/) 强大的状态管理和循环（Cycles）能力。我们将软件开发的各个环节抽象为图谱中的**节点（Nodes）**，将 Agent 之间的协作与信息流转定义为**边（Edges）**，从而打造出一个具备**自纠错能力**、**高度可控**的自动化软件开发流水线。

## ✨ 核心特性 (Key Features)

*   🤖 **多智能体角色协同 (Multi-Agent Collaboration)**
    *   内置多种 Agent 角色（如：产品经理、架构师、高级开发工程师、测试工程师），各司其职，协同完成复杂项目。
*   🕸️ **基于图的工作流 (Graph-based Workflow)**
    *   借助 LangGraph 的底层能力，支持复杂的循环工作流（例如：编码 -> 审查 -> 报错 -> 重新编码），告别线性生成的脆弱性。
*   💾 **持久化状态与记忆 (Stateful & Memory)**
    *   在整个开发生命周期中，保持对项目上下文（Context）、依赖树和历史版本的完整状态追踪。
*   🔌 **极简的拓展性 (Highly Extensible)**
    *   你可以轻松自定义新的 Agent 节点并将其接入到当前的开发图谱（Graph）中。

## 🏗️ 架构概览 (Architecture)

GraphCoder 的核心处理图谱如下所示：

```text
[User Request] 
      │
      ▼
(PM Agent) ──> 提取需求 & 编写 PRD 
      │
      ▼
(Architect Agent) ──> 系统设计 & 技术栈选择
      │
      ▼
(Coder Agent) <──┐
      │          │ (Self-Correction Loop)
      ▼          │
(Reviewer Agent) ┴──> 审查代码，如果不通过则打回重写
      │
      ▼
[Final Code Output]
