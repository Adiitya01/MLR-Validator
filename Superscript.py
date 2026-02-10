import re
import json
import os
import sys
from typing import List, Optional, Union, Dict
from pydantic import BaseModel, Field, ValidationError
from dotenv import load_dotenv
import fitz  # PyMuPDF
import logging
import time

# Get the root logger
logger = logging.getLogger(__name__)

# Conditional import for Google Gemini
try:
    from google import genai
    from google.genai import types
except ImportError:
    try:
        import google.generativeai as genai
        from google.generativeai import types
    except ImportError:
        pass  # Will be handled by gemini_client

# 1. Configure Gemini API using gemini_client
from gemini_client import configure_gemini

client = configure_gemini("parsing")

# --- Drug Superscript Table Extraction ---
def clean_json_string(s):
    """
    Robustly clean LLM output to extract a valid JSON string.
    """
    if not s: return "[]"
    
    # Clean markdown and whitespace
    s = s.strip()
    if s.startswith("```"):
        m = re.search(r"```(?:json)?\n?(.*?)```", s, re.DOTALL)
        if m:
            s = m.group(1).strip()
        else:
            s = s.strip('`').strip()
    
    # Basic structural repair if needed
    if s.count('{') > s.count('}'):
        s += '}' * (s.count('{') - s.count('}'))
    if s.count('[') > s.count(']'):
        s += ']' * (s.count('[') - s.count(']'))
    
    return s

# --- Pydantic Models ---

class Footnote(BaseModel):
    page: int
    number: Union[int, str]
    text: str

class InlineCitation(BaseModel):
    page_number: int
    superscript_number: str
    heading: Optional[str] = None
    statement: str

class DocumentExtraction(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    footnotes: List[Footnote] = []
    in_text: List[InlineCitation] = []
    references: Dict[str, str] = {}

# --- Reference Extraction Functions ---

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from PDF using PyMuPDF"""
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text("text")
        doc.close()
        return text
    except Exception as e:
        return ""

def clean_references_text(text: str) -> str:
    """Extract only References section and stop at BD footer."""
    start = re.search(r"References\s*(.*)", text, flags=re.IGNORECASE | re.DOTALL)
    if not start:
        return ""
    
    refs_text = start.group(1)

    # Stop at common footer patterns
    stop = re.search(
        r"(BD, the BD Logo|Becton, Dickinson|©|Copyright|All rights reserved)", 
        refs_text, 
        flags=re.IGNORECASE
    )
    if stop:
        refs_text = refs_text[:stop.start()]

    return refs_text.strip()

def extract_references_from_text(text: str) -> Dict[str, str]:
    """Extract references by capturing from each number until the next number."""
    refs_text = clean_references_text(text)
    if not refs_text:
        return {}

    # Pattern to match numbered references (e.g., 1. or 1) or 1-)
    pattern = r"(\d{1,3})[.)]\s+(.*?)(?=\s+\d{1,3}[.)]\s+|$)"
    matches = re.findall(pattern, refs_text, flags=re.DOTALL)

    references = {}
    for num, ref_text in matches:
        # Clean up the reference text
        ref_text = ref_text.replace("\n", " ")
        ref_text = re.sub(r"\s+", " ", ref_text).strip()
        references[num] = ref_text

    return references

# --- Drug Superscript Table Extraction ---

def extract_drug_superscript_table_data(pdf_path: str) -> list:
    """
    Extracts drug superscript and table data for both table types (as described in requirements).
    Processed PAGE-BY-PAGE to avoid output token limits.
    """
    import time
    all_extracted_data = []

    # Open valid PDF
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        raise ValueError(f"Could not open PDF: {e}")

    total_pages = len(doc)
    logger.info(f"[INFO] Processing {total_pages} pages individually to avoid token limits...")

    prompt = '''
You are a VISION-BASED data extractor for pharmaceutical tables.
This is ONE PAGE from a PDF. Extract every row from the table on this page into a JSON array.

--- TABLE TYPE DETECTION ---
1. **GRID TABLES**: Have many small columns for things like "Phlebitis", "Local site pain", "Redness", etc. with symbols (●, ◆).
2. **STATEMENT TABLES**: Have fewer, wider columns, typically "Generic Drug name", "Brand Name", and "Additional Consideration".

--- EXTRACTION RULES ---
- **row_name**: Exact text from the first column (e.g., "amikacin", "cefepime").
- **superscript_number**: Extract any numbers found in the drug name (e.g., "1,2,3").
- **ph_value**: Text from the "pH" column if present.
- **column_name**: 
    - For GRID tables: Dot-separated list of column headers where a symbol (●, ◆) is present in that row.
    - For STATEMENT tables: The header of the column containing the detailed text (usually "Additional Consideration").
- **mark_type**: For GRID tables, dot-separated list of shape types found ("Circle" or "Diamond"). Null for statement tables.
- **statement**: 
    - For STATEMENT tables: Extract the FULL text from the "Additional Consideration" column.
    - For GRID tables: Use null.
- **superscript_in_statement**: Extract any numbers found inside or at the end of the "statement" text.

--- OUTPUT FORMAT (STRICT JSON ARRAY) ---
[
  {
    "page_number": <integer from footer>,
    "row_name": "drug name",
    "superscript_number": "1,2",
    "ph_value": "4.5-5.5",
    "column_name": "Phlebitis.Local site pain",
    "mark_type": "Circle.Circle",
    "statement": "The full text from 'Additional Consideration' column or null",
    "superscript_in_statement": "number or null"
  }
]
'''
    # Reduced model list for speed, prioritizing flash for simple extraction
    models_to_try = ["gemini-2.0-flash"]
    
    for page_idx in range(total_pages):
        # Create single page PDF in memory
        new_doc = fitz.open()
        new_doc.insert_pdf(doc, from_page=page_idx, to_page=page_idx)
        pdf_bytes = new_doc.tobytes()
        new_doc.close()
        
        real_page_num = page_idx + 1
        print(f"   [PAGE {real_page_num}/{total_pages}] Extracting...", end="\r")

        response = None
        last_error = None
        
        # Retry with different models if one fails
        for model_id in models_to_try:
            try:
                # Detect API version
                if hasattr(client, "models"):
                    # New API
                    response = client.models.generate_content(
                        model=model_id,
                        contents=[
                            types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                            prompt
                        ],
                        config=types.GenerateContentConfig(
                            temperature=0.0,
                            response_mime_type="application/json",
                            max_output_tokens=8192
                        )
                    )
                else:
                    # Legacy API
                    model = client.GenerativeModel(model_name=model_id)
                    response = model.generate_content([
                        {"mime_type": "application/pdf", "data": pdf_bytes},
                        prompt
                    ],
                    generation_config={"temperature": 0.0, "response_mime_type": "application/json", "max_output_tokens": 8192}
                    )
                
                if response:
                    break
                    
            except Exception as e:
                # Simple rate limit handling
                if "429" in str(e):
                    time.sleep(2)
                last_error = e
                continue
        
        if not response:
             logger.error(f"[EXTRACTION] Failed to extract page {real_page_num}: {last_error}")
             continue

        # Parse Response
        try:
            resp = clean_json_string(response.text)
            page_data = json.loads(resp)
            if isinstance(page_data, list):
                # Ensure page number is correct
                for item in page_data:
                    # Override/Verify page number 
                    item["page_number"] = real_page_num
                
                all_extracted_data.extend(page_data)
            
        except Exception as e:
             # Just log error and continue to next page
             logger.error(f"[EXTRACTION] JSON Parsing failed for page {real_page_num}: {e}")
             continue

    logger.info(f"[EXTRACTION] complete. Total records: {len(all_extracted_data)}")
    
    # AUTO-SAVE RAW JSON for debugging
    dump_path = save_json(all_extracted_data, folder="output", filename="raw_extraction_dump.json")
    logger.info(f"[EXTRACTION] Raw dump saved to: {dump_path}")
    
    return all_extracted_data

def extract_footnotes(pdf_path: str) -> DocumentExtraction:
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    
    if not pdf_bytes:
        raise ValueError("PDF is empty")

    prompt = '''You are a specialized Vision Extractor for scientific PDF pages. Your goal is to extract EVERYTHING. You must be extremely granular and extract on a "Statement-By-Statement" basis so no superscript is missed.

    Output a SINGLE JSON array. Each element must follow this schema:
    {
        "page_number": <integer>,
        "superscript_number": "<string>",
        "heading": "<string>",
        "statement": "<string>"
    }

    ### CRITICAL RULES:
    1. **NO SKIPPING (ZERO-LOSS POLICY)**: You are not allowed to summarize. If a heading has a paragraph under it, you must extract EVERY statement in that paragraph if it relates to a superscript. 
    2. **STATEMENT-BY-STATEMENT**: If one paragraph has 3 different superscripts (e.g., 1, 2, and 3), you must create 3 SEPARATE JSON objects. 
    3. **CAPTURE THE "WHY"**: Do not just extract the heading. Extract the explanation, the statistics (like 63.4%, 2.3 million cases, 42.9%), and the full descriptive text associated with the superscript.
    4. **NUMERICAL PRECISION & MAPPING**: Ensure all percentages and case numbers are captured exactly. You MUST be 100% accurate with the superscript number. 

    ### STEP 1: FIND ALL SUPERSCRIPT CITATIONS
    Scan the document for superscript numbers (¹, ², ³, ⁴, ⁵, ⁶, ⁷, ⁸, ⁹, ¹⁰, ¹¹, ¹², ¹³, ¹⁴, ¹⁵, ¹⁶, ¹⁷, ¹⁸, ¹⁹, ²⁰, etc.)
    
    For EACH individual superscript found:
    - **superscript_number**: The exact number or range.
    - **statement**: Extract the FULL descriptive text.
    - **heading**: The nearest clear Section Header.
    - **page_number**: The page number it appears on.
    '''

    models_to_try = ["gemini-2.0-flash"]
    response = None
    last_error = None

    for model_id in models_to_try:
        try:
            if hasattr(client, "models"):
                response = client.models.generate_content(
                    model=model_id,
                    contents=[
                        types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                        prompt
                    ],
                    config=types.GenerateContentConfig(temperature=0.0, response_mime_type="application/json", max_output_tokens=8192)
                )
            else:
                model = client.GenerativeModel(model_name=model_id)
                response = model.generate_content([
                    {"mime_type": "application/pdf", "data": pdf_bytes},
                    prompt
                ],
                generation_config={"temperature": 0.0, "response_mime_type": "application/json", "max_output_tokens": 8192}
                )
            if response:
                break
        except Exception as e:
            last_error = e
            continue
    
    if not response:
        raise RuntimeError(f"Extraction failed: {last_error}")

    resp_text = clean_json_string(response.text)
    
    # Extract references separately
    full_text = extract_text_from_pdf(pdf_path)
    references = extract_references_from_text(full_text)

    try:
        data = json.loads(resp_text)
        
        in_text_items = []
        # Handle list vs dict with statements key
        items = data if isinstance(data, list) else data.get("statements", [])
        
        for item in items:
            try:
                in_text_items.append(InlineCitation(**item))
            except:
                continue
                
        return DocumentExtraction(
            title=None,
            author=None,
            footnotes=[],
            in_text=in_text_items,
            references=references
        )
    except Exception as e:
        logger.error(f"Failed to parse JSON: {str(e)}")
        raise e

def save_json(data, folder="output", filename="result.json"):
    """
    Saves JSON-serializable data into a folder.
    Automatically creates folder if missing.
    """
    try:
        os.makedirs(folder, exist_ok=True)
        file_path = os.path.join(folder, filename)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return file_path

    except Exception as e:
        return None

def main():
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        # Defaults for testing if no arg provided
        pdf_path = input("Enter path to PDF: ").strip()

    if not os.path.isfile(pdf_path):
        print(f"File not found: {pdf_path}")
        sys.exit(1)

    # Production Logic: Decide which extraction to run
    try:
        # If your PDF specifically requires the drug Mark/Table logic, use extract_drug_superscript_table_data
        # Otherwise, the new Footnote/Heading logic is used by default.
        if "drug" in pdf_path.lower():
            print("Running Drug Table Extraction...")
            result = extract_drug_superscript_table_data(pdf_path)
        else:
            print("Running Standard Heading/Footnote Extraction...")
            result = extract_footnotes(pdf_path)
            if hasattr(result, "model_dump"):
                result = result.model_dump()
        
        output_folder = "extracted_json"
        output_filename = os.path.basename(pdf_path).replace(".pdf", "_extracted.json")
        save_json(data=result, folder=output_folder, filename=output_filename)
        
        print(f"[OK] Extraction complete. Saved to {output_folder}/{output_filename}")
        print(json.dumps(result, indent=2)[:500] + "...")
        
    except Exception as e:
        print(f"[ERROR] Error: {e}")

if __name__ == "__main__":
    main()