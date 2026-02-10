import os
import sys
from gemini_client import configure_gemini
from dotenv import load_dotenv

# Try to handle imports similar to Superscript.py
try:
    from google import genai
    from google.genai import types
except ImportError:
    try:
        import google.generativeai as genai
    except ImportError:
        pass

def test_model():
    print("Testing 'gemini-2.0-flash' responsiveness...")
    
    try:
        # Load env vars
        load_dotenv()
        
        # Configure client just like in Superscript.py
        client = configure_gemini("parsing")
        print(f"Client configured successfully using type: {type(client)}")
        
        model_id = "gemini-2.0-flash"
        prompt = "Hello, are you responsive? Reply with 'Yes'."
        
        response = None
        
        if hasattr(client, "models"):
            # New API
            print(f"Using Google GenAI (new) API with model: {model_id}")
            response = client.models.generate_content(
                model=model_id,
                contents=prompt
            )
        else:
            # Legacy API
            print(f"Using Google GenerativeAI (legacy) API with model: {model_id}")
            model = client.GenerativeModel(model_name=model_id)
            response = model.generate_content(prompt)
            
        print("\n--- RESPONSE ---")
        if hasattr(response, 'text'):
             print(response.text)
        else:
             print(response)
        print("----------------")
        print("✅ Model is RESPONSIVE.")
        
    except Exception as e:
        print("\n❌ Model Test FAILED.")
        print(f"Error: {str(e)}")
        # Check if 404
        if "404" in str(e):
             print("\nNote: A 404 error usually means the model 'gemini-2.0-flash' is not found or your API key doesn't have access to it.")

if __name__ == "__main__":
    test_model()
