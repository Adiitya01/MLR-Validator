# app/schemas.py

from pydantic import BaseModel, Field
from typing import List, Optional

class CompanyUnderstanding(BaseModel):
    company_name: str = Field("Pending Analysis...", description="Name of the company extracted")
    company_summary: str = Field("We couldn't extract enough details. Please add more Manual Points.")
    industry: str = Field("Industry: Undefined")
    offerings: List[str] = Field(default_factory=list)
    target_users: List[str] = Field(default_factory=list)
    core_problems_solved: List[str] = Field(default_factory=list)
    manual_points: Optional[str] = None

class GeneratedPrompt(BaseModel):
    prompt_text: str
    intent_category: str  # e.g., Unbiased Discovery, Direct Comparison, Specific Solution

class EvaluationMetric(BaseModel):
    brand_present: bool
    url_cited: bool = Field(False, description="Whether the company URL is cited/linked in the response")
    recommendation_rank: Optional[int] = None  # 1 if first, 2 if second, etc. None if not present
    accuracy_score: float  # 0 to 1
    sentiment: str  # Positive, Neutral, Negative
    competitors_mentioned: List[str]

class ModelResponse(BaseModel):
    model_name: str
    response_text: str
    evaluation: EvaluationMetric

class VisibilityReport(BaseModel):
    company_name: str
    overall_score: float  # 0 to 100
    queries_tested: List[str]
    model_results: List[ModelResponse]
    key_findings: List[str]
    optimizer_tips: List[str]

