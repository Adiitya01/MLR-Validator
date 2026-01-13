from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

from app.website_loader import load_website_content
from app.text_cleaner import clean_text, chunk_text
from app.summarizer import summarize_company
from app.prompt_generator import generate_user_prompts
from app.evaluator import evaluate_visibility
from app.schemas import CompanyUnderstanding, GeneratedPrompt, ModelResponse, VisibilityReport

app = FastAPI(title="GEO Analytics API")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalysisRequest(BaseModel):
    url: Optional[str] = ""
    points: Optional[str] = ""

class AnalysisResponse(BaseModel):
    company_name: str
    industry: str
    prompts: List[GeneratedPrompt]
    company_profile: CompanyUnderstanding # Added to help with evaluation later

class EvaluatePromptRequest(BaseModel):
    company_profile: CompanyUnderstanding
    prompt: GeneratedPrompt
    use_google_search: bool = False

@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_company(request: AnalysisRequest):
    if not request.url and not request.points:
        raise HTTPException(status_code=400, detail="Missing url or points")
    
    try:
        raw_text = ""
        if request.url:
            raw_text = load_website_content(request.url)
        
        clean = clean_text(raw_text)
        chunks = chunk_text(clean)
        
        company_profile = summarize_company(chunks, manual_points=request.points)
        prompts = generate_user_prompts(company_profile)
        
        return AnalysisResponse(
            company_name=company_profile.company_name,
            industry=company_profile.industry,
            prompts=prompts,
            company_profile=company_profile
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/evaluate-prompt", response_model=ModelResponse)
async def evaluate_prompt(request: EvaluatePromptRequest):
    try:
        # evaluate_visibility expects a list, so we wrap it
        report = evaluate_visibility(request.company_profile, [request.prompt], use_google_search=request.use_google_search)
        return report.model_results[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class EvaluateAllRequest(BaseModel):
    company_profile: CompanyUnderstanding
    prompts: List[GeneratedPrompt]
    use_google_search: bool = False

@app.post("/evaluate-all", response_model=VisibilityReport)
async def evaluate_all(request: EvaluateAllRequest):
    try:
        report = evaluate_visibility(request.company_profile, request.prompts, use_google_search=request.use_google_search)
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
