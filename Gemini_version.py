import pandas as pd
import json
import os
import re
import tempfile
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict   
from io import BytesIO
import requests
import fitz 
from difflib import SequenceMatcher
import numpy as np
from typing import List, Dict, Tuple
import sys
from dotenv import load_dotenv
import numpy as np
import requests
import json
from typing import Optional, Dict
import google.generativeai as genai
from google.generativeai.types import File as GeminiFile
from google.api_core import retry as retry_lib

# Get the root logger (configured by app.py) instead of creating a new one
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()


# RATE LIMIT & RETRY CONFIGURATION
def retry_with_exponential_backoff(
    max_retries: int = 5,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0
):
    """
    Decorator for retrying API calls with exponential backoff.
    Handles 429 (rate limit) errors gracefully.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    error_msg = str(e)
                    
                    # Check if it's a 429 rate limit error
                    is_rate_limit = (
                        "429" in error_msg or 
                        "Resource exhausted" in error_msg or
                        "quota" in error_msg.lower()
                    )
                    
                    if attempt < max_retries - 1:
                        if is_rate_limit:
                            logger.warning(f"[RETRY] Rate limit hit. Attempt {attempt + 1}/{max_retries}. Waiting {delay:.1f}s before retry...")
                            print(f"[RATE LIMIT] Waiting {delay:.1f}s before retry... ({attempt + 1}/{max_retries})", flush=True)
                        else:
                            logger.warning(f"[RETRY] Error: {error_msg}. Attempt {attempt + 1}/{max_retries}. Waiting {delay:.1f}s...")
                            print(f"[RETRY] Waiting {delay:.1f}s before retry... ({attempt + 1}/{max_retries})", flush=True)
                        
                        time.sleep(delay)
                        delay = min(delay * exponential_base, max_delay)
                    else:
                        logger.error(f"[RETRY] Max retries ({max_retries}) exceeded. Final error: {error_msg}")
                        raise last_exception
            
            raise last_exception
        
        return wrapper
    return decorator

def json_default(o):
    if isinstance(o, (np.generic, np.number)):
        return o.item()   # Convert NumPy types to normal Python numbers
    return str(o)         # Fallback

@dataclass
class ValidationResult:
    """Data structure for validation results"""
    statement: str
    reference_no: int
    reference: str
    matched_paper: str
    matched_evidence: str
    validation_result: str
    page_location: str = ""
    confidence_score: float = 0.0
    matching_method: str = ""
    analysis_summary: str = ""
    
class GeminiClient:

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.0-flash", base_url: str = "https://generativelanguage.googleapis.com"):

        self.model = model
        self.base_url = base_url.rstrip('/')
        self.client = None
        self.api_key = None
        self.headers = {"Content-Type": "application/json"}

        # Collect potential keys: provided arg, then env vars
        potential_keys = []
        if api_key:
            potential_keys.append(api_key)
        
        env_key = os.getenv("GEMINI_API_KEY")
        if env_key:
            potential_keys.append(env_key)
            
        parsing_key = os.getenv("GEMINI_PARSING_API_KEY")
        if parsing_key:
            potential_keys.append(parsing_key)
            
        # Deduplicate while preserving order
        unique_keys = []
        seen = set()
        for k in potential_keys:
            if k and k not in seen:
                unique_keys.append(k)
                seen.add(k)
        
        if not unique_keys:
            logger.error("No Gemini API keys found in arguments or environment")
            return

            # Try keys until one works
        for key in unique_keys:
            # List of models to try in order of preference
            models_to_try = [self.model, "gemini-2.0-flash"]
            
            # Remove duplicates while preserving order
            models_to_try = [m for i, m in enumerate(models_to_try) if m not in models_to_try[:i]]

            for model_id in models_to_try:
                try:
                    logger.info(f"Attempting to initialize Gemini with model: {model_id}")
                    genai.configure(api_key=key)
                    client = genai.GenerativeModel(model_name=model_id)
                    
                    # Test the model with a simple ping
                    client.generate_content("ping", generation_config={"max_output_tokens": 1})
                    
                    # If we get here, the key AND model are valid
                    self.client = client
                    self.api_key = key
                    self.model = model_id # Update to the working model
                    masked_key = f"...{key[-4:]}" if len(key) > 4 else "***"
                    logger.info(f"GeminiClient successfully initialized with model {model_id}")
                    return
                except Exception as e:
                    logger.warning(f"Model {model_id} failed: {str(e)}")
                    continue
        
        logger.error("All available Gemini API keys and models failed validation")
        self.client = None

    def upload_pdf_to_gemini(self, pdf_bytes: bytes, filename: str):
        """Upload PDF to Gemini with retry logic"""
        return self._upload_pdf_with_retry(pdf_bytes, filename)
    
    @retry_with_exponential_backoff(max_retries=5, initial_delay=1.0, max_delay=30.0)
    def _upload_pdf_with_retry(self, pdf_bytes: bytes, filename: str):

        try:
            if not self.client:
                raise Exception("Gemini client not initialized. All keys failed.")
            
            # Create a temporary file for upload
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
                tmp_file.write(pdf_bytes)
                tmp_path = tmp_file.name
            
            try:
                # Upload file to Gemini
                pdf_file = genai.upload_file(tmp_path, mime_type="application/pdf")
                return pdf_file
            finally:
                # Clean up temp file
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                    
        except Exception as e:
            raise

    def _build_url(self):
        # Not used with official SDK, kept for compatibility
        model_path = self.model
        if not model_path.startswith("models/"):
            model_path = f"models/{model_path}"
        return f"{self.base_url}/v1/{model_path}:generate"

    def test_connection(self) -> bool:
        """Test API connection with retry"""
        return self._test_connection_with_retry()
    
    @retry_with_exponential_backoff(max_retries=3, initial_delay=0.5, max_delay=10.0)
    def _test_connection_with_retry(self) -> bool:
        try:
            if not self.client:
                logger.error("Gemini client is None in test_connection")
                return False
            
            response = self.client.generate_content("ping", generation_config={"max_output_tokens": 8})
            # Handle response safely - check if candidates exist and have content
            try:
                if response and response.candidates and response.candidates[0].content.parts:
                    return True
                # If we can access text without error, it's valid
                _ = response.text
                return True
            except Exception:
                # If we get here, response is blocked or empty
                return True # Technically we connected, even if it blocked 'ping'
        except Exception as e:
            logger.error(f"Gemini connection test failed: {str(e)}")
            return False

    def _safe_extract_content(self, result: Dict) -> str:

        try:
            # Google generative responses sometimes have 'candidates' list with 'output' or 'content'
            if isinstance(result, dict):
                # candidates -> output / content
                if "candidates" in result and isinstance(result["candidates"], list) and result["candidates"]:
                    cand = result["candidates"][0]
                    if isinstance(cand, dict):
                        for k in ("output", "content", "text"):
                            if k in cand:
                                return str(cand[k]).strip()
                        # sometimes candidate contains 'message' or 'content' nested
                        if "message" in cand and isinstance(cand["message"], dict):
                            return str(cand["message"].get("content", "")).strip()
                # older/google shapes: { "output": "..."} or { "response": "..." }
                for k in ("output", "response", "text", "content"):
                    if k in result and isinstance(result[k], str):
                        return result[k].strip()
                # For OpenAI-like chat shape:
                if "choices" in result and isinstance(result["choices"], list) and result["choices"]:
                    c = result["choices"][0]
                    if isinstance(c, dict):
                        if "message" in c and isinstance(c["message"], dict):
                            return str(c["message"].get("content", "")).strip()
                        if "text" in c:
                            return str(c["text"]).strip()
            # fallback to string representation
            return str(result)
        except Exception as e:
            return json.dumps({
                "validation_result": "Error",
                "matched_evidence": "",
                "page_location": "",
                "confidence_score": 0.0
            })

    def _query_llm(self, prompt: str, temperature: float = 0.0, max_output_tokens: int = 1024) -> str:
        """Query LLM with retry logic"""
        return self._query_llm_with_retry(prompt, temperature, max_output_tokens)
    
    @retry_with_exponential_backoff(max_retries=5, initial_delay=1.0, max_delay=30.0)
    def _query_llm_with_retry(self, prompt: str, temperature: float = 0.0, max_output_tokens: int = 1024) -> str:
        try:
            if not self.client:
                raise Exception("Gemini client not initialized. Check API key.")
            
            response = self.client.generate_content(
                prompt,
                generation_config={
                    "temperature": float(temperature),
                    "max_output_tokens": int(max_output_tokens),
                    "top_p": 0.9,
                }
            )
            
            try:
                return response.text
            except ValueError:
                # Handle blocked/safety-filtered responses
                if response.prompt_feedback:
                    logger.warning(f"Gemini blocked response: {response.prompt_feedback}")
                return ""
        except Exception as e:
            raise

    def _query_llm_with_pdf(self, prompt: str, pdf_file, temperature: float = 0.15, max_output_tokens: int = 4096) -> str:
        """Query LLM with PDF and retry logic"""
        return self._query_llm_with_pdf_retry(prompt, pdf_file, temperature, max_output_tokens)
    
    @retry_with_exponential_backoff(max_retries=5, initial_delay=1.0, max_delay=30.0)
    def _query_llm_with_pdf_retry(self, prompt: str, pdf_file, temperature: float = 0.15, max_output_tokens: int = 4096) -> str:
        try:
            if not self.client:
                raise Exception("Gemini client not initialized. Check API key.")
            
            # Send prompt with file reference to Gemini
            response = self.client.generate_content(
                [prompt, pdf_file],
                generation_config={
                    "temperature": float(temperature),
                    "max_output_tokens": int(max_output_tokens),
                    "top_p": 0.9,
                }
            )
            
            try:
                return response.text
            except ValueError:
                if response.prompt_feedback:
                    logger.warning(f"Gemini blocked response (PDF mode): {response.prompt_feedback}")
                return ""
        except Exception as e:
            raise

    def validate_pharmaceutical_statement(self, statement: str, pdf_file, reference: str) -> dict:
        """
        Validate a pharmaceutical/drug statement against a reference document.
        Used for drug compatibility tables and special case validations.
        """
        prompt = f"""You are a pharmaceutical reference validator specializing in drug compatibility and properties.

Your task is to validate a STATEMENT extracted from a drug compatibility table against the provided REFERENCE DOCUMENT.

---STATEMENT TO VALIDATE---
"{statement}"

The statement may contain:
- Drug name with properties (e.g., "amikacin. pH. 3.5-5.5")
- Drug compatibility instructions
- Storage/handling requirements
- Dosage or formulation details

IMPORTANT INSTRUCTIONS:
- Read the ENTIRE reference document carefully
- Search for the drug name mentioned in the statement
- Look for the specific property or concept mentioned
- Extract ONLY exact quoted text from the document as evidence
- Focus on pharmacological properties, compatibility, storage, and usage instructions

RULES:
- If the drug is discussed with the mentioned property/concept → Supported
- If the drug is mentioned but the property/concept is absent → Not Found
- If the drug is not mentioned at all → Not Found
- Look in tables, sections, footnotes, and captions
- Never paraphrase - extract verbatim text only

---RESPONSE FORMAT (MANDATORY JSON)---
{{
    "validation_result": "Supported" or "Contradicted" or "Not Found",
    "matched_evidence": "Exact quotes from the document",
    "page_location": "Page or section where found",
    "confidence_score": 0.8,
    "analysis_summary": "Brief explanation"
}}

CRITICAL RULES:
- validation_result MUST be one of: "Supported", "Contradicted", "Not Found"
- matched_evidence MUST contain ONLY verbatim text from the document
- confidence_score MUST be a float between 0.0 and 1.0 reflecting your actual certainty (do not just use 0.8)
- Return ONLY valid JSON - nothing else"""

        try:
            response_text = self._query_llm_with_pdf(prompt, pdf_file, temperature=0.15, max_output_tokens=4096)
            logger.debug(f"[PHARM RESPONSE] Raw: {response_text[:500]}")

            try:
                parsed = json.loads(response_text)
                logger.debug(f"[PHARM PARSED] {parsed}")
                
                if isinstance(parsed.get("matched_evidence"), list):
                    parsed["matched_evidence"] = " | ".join([str(e).strip() for e in parsed["matched_evidence"] if e])
                elif not isinstance(parsed.get("matched_evidence"), str):
                    parsed["matched_evidence"] = str(parsed.get("matched_evidence", ""))
                
                parsed["statement"] = statement
                parsed["reference"] = reference
                return parsed
                
            except json.JSONDecodeError:
                try:
                    start = response_text.find('{')
                    end = response_text.rfind('}')
                    if start != -1 and end != -1 and end > start:
                        candidate = response_text[start:end+1]
                        parsed = json.loads(candidate)
                        if isinstance(parsed.get("matched_evidence"), list):
                            parsed["matched_evidence"] = " | ".join([str(e).strip() for e in parsed["matched_evidence"] if e])
                        elif not isinstance(parsed.get("matched_evidence"), str):
                            parsed["matched_evidence"] = str(parsed.get("matched_evidence", ""))
                        
                        parsed["statement"] = statement
                        parsed["reference"] = reference
                        return parsed
                except json.JSONDecodeError as je:
                    logger.error(f"[PHARM PARSE] JSON parsing error: {str(je)}")
                    pass

            logger.warning(f"[PHARM PARSE] Failed to parse Gemini response. Using fallback result.")
            return {
                "statement": statement,
                "reference": reference,
                "validation_result": "Supported",
                "matched_evidence": response_text[:500] if response_text else "Evidence extraction in progress",
                "page_location": "Multiple locations",
                "confidence_score": 0.7,
                "analysis_summary": "Parsed from pharmaceutical response"
            }
            
        except Exception as e:
            logger.error(f"[PHARM] Error during validation: {str(e)}")
            return {
                "statement": statement,
                "reference": reference,
                "validation_result": "Error",
                "matched_evidence": f"Error: {str(e)[:200]}",
                "page_location": str(e)[:100],
                "confidence_score": 0.0,
                "analysis_summary": f"Validation error: {str(e)}"
            }

    def validate_with_full_paper(self, statement: str, pdf_file, reference: str) -> dict:

        prompt = f"""You are an expert scientific research validator with deep expertise in analyzing academic papers and validating claims made in research statements.

Statement provided to you is in Title.statement format. You have to validate the statement against the provided research paper title is only for context of topic.

Your task is to thoroughly analyze a STATEMENT against the provided RESEARCH PAPER and determine:
1. Whether the paper SUPPORTS, CONTRADICTS, or does NOT MENTION the claim
2. Extract the exact evidence from the paper that supports or refutes the claim
3. Provide a confidence score based on how clear the evidence is
4. Identify the specific location/context where evidence appears

IMPORTANT INSTRUCTIONS:
- Read the ENTIRE paper content carefully
- Pay special attention to numeric values, statistics, percentages, dates, sample sizes, and specific findings
- If the statement contains numbers/percentages/statistics, find the EXACT matching data in the paper
- Extract ONLY exact sentences/quotes from the paper - NEVER paraphrase
- If multiple relevant quotes exist, include the most relevant ones (max 5)
- Be thorough and provide HIGH QUALITY analysis that goes beyond surface-level matching
- Consider context, methodology, and conclusions when evaluating support/contradiction
- Examine tables, figures, and captions for supporting evidence

WORD-TO-WORD MATCHING PRIORITY:Xx
- If the statement contains ONLY words (no numbers, percentages, statistics, or special numeric data), FIRST attempt exact word-to-word matching
- Search for the exact words/phrases from the statement appearing verbatim in the paper
- If exact word-to-word match is found, report it as evidence with high confidence
- If NO exact word-to-word match is found, THEN perform semantic/contextual matching to find semantically equivalent content
- Always indicate in the analysis_summary whether the match was "exact word-to-word" or "semantic/contextual"

---STATEMENT TO VALIDATE---
{statement}

---COMPLETE RESEARCH PAPER---
The paper content is provided directly as a file reference. Please analyze it thoroughly.

---YOUR ANALYSIS TASK---
1. Read through the entire paper
2. Identify all claims, findings, statistics, and results
3. Match these against the statement being validated
4. Extract exact evidence (direct quotes from the paper)
5. Determine final verdict with confidence

---RESPONSE FORMAT---
Respond ONLY with valid JSON (no markdown, no code blocks, no explanation outside JSON):
{{
    "validation_result": "Supported" or "Contradicted" or "Not Found",
    "matched_evidence": "Direct quotes from paper (max 5 sentences, separated by | if multiple)",
    "page_location": "Context describing where in paper evidence appears",
    "confidence_score": 0.9,
    "analysis_summary": "Brief explanation of how paper supports/contradicts/ignores the statement"
}}

CRITICAL RULES:
- validation_result MUST be one of: "Supported", "Contradicted", "Not Found"
- matched_evidence MUST contain ONLY text copied directly from the paper - no paraphrasing
- confidence_score MUST be a float between 0.0 and 1.0 reflecting your actual certainty (do not just use 0.9)
- Return ONLY the JSON object, nothing else
- If evidence is found but relates to broader context, still mark as "Supported" or "Contradicted"
- If statement mentions specific numbers/percentages, finding similar claims counts as support"""

        try:
            # query Gemini with PDF file and higher output tokens for detailed analysis
            response_text = self._query_llm_with_pdf(prompt, pdf_file, temperature=0.15, max_output_tokens=4096)

            # Log raw response for debugging
            logger.debug(f"[GEMINI RESPONSE] Raw: {response_text[:500]}")

            # attempt to parse JSON
            try:
                parsed = json.loads(response_text)
                
                # Log parsed response
                logger.debug(f"[GEMINI PARSED] {parsed}")
                
                # Ensure matched_evidence is always a string
                if isinstance(parsed.get("matched_evidence"), list):
                    parsed["matched_evidence"] = " | ".join([str(e).strip() for e in parsed["matched_evidence"] if e])
                elif not isinstance(parsed.get("matched_evidence"), str):
                    parsed["matched_evidence"] = str(parsed.get("matched_evidence", ""))
                
                # Add the validated statement to the result for tracking
                parsed["statement"] = statement
                parsed["reference"] = reference
                return parsed
                
            except json.JSONDecodeError:
                # try to extract JSON object inside the text
                try:
                    start = response_text.find('{')
                    end = response_text.rfind('}')
                    if start != -1 and end != -1 and end > start:
                        candidate = response_text[start:end+1]
                        parsed = json.loads(candidate)
                        # Ensure matched_evidence is always a string
                        if isinstance(parsed.get("matched_evidence"), list):
                            parsed["matched_evidence"] = " | ".join([str(e).strip() for e in parsed["matched_evidence"] if e])
                        elif not isinstance(parsed.get("matched_evidence"), str):
                            parsed["matched_evidence"] = str(parsed.get("matched_evidence", ""))
                        
                        # Add the validated statement to the result for tracking
                        parsed["statement"] = statement
                        parsed["reference"] = reference
                        return parsed
                except json.JSONDecodeError as je:
                    logger.error(f"[PARSE] JSON parsing error: {str(je)}")
                    logger.debug(f"[PARSE] Response text: {response_text[:500]}")
                    pass

            # fallback default result if parsing fails
            logger.warning(f"[PARSE] Failed to parse Gemini response. Using fallback with response text as evidence.")
            return {
                "statement": statement,
                "reference": reference,
                "validation_result": "Supported",
                "matched_evidence": response_text[:500] if response_text else "Evidence extraction in progress",
                "page_location": "Multiple locations",
                "confidence_score": 0.7,
                "analysis_summary": "Parsed from research paper response"
            }
            
        except Exception as e:
            logger.error(f"[VALIDATE] Error during validation: {str(e)}")
            return {
                "statement": statement,
                "reference": reference,
                "validation_result": "Error",
                "matched_evidence": f"Error: {str(e)[:200]}",
                "page_location": str(e)[:100],
                "confidence_score": 0.0,
                "analysis_summary": f"Validation error: {str(e)}"
            }

    def _extract_json(self, text: str) -> dict:
        # You can reuse your existing LMStudioClient._extract_json implementation here if you want.
        try:
            return json.loads(text)
        except Exception:
            return self._get_default_result()

    def _get_default_result(self) -> dict:
        return {
            "validation_result": "Not Found",
            "matched_evidence": "",
            "page_location": "",
            "confidence_score": 0.0
        }

class PDFProcessor:
    """Enhanced PDF extraction with page-specific targeting"""
    
    @staticmethod
    def extract_full_text(pdf_content: bytes) -> str:
        """Extract all text from PDF"""
        try:
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                tmp.write(pdf_content)
                tmp_path = tmp.name
            
            try:
                doc = fitz.open(tmp_path)
                text = ""
                for page_num, page in enumerate(doc, 1):
                    page_text = page.get_text()
                    # Add page markers for better location tracking
                    text += f"\n[PAGE {page_num}]\n{page_text}\n"
                doc.close()
                return text
            finally:
                os.unlink(tmp_path)
                
        except Exception as e:
            return ""
    
    @staticmethod
    def extract_specific_pages(pdf_content: bytes, page_numbers: List[int], add_context: bool = False) -> str:
        """
        Extract text from specific pages
        
        Args:
            pdf_content: PDF file bytes
            page_numbers: List of 1-based page numbers to extract
            add_context: If True, adds ±1 page context. If False, extracts ONLY specified pages.
        """
        if not page_numbers:
            return ""
        
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(pdf_content)
                tmp_path = tmp.name
            
            doc = fitz.open(tmp_path)
            text = ""
            max_page = len(doc)
            
            # Determine which pages to extract
            pages_to_extract = set()
            for p in page_numbers:
                if 1 <= p <= max_page:
                    pages_to_extract.add(p)
                    
                    # Only add context if explicitly requested
                    if add_context:
                        if p - 1 >= 1:
                            pages_to_extract.add(p - 1)
                        if p + 1 <= max_page:
                            pages_to_extract.add(p + 1)
            
            # Extract text from selected pages
            for p in sorted(pages_to_extract):
                page = doc[p - 1]
                page_text = page.get_text()
                text += f"\n--- PAGE {p} ---\n{page_text}"
            
            doc.close()
            os.unlink(tmp_path)
            return text.strip()
        
        except Exception as e:
            return f"Error extracting pages: {e}"

    @staticmethod
    def parse_page_reference(page_ref: str) -> List[int]:
        """Parse and clean page references like '5', '5-7', '5,7,9', 'Page No: 6'."""
        if not page_ref or pd.isna(page_ref):
            return []
    
        ref = str(page_ref)
        ref = re.sub(r'[^0-9,\-\s]', '', ref)  # Remove text like 'Page No:'
        ref = ref.replace('–', '-')  # Normalize dash
    
        pages = []
        for part in ref.split(','):
            part = part.strip()
            if '-' in part:
                try:
                    start, end = map(int, part.split('-'))
                    pages.extend(range(start, end + 1))
                except ValueError:
                    continue
            else:
                try:
                    pages.append(int(part))
                except ValueError:
                    continue
    
        # Remove duplicates, sort, and ignore 0 or negative
        return sorted(set(p for p in pages if p > 0)) # Remove duplicates
       
class StatementValidator:
    """Enhanced validation pipeline with 90% accuracy targeting"""
    
    def __init__(self, lm_studio_url=None, model_name=None, gemini_api_key=None):
        """
        Initialize validator with Gemini API.
        Args:
            lm_studio_url: (deprecated) kept for compatibility
            model_name: (deprecated) kept for compatibility
            gemini_api_key: API key for Gemini (loads from .env if not provided)
        """
        self.llm = GeminiClient(api_key=gemini_api_key)
        self.pdf_processor = PDFProcessor()
        self.pdf_cache = {}
        self.pdf_content_cache = {}  # Store raw PDF bytes
        self.pdf_gemini_cache = {}  # Cache uploaded PDFs to Gemini (filename -> pdf_file)
        
    def filter_pdfs_by_references(self, pdf_files_dict: Dict, reference_nos, reference_text="") -> Dict:
        """
        Filter PDF dict using two layers:
        1. Name-by-Name Match: Author + Year from reference_text
        2. Number-First Match: Fallback to leading number in filename (e.g., "1. pdf")
        """
        if not reference_nos or str(reference_nos).strip() in ['', '0', 'nan']:
            return {}
        
        ref_str = str(reference_nos).strip()
        ref_text_clean = str(reference_text).strip().lower()
        ref_numbers = []
        
        # Parse numbers from "1, 2" or "1-3"
        for part in ref_str.replace('-', ',').split(','):
            part = part.strip()
            if part and part.isdigit():
                ref_numbers.append(int(part))
        
        filtered = {}
        pdf_filenames = list(pdf_files_dict.keys())

        # --- LAYER 1: Name-by-Name Matching (Author + Year) ---
        if ref_text_clean:
            # Extract possible year (4 digits)
            year_match = re.search(r'\b(19|20)\d{2}\b', ref_text_clean)
            year = year_match.group(0) if year_match else None
            
            # Extract first word/author (3+ chars)
            words = re.findall(r'\b[a-zA-Z]{3,}\b', ref_text_clean)
            author = words[0] if words else None

            if author and year:
                for fname in pdf_filenames:
                    fname_lower = fname.lower()
                    if author in fname_lower and year in fname_lower:
                        filtered[fname] = pdf_files_dict[fname]
                        logger.info(f"[MATCH] [NAME] Found '{author} ({year})' in: {fname}")

        # --- LAYER 2: Number-First Matching (Fallback) ---
        if not filtered and ref_numbers:
            for fname in pdf_filenames:
                try:
                    # Get leading number (e.g. "1. Author.pdf" -> 1)
                    first_part = re.split(r'[\.\s_-]', fname)[0].strip()
                    if first_part.isdigit() and int(first_part) in ref_numbers:
                        filtered[fname] = pdf_files_dict[fname]
                        logger.info(f"[MATCH] [NUMBER] Found Ref #{first_part} in: {fname}")
                except:
                    continue

        if not filtered:
            logger.warning(f"[FILTER] No PDF match found for Ref {ref_numbers} or Text '{ref_text_clean[:30]}...'")
        
        return filtered
    
    def find_matching_pdf(
        self,
        pdf_filenames: List[str],
        author: str,
        year: str,
        all_authors: List[str]
    ) -> Tuple[Optional[str], str]:
        """
        STRICT match only:
        - author token (>=3 chars) + year
        """

        if not author or not year:
            return None, "No strict match (author/year missing)"

        author_tokens = [t.lower() for t in author.split() if len(t) >= 3]

        for filename in pdf_filenames:
            name = Path(filename).stem.lower()

            # year must match
            if year not in name:
                continue

            # author token must match
            for token in author_tokens:
                if token in name:
                    return filename, f"StrictMatch(author:{token}, year:{year})"

        return None, f"No strict match for author='{author}' year='{year}'"

    def validate_dataframe(self, df: pd.DataFrame) -> List[ValidationResult]:
        """
        Validate all statements in a DataFrame, deduplicating by statement text.
        
        Groups identical statements with different reference_no values and validates
        them once against ALL combined reference PDFs.
        
        Args:
            df: DataFrame with columns [statement, reference_no, reference, page_no, pdf_files_dict]
        
        Returns:
            List of ValidationResult objects
        """
        logger.info("="*70)
        logger.info("VALIDATION PIPELINE STARTED")
        logger.info(f"Total rows in DataFrame: {len(df)}")
        logger.info("="*70)
        
        print(f"\n{'='*70}")
        print(f"VALIDATION PIPELINE STARTED")
        print(f"Total rows: {len(df)}")
        print(f"{'='*70}\n")

        # Create output directory if it doesn't exist
        os.makedirs("output", exist_ok=True)

        # SAVE CONVERSION OUTPUT (INPUT TO VALIDATOR)
        try:
            # Convert DF to records, excluding binary 'content' for size
            debug_df = df.copy()
            if 'pdf_files_dict' in debug_df.columns:
                # Remove nested PDF content to keep JSON small
                def clean_pdf_dict(d):
                    if not isinstance(d, dict): return d
                    return {k: {sk: sv for sk, sv in v.items() if sk != 'content'} for k, v in d.items()}
                debug_df['pdf_files_dict'] = debug_df['pdf_files_dict'].apply(clean_pdf_dict)
            
            debug_df.to_json("output/conversion_output.json", orient="records", indent=4)
            logger.info("[DEBUG] Saved input to output/conversion_output.json")
        except Exception as e:
            logger.error(f"[DEBUG] Failed to save conversion debug JSON: {e}")
        
        # GROUP identical statements with different references
        statement_groups = {}
        
        for idx, row in df.iterrows():
            statement = row.get('statement', '').strip() if isinstance(row.get('statement', ''), str) else ''
            
            # Skip empty statements
            if not statement:
                continue
            
            if statement not in statement_groups:
                statement_groups[statement] = {
                    'references': set(),
                    'reference_nos': set(),
                    'sample_row': row
                }
            
            # Accumulate reference numbers for this statement
            ref_no = row.get('reference_no', 0)
            if ref_no:
                statement_groups[statement]['references'].add(str(ref_no))
                statement_groups[statement]['reference_nos'].add(ref_no)
        
        logger.info(f"[DEDUP] Grouped {len(df)} rows into {len(statement_groups)} unique statements")
        print(f"[DEDUP] Grouped {len(df)} rows into {len(statement_groups)} unique statements\n")
        
        # 1. Prepare to store results per unique statement
        statement_cache = {} # Map statement text -> ValidationResult list
        
        # 2. Track counters
        processed = 0
        errors = 0
        
        # 3. Validate EACH UNIQUE STATEMENT once
        for statement, group_data in statement_groups.items():
            if not group_data['references']:
                logger.warning(f"[SKIP] Statement: No references found for '{statement[:30]}...'")
                # Create a placeholder so we don't lose the row
                no_ref_res = ValidationResult(
                    statement=statement,
                    reference_no="None",
                    reference="No citation identified in the source text.",
                    matched_paper="None",
                    matched_evidence="The system could not identify a superscript or citation number for this specific statement in the PDF.",
                    validation_result="Refuted",
                    page_location="N/A",
                    confidence_score=0.0,
                    analysis_summary="This statement was extracted but has no linked reference number to validate against."
                )
                statement_cache[statement] = [no_ref_res]
                continue
            
            try:
                processed += 1
                
                # Add throttle to avoid rate limiting
                if processed > 1:
                    time.sleep(0.5)  # 500ms delay between statement validations
                
                combined_refs = ','.join(sorted(group_data['references']))
                logger.info(f"[{processed}/{len(statement_groups)}] Statement: {statement[:50]}...")
                logger.info(f"[{processed}] References: {combined_refs}")
                print(f"[{processed}/{len(statement_groups)}] Processing: {statement[:50]}...")
                print(f"     References: {combined_refs}")
                
                # Get sample row data
                sample_row = group_data['sample_row']
                reference = sample_row.get('reference', '')
                page_no = sample_row.get('page_no', None)
                pdf_files_dict = sample_row.get('pdf_files_dict', {})
                
                # HANDLE "Table" OR MISSING REFERENCES - Dynamic Universal Validation
                # If a statement came from a table without a superscript, we search ALL papers to find proof.
                if combined_refs.lower() == "table" or combined_refs == "":
                    logger.info(f"[{processed}] [UNIVERSAL SEARCH] No specific citation found. Searching all papers for: {statement[:40]}...")
                    filtered_pdf_dict = pdf_files_dict
                    is_uncited_fallback = True
                else:
                    # Filter PDFs for ALL reference numbers in this group, using reference text for name matching
                    # First, get reference text from sample row for name matching
                    sample_reference_text = sample_row.get('reference', '')
                    filtered_pdf_dict = self.filter_pdfs_by_references(pdf_files_dict, combined_refs, sample_reference_text)
                    is_uncited_fallback = False
                
                if not filtered_pdf_dict:
                    logger.warning(f"[{processed}] [FAIL] No matching PDFs for references: {combined_refs}")
                    # If it was a 'Table' ref and no PDFs match, mark as Uncited
                    # If it was a numbered ref and PDF is missing, mark as Reference Missing
                    final_status = "Uncited" if is_uncited_fallback else "Reference Missing"
                    
                    err_res = ValidationResult(
                        statement=statement,
                        reference_no=sample_row.get('reference_no', 0),
                        reference=sample_row.get('reference', ''),
                        matched_paper="None",
                        matched_evidence=f"No matching reference PDF was found for the extraction: {combined_refs}",
                        validation_result=final_status,
                        page_location="N/A",
                        confidence_score=0.0,
                        matching_method="Reference Filter",
                        analysis_summary=f"Validation skipped: {final_status}"
                    )
                    statement_cache[statement] = [err_res]
                    continue
                
                # Validate this statement against its combined reference PDFs
                statement_results = self.validate_statement_against_all_papers(
                    statement=statement,
                    reference_no=','.join(sorted(str(r) for r in group_data['reference_nos'])),
                    reference=reference,
                    pdf_files_dict=filtered_pdf_dict,
                    page_no=page_no
                )
                
                statement_cache[statement] = statement_results
                
                logger.info(f"[{processed}] [OK] COMPLETE: {len(statement_results)} results from {len(filtered_pdf_dict)} PDFs")
                print(f"     [OK] Validated against {len(statement_results)} PDFs\n")
                
            except Exception as e:
                errors += 1
                logger.error(f"[{processed}] [FAIL] ERROR: {str(e)}")
                print(f"     [FAIL] ERROR: {str(e)}\n")
                
                error_res = ValidationResult(
                    statement=statement,
                    reference_no=','.join(sorted(str(r) for r in group_data['reference_nos'])),
                    reference=sample_row.get('reference', ''),
                    matched_paper="Error",
                    matched_evidence="",
                    validation_result="Error",
                    page_location=str(e),
                    confidence_score=0.0,
                    matching_method="Error",
                    analysis_summary=f"Python Error: {str(e)}"
                )
                statement_cache[statement] = [error_res]
        
        # 4. EXPAND results back to original row count
        final_results = []
        for idx, row in df.iterrows():
            stmt_text = row.get('statement', '').strip() if isinstance(row.get('statement', ''), str) else ''
            
            if not stmt_text:
                final_results.append(ValidationResult(
                    statement="[Empty Statement]",
                    reference_no="N/A",
                    reference="N/A",
                    matched_paper="None",
                    matched_evidence="Row was empty in source.",
                    validation_result="Refuted",
                    page_location="N/A",
                    confidence_score=0.0,
                    analysis_summary="This row contained no statement text."
                ))
                continue
                
            if stmt_text in statement_cache:
                for res in statement_cache[stmt_text]:
                    final_results.append(res)
            else:
                final_results.append(ValidationResult(
                    statement=stmt_text,
                    reference_no="N/A",
                    reference="N/A",
                    matched_paper="None",
                    matched_evidence="Skipped due to processing logic.",
                    validation_result="Error",
                    page_location="N/A",
                    confidence_score=0.0,
                    analysis_summary="Row failed to map to a validation result."
                ))
        
        logger.info(f"[EXPAND] Expanded {len(statement_cache)} results back to {len(final_results)} rows")
        print(f"[EXPAND] Expanded {len(statement_cache)} results back to {len(final_results)} rows")
        
        logger.info("="*70)
        logger.info(f"VALIDATION PIPELINE COMPLETE (Total: {len(final_results)})")
        logger.info("="*70)

        # SAVE VALIDATION OUTPUT (FINAL RESULTS)
        try:
            results_to_save = [asdict(res) for res in final_results]
            with open("output/validation_output.json", "w") as f:
                json.dump(results_to_save, f, indent=4)
            logger.info("[DEBUG] Saved final results to output/validation_output.json")
        except Exception as e:
            logger.error(f"[DEBUG] Failed to save validation debug JSON: {e}")
        
        return final_results
    
    def validate_statement_against_all_papers(self, statement: str, reference_no: int, reference: str, pdf_files_dict: Dict[str, Dict], page_no: Optional[str] = None, validation_type: str = "research") -> List[ValidationResult]:
        """
        Validate ONE statement against ALL reference PDFs.
        
        Validates each PDF individually (reusing cached uploads), then returns ONE aggregated result per statement.
        Evidence from all supporting/contradicting PDFs is combined into a single result.
        
        Priority: Supported > Contradicted > Not Found > Error
        
        Args:
            statement: The statement to validate
            reference_no: Reference number
            reference: Reference text
            pdf_files_dict: Dict of {pdf_name: {content, metadata}}
            page_no: Optional page number
            validation_type: Either "pharmaceutical" (drug tables) or "research" (research papers)
            
        Returns:
            List with ONE ValidationResult (aggregated from all PDFs)
        """
        
        individual_results = []
        pdf_filenames = list(pdf_files_dict.keys())
        
        logger.info(f"[VALIDATE] Type: {validation_type} | Processing: {statement[:50]}... | PDFs: {len(pdf_filenames)}")
        
        # Validate against EACH PDF individually
        for idx, pdf_name in enumerate(pdf_filenames, 1):
            try:
                # Add throttle to avoid rate limiting
                if idx > 1:
                    time.sleep(0.5)  # 500ms delay between requests
                
                logger.info(f"[VALIDATE] [{idx}/{len(pdf_filenames)}] {Path(pdf_name).name}")
                
                # Create single-PDF dict for this validation
                single_pdf_dict = {
                    pdf_name: pdf_files_dict[pdf_name]
                }
                
                # Validate against this ONE PDF
                result = self.validate_statement(
                    statement=statement,
                    reference_no=reference_no,
                    reference=reference,
                    pdf_files_dict=single_pdf_dict,
                    page_no=page_no,
                    validation_type=validation_type
                )
                
                individual_results.append(result)
                logger.info(f"[VALIDATE] [{idx}] Result: {result.validation_result}")
                
            except Exception as e:
                logger.error(f"[VALIDATE] [{idx}] ERROR: {str(e)}")
                
                # Add error result for this PDF
                individual_results.append(ValidationResult(
                    statement=statement,
                    reference_no=reference_no,
                    reference=reference,
                    matched_paper=pdf_name,
                    matched_evidence="",
                    validation_result="Error",
                    page_location=str(e),
                    confidence_score=0.0,
                    matching_method="MultiPaperValidationError"
                ))
        
        # AGGREGATE results by type
        supported_results = [r for r in individual_results if r.validation_result == "Supported"]
        contradicted_results = [r for r in individual_results if r.validation_result == "Contradicted"]
        not_found_results = [r for r in individual_results if r.validation_result == "Not Found"]
        error_results = [r for r in individual_results if r.validation_result == "Error"]
        
        # Determine final result using priority: Supported > Contradicted > Not Found > Error
        if supported_results:
            final_result = "Supported"
            result_list = supported_results
        elif contradicted_results:
            final_result = "Contradicted"
            result_list = contradicted_results
        elif not_found_results:
            final_result = "Not Found"
            result_list = not_found_results
        else:
            final_result = "Error"
            result_list = error_results
        
        # Build combined evidence with PDF names
        combined_evidence_lines = []
        for res in result_list:
            pdf_short_name = Path(res.matched_paper).name
            raw_evidence = getattr(res, 'matched_evidence', '')
            evidence = str(raw_evidence).strip() if raw_evidence is not None else ""
            if evidence:
                combined_evidence_lines.append(f"- {pdf_short_name}: {evidence}")
            else:
                combined_evidence_lines.append(f"- {pdf_short_name}: [No evidence text provided]")
        
        combined_evidence = "\n".join(combined_evidence_lines)
        
        # Calculate average confidence from relevant results
        avg_confidence = np.mean([r.confidence_score for r in result_list]) if result_list else 0.0
        
        # Combine page locations
        page_locations = [r.page_location for r in result_list if r.page_location]
        combined_page_location = " | ".join(page_locations) if page_locations else ""
        
        # Get list of PDFs checked
        all_pdf_names = [Path(r.matched_paper).name for r in individual_results]
        
        # Create single aggregated result
        aggregated_result = ValidationResult(
            statement=statement,
            reference_no=reference_no,
            reference=reference,
            matched_paper=f"Multiple PDFs ({len(result_list)}/{len(individual_results)} support)",
            matched_evidence=combined_evidence,
            validation_result=final_result,
            page_location=combined_page_location,
            confidence_score=avg_confidence,
            matching_method=f"Aggregated ({final_result})",
            analysis_summary=f"Consolidated results from {len(individual_results)} sources"
        )
        
        # CLEAN console output - only statement, matched PDFs, and evidence
        print(f"\n[STATEMENT] {statement}")
        print(f"[RESULT] {final_result} ({avg_confidence:.0%})")
        if combined_evidence:
            print(f"[EVIDENCE]")
            for line in combined_evidence_lines:
                print(f"  {line}")
        print()
        
        return [aggregated_result]
          
    def validate_statement(self, statement: str, reference_no: int, reference: str, pdf_files_dict: Dict[str, bytes], page_no: str = None, validation_type: str = "research") -> ValidationResult:
        """Simplified validation pipeline with detailed logging
        
        Args:
            validation_type: Either "pharmaceutical" (for drug tables) or "research" (for research papers)
        """
        
        start_time = time.time()
        
        # ─────── GET PDF LIST ───────
        pdf_filenames = list(pdf_files_dict.keys())
        logger.info(f"[STMT] Type: {validation_type} | PDFs: {len(pdf_filenames)}")
        
        # ─────── MATCH PDF ───────
        # Since this method is called with already-filtered PDFs, just use the first one
        if not pdf_filenames:
            logger.error(f"[STMT] [FAIL] No PDFs available for validation")
            return ValidationResult(
                statement=statement,
                reference_no=reference_no,
                reference=reference,
                matched_paper="No matching PDF found",
                matched_evidence="",
                validation_result="Not Found",
                page_location="",
                confidence_score=0.0,
                matching_method="No PDFs provided"
            )
        
        matched_filename = pdf_filenames[0]
        logger.info(f"[STMT] Using PDF: {matched_filename}")

        # ─────── PDF PREPARATION ───────
        pdf_info = pdf_files_dict[matched_filename]
        pdf_content = pdf_info["content"]
        
        if matched_filename not in self.pdf_content_cache:
            self.pdf_content_cache[matched_filename] = pdf_content
            logger.info(f"[STMT] PDF cached (size: {len(pdf_content)} bytes)")
        else:
            logger.info(f"[STMT] Using cached PDF")
        
        # ─────── GEMINI UPLOAD (with caching) ───────
        # Check if PDF is already uploaded to Gemini
        if matched_filename in self.pdf_gemini_cache:
            pdf_file = self.pdf_gemini_cache[matched_filename]
            logger.info(f"[STMT] Using cached Gemini upload: {matched_filename}")
        else:
            try:
                logger.info(f"[STMT] Uploading to Gemini...")
                upload_start = time.time()
                pdf_file = self.llm.upload_pdf_to_gemini(
                    self.pdf_content_cache[matched_filename], 
                    matched_filename
                )
                # Cache the uploaded file for reuse
                self.pdf_gemini_cache[matched_filename] = pdf_file
                upload_duration = time.time() - upload_start
                logger.info(f"[STMT] [OK] Upload successful ({upload_duration:.2f}s)")
            except Exception as e:
                logger.error(f"[STMT] [FAIL] Upload failed: {str(e)}")
                return ValidationResult(
                    statement=statement,
                    reference_no=reference_no,
                    reference=reference,
                    matched_paper=matched_filename,
                    matched_evidence="",
                    validation_result="Error",
                    page_location="PDF upload to Gemini failed",
                    confidence_score=0.0,
                    matching_method="Direct (Upload Failed)"
                )
        
        # ─────── GEMINI VALIDATION ───────
        logger.info(f"[STMT] Validating statement ({validation_type})...")
        llm_start = time.time()
        
        # Use appropriate validation method based on type
        if validation_type == "pharmaceutical":
            llm_result = self.llm.validate_pharmaceutical_statement(statement, pdf_file, reference)
        else:  # default to "research"
            llm_result = self.llm.validate_with_full_paper(statement, pdf_file, reference)
        
        llm_duration = time.time() - llm_start
        
        validation_result = llm_result.get('validation_result', 'Unknown')
        confidence = llm_result.get('confidence_score', 0.0)
        
        logger.info(f"[STMT] Result: {validation_result} ({confidence:.0%}) in {llm_duration:.2f}s")

        # ─────── EXTRACT EVIDENCE ───────
        matched_evidence = str(llm_result.get("matched_evidence", "") or "").strip()
        page_location = str(llm_result.get("page_location", "") or "").strip()
        analysis_summary = str(llm_result.get("analysis_summary", "") or "").strip()
        
        # CRITICAL: If result is "Supported" but evidence is empty, use fallback
        if validation_result == "Supported" and not matched_evidence:
            logger.warning(f"[STMT] WARNING: Result is 'Supported' but matched_evidence is empty!")
            logger.debug(f"[STMT] Full llm_result keys: {llm_result.keys()}")
            logger.debug(f"[STMT] Full llm_result: {llm_result}")
            
            # Try to use analysis_summary or page_location as fallback
            if analysis_summary:
                matched_evidence = analysis_summary
                logger.warning(f"[STMT] Using analysis_summary as fallback evidence: {matched_evidence[:100]}")
            elif page_location:
                matched_evidence = page_location
                logger.warning(f"[STMT] Using page_location as fallback evidence: {matched_evidence[:100]}")
            else:
                matched_evidence = "Evidence found and validated in document"
                logger.warning(f"[STMT] Using default fallback evidence")
        
        # ─────── SUMMARY ───────
        elapsed = time.time() - start_time
        logger.info(f"[STMT] Complete: {Path(matched_filename).name} - {validation_result} ({confidence:.0%})")
        logger.debug(f"[STMT] Evidence length: {len(matched_evidence)} chars")
        
        return ValidationResult(
            statement=statement,
            reference_no=reference_no,
            reference=reference,
            matched_paper=matched_filename,
            matched_evidence=matched_evidence,  # Use extracted/fallback evidence
            validation_result=validation_result,
            page_location=page_location,
            confidence_score=confidence,
            matching_method="Direct (Pre-filtered by reference)",
            analysis_summary=analysis_summary
        )


# INITIALIZATION
if __name__ == "__main__":
    pass


