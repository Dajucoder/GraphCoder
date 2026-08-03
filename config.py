from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
base_url = os.getenv("OPENAI_BASE_URL")
model_name = os.getenv("MODEL_NAME", "gpt-4o-mini")
temperature = float(os.getenv("TEMPERATURE", "0.2"))
max_tokens = int(os.getenv("MAX_TOKENS", "4096"))
