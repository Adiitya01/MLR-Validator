# app/evaluator.py

import json
import traceback
import google.generativeai as genai
from typing import List
from app.schemas import CompanyUnderstanding, GeneratedPrompt, ModelResponse, EvaluationMetric, VisibilityReport
from app.config import GEMINI_API_KEY, GEMINI_MODEL_NAME

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Note: We create the model instances as needed if tools change, 
# but for now we'll define the base model name.
BASE_MODEL = genai.GenerativeModel(GEMINI_MODEL_NAME)

def evaluate_visibility(company: CompanyUnderstanding, prompts: List[GeneratedPrompt], use_google_search: bool = False) -> VisibilityReport:
    """
    Executes prompts and evaluates how the company appears in AI responses.
    """
    model_results = []
    
    # Configure tools if google search is requested
    # We create a new model instance here to ensure tools are applied correctly per request
    if use_google_search:
        try:
            # Use the correct google_search tool format
            model = genai.GenerativeModel(
                model_name=GEMINI_MODEL_NAME,
                tools=[{"google_search": {}}]
            )
            print("[INFO] Using Google Search grounding (google_search)")
        except Exception as e:
            print(f"[WARNING] Google Search grounding not available: {e}")
            print("[INFO] Falling back to standard model without grounding")
            model = BASE_MODEL
            use_google_search = False  # Disable flag since we're falling back
    else:
        model = BASE_MODEL
    
    for gen_prompt in prompts:
        print(f"[INFO] Testing prompt: {gen_prompt.prompt_text} (Google Search Grounding: {use_google_search})")
        
        # 1. Get raw AI response
        try:
            ai_response = model.generate_content(gen_prompt.prompt_text)
            response_text = ai_response.text
            print(f"[SUCCESS] Generated response ({len(response_text)} chars)")
        except Exception as e:
            error_msg = str(e)
            print(f"[ERROR] Content generation failed: {error_msg}")
            traceback.print_exc()
            
            # Provide helpful error message
            if "google_search" in error_msg.lower() or "grounding" in error_msg.lower():
                response_text = "Google Search grounding is not available with your API key. Please use Gemini Standard mode or upgrade your API access."
            elif "quota" in error_msg.lower():
                response_text = "API quota exceeded. Please try again later or check your API limits."
            elif "api key" in error_msg.lower():
                response_text = "API key error. Please verify your GEMINI_API_KEY in the .env file."
            else:
                response_text = f"Analysis error: {error_msg}"

        # 2. Use AI to EVALUATE the response
        eval_prompt = f"""
You are an AI Search Visibility Auditor. Analyze the "Model Response" provided below to see how "{company.company_name}" is positioned.

Model Response:
\"\"\"
{response_text}
\"\"\"

Audit requirements for "{company.company_name}":
1. brand_present: Is the company mentioned? (true/false)
2. url_cited: Is the company's website URL mentioned or linked? (true/false).
3. recommendation_rank: If mentioned, what is its position in the list (1, 2, 3...)? If not mentioned, null.
4. accuracy_score: How accurately did the model describe the company's offerings? (0.0 to 1.0)
5. sentiment: What is the tone regarding this company? (Positive, Neutral, Negative)
6. competitors_mentioned: List other companies mentioned in the same response.

Return valid JSON:
{{
  "brand_present": bool,
  "url_cited": bool,
  "recommendation_rank": int or null,
  "accuracy_score": float,
  "sentiment": "Positive|Neutral|Negative",
  "competitors_mentioned": ["name1", "name2"]
}}
"""
        try:
            # We use the base model for evaluation to keep it fast and separate from search results
            eval_ai = BASE_MODEL.generate_content(
                eval_prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            eval_data = json.loads(eval_ai.text)
            
            # Handle list response if model returns it wrapped
            if isinstance(eval_data, list) and len(eval_data) > 0:
                eval_data = eval_data[0]
                
            if isinstance(eval_data, dict):
                metric = EvaluationMetric(**eval_data)
            else:
                raise ValueError(f"Expected dict but got {type(eval_data)}")
                
        except Exception as e:
            print(f"[ERROR] Evaluation parsing failed: {e}")
            print(f"[DEBUG] Raw eval response: {eval_ai.text if 'eval_ai' in locals() else 'N/A'}")
            metric = EvaluationMetric(
                brand_present=company.company_name.lower() in response_text.lower() if company.company_name else False,
                recommendation_rank=None,
                accuracy_score=0.0,
                sentiment="Neutral",
                competitors_mentioned=[]
            )

        model_results.append(ModelResponse(
            model_name="Google AI Search" if use_google_search else GEMINI_MODEL_NAME,
            response_text=response_text, # Return FULL text now
            evaluation=metric
        ))

    # 3. Calculate Overall Visibility Score
    mentions = sum(1 for r in model_results if r.evaluation.brand_present)
    avg_accuracy = sum(r.evaluation.accuracy_score for r in model_results) / len(model_results) if model_results else 0
    
    overall_score = (mentions / len(prompts) * 70) + (avg_accuracy * 30) if prompts else 0

    return VisibilityReport(
        company_name=company.company_name,
        overall_score=round(overall_score, 2),
        queries_tested=[p.prompt_text for p in prompts],
        model_results=model_results,
        key_findings=[
            f"Brand mention rate: {mentions}/{len(prompts)}",
            f"Average information accuracy: {round(avg_accuracy * 100, 1)}%"
        ],
        optimizer_tips=[
            "Optimize technical blog posts for long-tail search queries.",
            "Ensure company name and product names are consistent across external profiles.",
            "Increase presence on industry directory sites to improve LLM training data visibility."
        ]
    )
