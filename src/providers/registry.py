"""Provider registry: built-in presets + user-defined custom providers."""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from src.providers.anthropic_provider import AnthropicProvider
from src.providers.base import ProviderConfig
from src.providers.gemini_provider import GeminiProvider
from src.providers.ollama_provider import OllamaProvider
from src.providers.openai_compat import OpenAICompatProvider

PROVIDER_CLASSES: dict[str, type] = {
    "openai-compatible": OpenAICompatProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
    "ollama": OllamaProvider,
}

BUILTIN_PRESETS: list[ProviderConfig] = [
    ProviderConfig(
        id="openai",
        name="OpenAI",
        kind="openai-compatible",
        base_url="https://api.openai.com/v1",
        api_key_env="OPENAI_API_KEY",
        model="gpt-4o",
    ),
    ProviderConfig(
        id="anthropic",
        name="Anthropic Claude",
        kind="anthropic",
        base_url=None,
        api_key_env="ANTHROPIC_API_KEY",
        model="claude-sonnet-4-5",
    ),
    ProviderConfig(
        id="gemini",
        name="Google Gemini",
        kind="gemini",
        base_url=None,
        api_key_env="GEMINI_API_KEY",
        model="gemini-2.5-pro",
    ),
    ProviderConfig(
        id="ollama",
        name="Ollama (本地)",
        kind="ollama",
        base_url="http://127.0.0.1:11434",
        model="qwen2.5-coder:14b",
    ),
    ProviderConfig(
        id="deepseek",
        name="DeepSeek",
        kind="openai-compatible",
        base_url="https://api.deepseek.com/v1",
        api_key_env="DEEPSEEK_API_KEY",
        model="deepseek-chat",
    ),
    ProviderConfig(
        id="moonshot",
        name="Moonshot Kimi",
        kind="openai-compatible",
        base_url="https://api.moonshot.cn/v1",
        api_key_env="MOONSHOT_API_KEY",
        model="kimi-k2",
    ),
    ProviderConfig(
        id="zhipu",
        name="智谱 GLM",
        kind="openai-compatible",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        api_key_env="ZHIPU_API_KEY",
        model="glm-4-plus",
    ),
    ProviderConfig(
        id="qwen",
        name="通义千问 Qwen",
        kind="openai-compatible",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key_env="DASHSCOPE_API_KEY",
        model="qwen-max",
    ),
    ProviderConfig(
        id="stepfun",
        name="阶跃星辰 StepFun",
        kind="openai-compatible",
        base_url="https://api.stepfun.com/v1",
        api_key_env="STEPFUN_API_KEY",
        model="step-2-16k",
    ),
    ProviderConfig(
        id="grok",
        name="xAI Grok",
        kind="openai-compatible",
        base_url="https://api.x.ai/v1",
        api_key_env="XAI_API_KEY",
        model="grok-4",
    ),
    ProviderConfig(
        id="siliconflow",
        name="SiliconFlow",
        kind="openai-compatible",
        base_url="https://api.siliconflow.cn/v1",
        api_key_env="SILICONFLOW_API_KEY",
        model="deepseek-ai/DeepSeek-V3",
    ),
]


def build_provider(config: ProviderConfig):
    """Instantiate a provider class from its config."""
    cls = PROVIDER_CLASSES.get(config.kind)
    if cls is None:
        raise ValueError(f"不支持的 provider 类型: {config.kind}")
    return cls(config)


def env_provider() -> ProviderConfig | None:
    """Build a provider from legacy environment variables (API_KEY/API_BASE_URL)."""
    key = os.getenv("API_KEY") or os.getenv("OPENAI_API_KEY")
    if key:
        return ProviderConfig(
            id="env",
            name="环境变量 (API_KEY)",
            kind=os.getenv("PROVIDER_KIND", "openai-compatible"),
            base_url=os.getenv("API_BASE_URL")
            or os.getenv("OPENAI_BASE_URL")
            or "https://api.openai.com/v1",
            api_key=key,
            model=os.getenv("MODEL_NAME", "step-3.7-flash"),
            temperature=float(os.getenv("TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("MAX_TOKENS", "8192")),
        )
    return None


def resolve_provider(
    custom_providers: list[ProviderConfig] | None = None,
    active_id: str | None = None,
) -> ProviderConfig:
    """Resolve the active provider config.

    Priority: env vars (legacy quick start) > active custom provider > builtin preset.
    """
    env_cfg = env_provider()
    if env_cfg and not active_id:
        return env_cfg

    all_providers = list(BUILTIN_PRESETS)
    if custom_providers:
        all_providers += custom_providers

    target = active_id or os.getenv("ACTIVE_PROVIDER")
    if target:
        for p in all_providers:
            if p.id == target:
                return p
    # fall back to a preset whose env key is populated
    for p in BUILTIN_PRESETS:
        if p.api_key_env and os.getenv(p.api_key_env):
            return p
    return BUILTIN_PRESETS[0]


def merge_presets(custom_providers: list[dict[str, Any]]) -> list[ProviderConfig]:
    """Convert raw dicts from settings into ProviderConfig objects."""
    out = list(BUILTIN_PRESETS)
    for raw in custom_providers:
        out.append(ProviderConfig(**raw))
    return out
