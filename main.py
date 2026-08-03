"""
GraphCoder 最小可运行入口

当前目标：
- 提供稳定、可演示的最小调用链
- 避免一次性把 LangGraph 复杂结构全塞进 main

后续演进方向：
1. api/ 下封装 run project from prompt
2. core/ 下封装 State + Graph + runner
3. agents/ 下封装 PM/Architect/Coder/Reviewer/QA
"""

from langchain_core.prompts import ChatPromptTemplate
from config import api_key, base_url, model_name, temperature, max_tokens
from langchain_openai import ChatOpenAI


def build_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        max_retries=3,
        timeout=None,
    )


def build_simple_ask_chain():
    llm = build_llm()
    prompt = ChatPromptTemplate.from_template(
        "请用中文详细解释（但不能太长）: {topic}, 请尽量调用知识库内容"
    )
    return prompt | llm


def main() -> None:
    topic = input("请输入问题: ")
    if not topic.strip():
        print("输入为空。")
        return

    chain = build_simple_ask_chain()
    result = chain.invoke({"topic": topic})
    print(result.content)


if __name__ == "__main__":
    main()
