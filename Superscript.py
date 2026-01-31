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

    prompt = '''You are a specialized Vision Extractor for scientific PDF pages. Your goal is to extract specific statements, specifically focusing on superscript citations AND data presented in tables.

    Output a SINGLE JSON array. Each element must follow this schema:
    {
        "page_number": <integer>,
        "superscript_number": "<string>",
        "heading": "<string>",
        "statement": "<string>"
    }

    ### INSTRUCTIONS FOR SUPERSCRIPTS (STRICT VERBATIM):
    Your goal is to extract content EXACTLY as it appears. 
    
    1. **CITATION ON HEADING**: If a superscript citation is found on a section title or heading (e.g., "Introduction¹" or "21. Midline study...²¹"):
       - **Superscript Number**: Extract the number(s) from the heading.
       - **Heading**: The heading text itself (without the superscript).
       - **Statement**: You MUST capture the ENTIRE page content following that heading. 
         - Specifically, look for and include sections like "Study author(s)", "Study design", "Study objective", "Publication", "Study location", "Study Length", etc.
         - Do not stop after the citation. Include every paragraph and detail until the next superscript number is found.
         - If the section continues on the next page, include that too.
    
    2. **CITATION IN SENTENCE**: If a superscript citation is found at the end of a sentence:
       - **Superscript Number**: Extract the number(s).
       - **Heading**: The nearest section title.
       - **Statement**: The specific sentence associated with that citation (verbatim).

    ### INSTRUCTIONS FOR TABLES (CRITICAL):
    1. Identify any comparison tables or data grids on the page.
    2. For every distinct cell containing data, create a JSON entry.
    3. If the table cell text contains a superscript citation (e.g., ¹, ², ³–⁵):
    - Extract the citation number(s) EXACTLY as they appear.
    - Set "superscript_number" to those number(s) (e.g., "6", "12,13", "14-15").
    4. If the table cell text does NOT contain any superscript citation:
    - Set "superscript_number" to "Table".
    5. Set "heading" to the Main Table Title or the specific Row Category
    (e.g., "Cost", "Invasiveness", "Pain or Side Effects").
    6. Set "statement" using the following strict format:
    "Row: [Row Header Name] | Column: [Column Header Name] | Content: [Cell Text WITHOUT the superscript]"

    
    *Example of Table Handling:*
    If a cell has text "$500" where the Row is "Cost" and Column is "Surgery" with a superscript "¹²":
    {
        "page_number": 1,
        "superscript_number": "12",
        "heading": "Cost",
        "statement": "Row: Cost | Column: Surgery | Content: $500"
    }

    ### GENERAL RULES:
    - Return ONLY the JSON array. No markdown, no explanations.
    - If the page has no citations and no tables, return an empty array [].
    '''

    models_to_try = ["gemini-1.5-flash-latest", "gemini-2.0-flash", "gemini-1.5-pro"]
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