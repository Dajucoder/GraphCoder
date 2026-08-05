import os

from dotenv import load_dotenv

load_dotenv()

# Unified API key: prefer API_KEY, fall back to legacy OPENAI_API_KEY.
api_key = os.getenv("API_KEY") or os.getenv("OPENAI_API_KEY")
base_url = os.getenv("OPENAI_BASE_URL")
model_name = os.getenv("MODEL_NAME", "step-3.7-flash")
temperature = float(os.getenv("TEMPERATURE", "1.0"))
max_tokens = int(os.getenv("MAX_TOKENS", "256000"))

# Unified provider settings: prefer these over the legacy aliases.
api_base_url = os.getenv("API_BASE_URL") or base_url or "https://api.openai.com/v1"
active_provider = os.getenv("ACTIVE_PROVIDER", "")
graphcoder_home = os.getenv("GRAPHCODER_HOME", "")
log_level = os.getenv("LOG_LEVEL", "INFO")
debug = os.getenv("DEBUG", "false").lower() in {"1", "true", "yes"}
