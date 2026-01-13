
import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-2.0-flash")

print(f"Using Model: {model_name}")
print(f"API Key present: {'Yes' if api_key else 'No'}")

if api_key:
    genai.configure(api_key=api_key)

model = genai.GenerativeModel(model_name)

prompt = "Return a JSON object with a key 'test' and value 'success'."

try:
    response = model.generate_content(
        prompt,
        generation_config={"response_mime_type": "application/json"}
    )
    print("Response text:", response.text)
except Exception as e:
    print("Error during generation:", str(e))
