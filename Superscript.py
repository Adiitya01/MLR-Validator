import re
import json
import os
import sys
from typing import List, Optional, Union, Dict
from pydantic import BaseModel, Field, ValidationError
from dotenv import load_dotenv
import fitz  # PyMuPDF

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
def extract_drug_superscript_table_data(pdf_path: str) -> list:

    """
    Extracts drug superscript and table data for both table types (as described in requirements).
    """
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
        prompt = '''
You are an expert at extracting and validating drug superscript citations and table data from scientific PDFs.
For each table in the PDF, do the following: 
--- For tables like IMAGE 1 ---
1. For every row, check if the row name (first column) contains a superscript citation (e.g., ¹, ², ³–⁵).
2. If a superscript is present in the row name, extract the row name and the superscript number(s).
3. For that row, check each cell for a circle (●) or diamond (◆) mark.
4. Collect all columns in that row that have a circle or diamond mark.
5. Also extract the pH value from the relevant column in that row. If the cloumn has no pH value, set it to null.
6. Output a single JSON object per row:
    {
      "page_number": <integer>,
      "row_name": "<string>",
      "superscript_number": "<string>",
      "ph_value": "<string>",
      "column_name": "<column1>.<column2>.<column3>",
      "mark_type": "<type1>.<type2>.<type3>"
    }
--- For tables like IMAGE 2 ---
1. For every row, extract:
    - The row name (first column)
    - The statement (second column)
    - The column name (header)
2. Detect and extract any superscript citations in both the row name and the statement.
3. Output a JSON object for each row:
    {
      "page_number": <integer>,
      "row_name": "<string>",
      "row_superscript": "<string or null>",
      "statement": "<string>",
      "statement_superscript": "<string or null>",
      "column_name": "<string>"
    }
--- GENERAL RULES ---
- Return a JSON array of all findings.
- If no superscripts or marks are found, return an empty array [].
- Do not include markdown or explanations, only the JSON array.
'''
    models_to_try = ["gemini-1.5-flash-latest", "gemini-2.0-flash", "gemini-1.5-pro"]
    response = None
    last_error = None

    for model_id in models_to_try:
        try:
            # Detect if we're using the new Client or the legacy genai
            if hasattr(client, "models"):
                # New API (google-genai)
                response = client.models.generate_content(
                    model=model_id,
                    contents=[
                        types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                        prompt
                    ],
                    config=types.GenerateContentConfig(temperature=0.0)
                )
            else:
                # Legacy API (google-generativeai)
                model = client.GenerativeModel(model_name=model_id)
                response = model.generate_content([
                    {"mime_type": "application/pdf", "data": pdf_bytes},
                    prompt
                ])
            
            if response:
                break
        except Exception as e:
            last_error = e
            continue
    
    if not response:
        raise RuntimeError(f"All models failed for extraction: {str(last_error)}")

    resp = response.text.strip()
    # Clean up Markdown code blocks if present
    if resp.startswith("```"):
        m = re.search(r"```(?:[^\n]*\n)?(.*)```$", resp, re.S)
        if m:
            resp = m.group(1).strip()
        else:
            resp = resp.strip('`').strip()

    try:
        data = json.loads(resp)
        return data
    except Exception as e:
        raise ValueError(f"Failed to parse Gemini response: {e}\nRaw response: {resp}")

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

# --- Main Extraction Function ---

def extract_footnotes(pdf_path: str) -> DocumentExtraction:
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    
    # Validate PDF is not empty
    if not pdf_bytes:
        raise ValueError(f"PDF file at {pdf_path} is empty. Cannot process.")
    
    # Validate PDF has content (check for PDF header)
    if not pdf_bytes.startswith(b'%PDF'):
        raise ValueError(f"File at {pdf_path} is not a valid PDF file.")

    prompt = '''You are a specialized Vision Extractor for scientific PDF pages. Your goal is to extract EVERYTHING. You must be extremely granular and extract on a "Statement-By-Statement" basis so no superscript is missed.

    Output a SINGLE JSON array. Each element must follow this schema:
    {
        "page_number": <integer>,
        "superscript_number": "<string>",
        "heading": "<string>",
        "statement": "<string>"
    }

    ### CRITICAL RULES:
    1. **NO SKIPPING (ZERO-LOSS POLICY)**: You are not allowed to summarize. If a heading has a paragraph under it, you must extract EVERY statement in that paragraph if it relates to a superscript. Special focus: capture the "63.4% stage I-II diagnosis" statistic in the Epidemiology section.
    2. **STATEMENT-BY-STATEMENT**: If one paragraph has 3 different superscripts (e.g., 1, 2, and 3), you must create 3 SEPARATE JSON objects. 
    3. **CAPTURE THE "WHY"**: Do not just extract the heading. Extract the explanation, the statistics (like 63.4%, 2.3 million cases, 42.9%), and the full descriptive text associated with the superscript.
    4. **NUMERICAL PRECISION & MAPPING**: Ensure all percentages and case numbers are captured exactly. You MUST be 100% accurate with the superscript number. If a fact is cited by "7", do not ever assign it "1". Check the number's physical proximity to the text carefully.
    5. **TITLE + BODY RULE**: If the superscript is attached to a **title or subtitle** (like "National Comprehensive Cancer Network¹⁴"), you MUST include BOTH the title AND the full explanatory paragraph that follows it in the "statement" field.
       - Example: "National Comprehensive Cancer Network¹⁴ - Encourages to place clips during biopsy of suspicious axillary nodes to guide surgery. In cases with palpable or multiple suspicious nodes, malignancy must be confirmed by FNA or core biopsy with clip placement."

    ### STEP 1: FIND ALL SUPERSCRIPT CITATIONS
    Scan every pixel of the page for superscript numbers (¹, ², ³, ⁴, ⁵, ⁶, ⁷, ⁸, ⁹, ¹⁰, ¹¹, ¹², ¹³, ¹⁴, ¹⁵, ¹⁶, ¹⁷, ¹⁸, ¹⁹, ²⁰, ²¹, etc.)
    
    For EACH individual superscript found:
    - **superscript_number**: The exact number or range (e.g., "1,2", "3", "7"). Be extremely careful to match the number to the correct sentence.
    - **statement**: Extract on a "STATEMENT-BY-STATEMENT" basis. Capture the FULL descriptive text, explanation, and any statistics (like 63.4%, 90% success, 0% false negatives) cited by the number. **If the superscript is on a title, include the title AND all body text below it.**
    - **heading**: The nearest clear Section Header or Title (e.g., "Epidemiology", "USA and Canada", "Asia-Pacific").
    
    ### STEP 2: EXTRACT ALL TABLE DATA
    For any comparison tables or data grids:
    
    1. **IDENTIFY HEADERS** - Note the labels for Rows (left column) and Columns (top row).
    
    2. **FOR EACH DATA CELL:**
       - **Find the Citation**: Search for a superscript number in this order:
         a) Inside the cell itself.
         b) In the Row Header (the category on the left).
         c) In the Column Header (the title at the top).
       - **Assign Citation**: 
         - If a number is found in any of those 3 places, set "superscript_number" to that number.
         - ONLY if no number exists in the cell, row, or column, set "superscript_number" to "Table".
       - **Set Details**:
         - Set "heading" to the Row Category.
         - Set "statement" using format: "Row: [Row Name] | Column: [Column Name] | Content: [Cell Text]"

    ### STEP 3: IGNORE REFERENCES
    Do NOT extract the list of references at the bottom of the page. Only extract the in-text statements.
    '''

    models_to_try = ["gemini-2.0-flash"]
    response = None
    last_error = None

    for model_id in models_to_try:
        try:
            if hasattr(client, "models"):
                # New API (google-genai)
                response = client.models.generate_content(
                    model=model_id,
                    contents=[
                        types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                        prompt
                    ],
                    config=types.GenerateContentConfig(temperature=0.0 , top_k=1)
                )
            else:
                # Legacy API (google-generativeai)
                model = client.GenerativeModel(model_name=model_id)
                response = model.generate_content([
                    {"mime_type": "application/pdf", "data": pdf_bytes},
                    prompt
                ])
            if response:
                break
        except Exception as e:
            last_error = e
            continue
    
    if not response:
        raise RuntimeError(f"All models failed for extraction: {str(last_error)}")

    resp = response.text.strip()
    # Clean up Markdown code blocks if present
    if resp.startswith("```"):
        m = re.search(r"```(?:[^\n]*\n)?(.*)```$", resp, re.S)
        if m:
            resp = m.group(1).strip()
        else:
            resp = resp.strip('`').strip()

    try:
        data = json.loads(resp)

        # Extract references from PDF text once
        pdf_text = extract_text_from_pdf(pdf_path)
        references = extract_references_from_text(pdf_text)

        # Handle new structure: {title, statements[]}
        if isinstance(data, dict) and "statements" in data:
            in_text_items = []
            title = data.get("title", None)
            
            for idx, item in enumerate(data.get("statements", [])):
                try:
                    in_text_items.append(InlineCitation(**item))
                except ValidationError as ve:
                    continue
            
            return DocumentExtraction(
                title=title, 
                author=None, 
                footnotes=[], 
                in_text=in_text_items,
                references=references
            )

        # Handle List output (Legacy format from old prompt)
        if isinstance(data, list):
            in_text_items = []
            for idx, item in enumerate(data):
                try:
                    in_text_items.append(InlineCitation(**item))
                except ValidationError as ve:
                    continue
            
            return DocumentExtraction(
                title=None, 
                author=None, 
                footnotes=[], 
                in_text=in_text_items,
                references=references
            )

        # Handle Dict output (Edge case)
        if isinstance(data, dict):
            extraction = DocumentExtraction(**data)
            extraction.references = references
            return extraction

        raise ValueError("Unexpected JSON structure")

    except Exception as e:
        raise

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