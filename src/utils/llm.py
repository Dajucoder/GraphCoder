from langchain_openai import ChatOpenAI

from config import api_key, base_url, model_name, temperature, max_tokens


def build_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        max_retries=3,
        timeout=None,
    )
