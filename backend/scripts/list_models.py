import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_PARSING_API_KEY") or os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

print(f"Using API Key ending in: {api_key[-4:] if api_key else 'None'}")

try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(m.name)
except Exception as e:
    print(f"Error: {e}")
