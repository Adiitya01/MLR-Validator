# app/prompt_generator.py

import json
import google.generativeai as genai
from typing import List
from app.schemas import CompanyUnderstanding, GeneratedPrompt
from app.config import GEMINI_API_KEY, GEMINI_MODEL_NAME

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

MODEL = genai.GenerativeModel(GEMINI_MODEL_NAME)

def generate_user_prompts(company: CompanyUnderstanding) -> List[GeneratedPrompt]:
    """
    Generates 20 realistic user queries to test AI search visibility.
    """
    prompt = f"""
You are an expert in Generative Engine Optimization (GEO). Your task is to generate 20 realistic and highly diverse user queries that someone might ask an AI (like ChatGPT or Gemini) to find services or companies in the industry: {company.industry}.

Company Context:
- Name: {company.company_name}
- Offerings: {", ".join(company.offerings)}
- Problems Solved: {", ".join(company.core_problems_solved)}

Generate a total of 20 queries distributed across these categories:
1. Unbiased Discovery: (Broad searches for top companies/tools in the sector)
2. Specific Solution-Seeking: (Focus on solving specific technical or business pain points)
3. Competitive Comparison: (Comparing top players or asking for alternatives)
4. Intent-Based / Transactional: (Ready to hire or looking for a specific project partner)
5. Brand Awareness & Verification: (Direct questions about {company.company_name})
6. Long-Tail / Niche: (Very specific or technical queries related to {company.offerings[0] if company.offerings else 'the industry'})

Requirements:
- Ensure the queries sound like real humans asking an AI.
- Mix high-level and granular queries.
- Return exactly 20 queries.
- Return a JSON list of objects with "prompt_text" and "intent_category". 
"""

    try:
        response = MODEL.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        
        data = json.loads(response.text)
        # Robust handling for list formats
        if isinstance(data, dict):
            for key in ["queries", "prompts", "results", "data"]:
                if key in data and isinstance(data[key], list):
                    data = data[key]
                    break
        
        if not isinstance(data, list):
            raise ValueError("AI did not return a list of prompts")

        return [GeneratedPrompt(**item) for item in data[:20]]
    
    except Exception as e:
        print(f"[ERROR] Prompt generation failed: {e}")
        # Return a smaller fallback list if fails
        return [
            GeneratedPrompt(prompt_text=f"Top companies in {company.industry}", intent_category="Discovery"),
            GeneratedPrompt(prompt_text=f"Who is the leader in {company.offerings[0] if company.offerings else company.industry}?", intent_category="Discovery")
        ]
