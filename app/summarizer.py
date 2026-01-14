# app/summarizer.py

import json
import google.generativeai as genai
from app.schemas import CompanyUnderstanding
from app.config import GEMINI_API_KEY, GEMINI_MODEL_NAME

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

MODEL = genai.GenerativeModel(GEMINI_MODEL_NAME)

def summarize_company(chunks: list[str], manual_points: str = "") -> CompanyUnderstanding:
    """
    Summarizes company information by combining website content and manual user points.
    """
    combined_site_text = "\n".join(chunks[:8]) if chunks else "No website content available."
    
    prompt = f"""
You are a professional business analyst. Your task is to extract key information about a company.
You have two sources of information:
1. Website Content (Crawl)
2. Manual User Points (Specific Details provided by the user)

---
WEBSITE CONTENT:
\"\"\"
{combined_site_text}
\"\"\"

---
MANUAL USER POINTS:
\"\"\"
{manual_points}
\"\"\"

Instructions:
1. Extraction: Merge information from both sources. Prioritize Manual User Points if there is a conflict.
2. If a field (like target_users) is unknown, return an empty list [], UNLESS it is a string field, then return "N/A".
3. Return valid JSON only.

JSON Schema:
{{
  "company_name": "Official name of the company.",
  "company_summary": "A 2-3 sentence overview.",
  "industry": "Primary industry category.",
  "offerings": ["List of products/services"],
  "target_users": ["List of customers"],
  "core_problems_solved": ["List of problems solved"]
}}
"""

    try:
        response = MODEL.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        
        # Clean up response text in case of markdown blocks
        res_text = response.text.strip()
        if res_text.startswith("```json"):
            res_text = res_text.replace("```json", "", 1).replace("```", "", 1).strip()
            
        data = json.loads(res_text)
        
        # Handle list response
        if isinstance(data, list) and len(data) > 0:
            data = data[0]
        
        # Ensure lists are actually lists to avoid Pydantic errors
        for field in ["offerings", "target_users", "core_problems_solved"]:
            if field in data and isinstance(data[field], str):
                data[field] = [data[field]] if data[field] not in ["Information not available", "N/A", ""] else []
            elif field not in data:
                data[field] = []
        
        # Ensure name is not "Unknown" if we can do better
        if data.get("company_name") == "Unknown" and manual_points:
            # Very simple heuristic: first line or first few words of manual points might contain the name
            # But better to just let it be if the AI couldn't find it. 
            # However, we'll strip any "Official name of..." boilerplate if AI returned that
            pass

        return CompanyUnderstanding(**data, manual_points=manual_points)
    
    except Exception as e:
        print(f"[ERROR] Summarization failed: {e}")
        if 'response' in locals():
            print(f"[DEBUG] Raw response: {response.text}")
        
        # Fallback: if we have manual points, maybe we can guess the name?
        # For now, just return defaults but keep manual_points
        return CompanyUnderstanding(
            company_name="Analysis Pending" if manual_points else "Unknown",
            company_summary="Could not automatically summarize company data.",
            manual_points=manual_points
        )
