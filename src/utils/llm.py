"""LLM compatibility layer.

The legacy ``build_llm()`` helper is kept for backward compatibility with the
original skeleton. New code should use :mod:`src.providers` instead, which
supports OpenAI-compatible, Anthropic, Gemini, Ollama and custom providers.
"""

from __future__ import annotations

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from config import api_key, base_url, model_name, temperature


def build_llm() -> ChatOpenAI:
    """Build a legacy LangChain ChatOpenAI instance (OpenAI-compatible only)."""
    return ChatOpenAI(
        model=model_name,
        api_key=SecretStr(api_key) if api_key else None,
        base_url=base_url,
        temperature=temperature,
        max_retries=3,
        timeout=None,
    )
