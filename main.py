from langchain_core.prompts import ChatPromptTemplate

from config import api_key,base_url
from langchain_openai import ChatOpenAI


llm = ChatOpenAI(
    model="step-3.7-flash",
    api_key=api_key,
    base_url=base_url,
    temperature=0.7,
    max_retries=3,
    timeout=None,
)

prompt = ChatPromptTemplate.from_template(
    "请解释: {topic}"
)

chain = prompt | llm

result = chain.invoke({
    "topic": input("请输入问题: ")
})

print(result.content)
