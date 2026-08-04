from langchain_core.prompts import ChatPromptTemplate

from src.utils.llm import build_llm


def build_simple_ask_chain():
    llm = build_llm()
    prompt = ChatPromptTemplate.from_template(
        "请用中文详细解释（但不能太长）: {topic}, 请尽量调用知识库内容"
    )
    return prompt | llm
