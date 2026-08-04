from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from config import api_key, base_url, model_name, temperature


def build_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=model_name,
        api_key=SecretStr(api_key) if api_key else None,
        base_url=base_url,
        temperature=temperature,
        max_retries=3,
        timeout=None,
    )
