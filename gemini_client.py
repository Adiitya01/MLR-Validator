import os
from dotenv import load_dotenv

# Try new API first, fall back to old one
try:
    from google import genai
except ImportError:
    import google.generativeai as genai

load_dotenv()

def configure_gemini(use_case: str):
    """Configure Gemini API client with appropriate API key"""
    if use_case == "parsing":
        api_key = os.getenv("GEMINI_PARSING_API_KEY")
    elif use_case == "reasoning":
        api_key = os.getenv("GEMINI_API_KEY")
    else:
        raise ValueError("Unknown Gemini use case")

    if not api_key:
        raise RuntimeError(f"Missing API key for {use_case}")

    # Return configured client
    try:
        return genai.Client(api_key=api_key)
    except:
        # Fallback for older API
        genai.configure(api_key=api_key)
        return genai
