from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
base_url = os.getenv("OPENAI_BASE_URL")
model_name = os.getenv("MODEL_NAME", "step-3.7-flash")
temperature = float(os.getenv("TEMPERATURE", "1.0"))
max_tokens = int(os.getenv("MAX_TOKENS", "256000"))
