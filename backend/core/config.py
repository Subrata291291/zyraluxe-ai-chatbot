import os
from dotenv import load_dotenv

load_dotenv()

STORE_URL = os.getenv("STORE_URL")
WC_KEY = os.getenv("WC_KEY")
WC_SECRET = os.getenv("WC_SECRET")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")