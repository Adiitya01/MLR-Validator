# app/config.py

import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-flash")

if not GEMINI_API_KEY:
    print("[WARNING] GEMINI_API_KEY not found in environment variables.")

# Scraping settings
DEFAULT_TIMEOUT = 10
MAX_CONCURRENT_REQUESTS = 5
IMPORTANT_PATHS = ["", "about", "about-us", "solutions", "products", "services"]
