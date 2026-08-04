# API Reference

This document provides reference documentation for GraphCoder's public APIs.

---

## `src.utils.llm`

### `build_llm() -> ChatOpenAI`

Creates and returns a configured `ChatOpenAI` instance.

**Reads from environment (via `config.py`):**

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_NAME` | `step-3.7-flash` | LLM model identifier |
| `OPENAI_API_KEY` | — | API authentication key |
| `OPENAI_BASE_URL` | — | API base URL |
| `TEMPERATURE` | `1.0` | Sampling temperature |
| `MAX_TOKENS` | `256000` | Maximum tokens per response |

**Returns:** `ChatOpenAI` instance with `max_retries=3` and no timeout.

**Example:**
```python
from src.utils.llm import build_llm

llm = build_llm()
response = llm.invoke("Hello, world!")
print(response.content)
```

---

## `src.api.cli`

### `main() -> None`

Interactive CLI entry point.

1. Reads a topic from stdin: `请输入问题: `
2. Builds a simple LLM chain via `src.nodes.simple_chain.build_simple_ask_chain()`
3. Invokes the chain and prints the result

**Run:**
```bash
python main.py
```

---

## `src.nodes.simple_chain`

### `build_simple_ask_chain() -> Runnable`

Builds a minimal LangChain pipeline: `ChatPromptTemplate | ChatOpenAI`.

**Prompt template:**
```
请用中文详细解释（但不能太长）: {topic}, 请尽量调用知识库内容
```

**Example:**
```python
from src.nodes.simple_chain import build_simple_ask_chain

chain = build_simple_ask_chain()
result = chain.invoke({"topic": "量子计算"})
print(result.content)
```

---

## `config`

Module-level configuration loaded from environment variables.

**Available constants:**

| Constant | Type | Default | Description |
|----------|------|---------|-------------|
| `api_key` | `str \| None` | — | OpenAI API key |
| `base_url` | `str \| None` | — | OpenAI-compatible API base URL |
| `model_name` | `str` | `step-3.7-flash` | Model identifier |
| `temperature` | `float` | `1.0` | LLM temperature |
| `max_tokens` | `int` | `256000` | Max response tokens |

All variables are loaded from `.env` via `python-dotenv` at import time.
