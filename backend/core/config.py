import os
from dotenv import load_dotenv

load_dotenv()

STORE_URL = os.getenv("STORE_URL")
WC_KEY = os.getenv("WC_KEY")
WC_SECRET = os.getenv("WC_SECRET")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Model used for chat completions. Keep the original free model by default.
# To try a different (still free) model, set AI_MODEL in your .env, e.g.:
#   meta-llama/llama-3.1-8b-instruct   (original)
#   meta-llama/llama-4-maverick:free   (newer, free)
#   google/gemma-4-31b-it:free         (free + stronger)
AI_MODEL = os.getenv("AI_MODEL", "meta-llama/llama-3.1-8b-instruct")