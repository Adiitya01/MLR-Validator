import json
import pandas as pd
from pathlib import Path
import sys
import re
from Superscript import extract_drug_superscript_table_data

def build_validation_dataframe(in_text, references, title=""):
    """
    Create DataFrame for Excel export matching Validation.py requirements:
    
    Columns: statement | reference_no | reference
    """

    output = []

    def _get_field(obj, key, default=""):
        """Safely get a field from a dict-like or Pydantic/BaseModel object.

        Tries in this order: mapping `.get`, `.dict()` conversion, attribute access.
        Any exceptions are swallowed and `default` is returned.
        """
        # Try mapping-style `.get()` first
        try:
            if hasattr(obj, 'get'):
                return obj.get(key, default)
        except Exception:
            pass

        # Try Pydantic/BaseModel `.dict()`
        try:
            if hasattr(obj, 'dict'):
                return obj.dict().get(key, default)
        except Exception:
            pass

        # Fallback to attribute access
        try:
            return getattr(obj, key, default)
        except Exception:
            return default
        
    for item in in_text:
        raw_sup = _get_field(item, "superscript_number", "")
        raw_stmt = _get_field(item, "statement", "")
        raw_heading = _get_field(item, "heading", "")

        superscript_no = str(raw_sup if raw_sup is not None else "").strip()
        statement = str(raw_stmt if raw_stmt is not None else "").strip()
        heading = str(raw_heading if raw_heading is not None else "").strip()

        # ----------------------------------------------
        # 1. Detect table format: Row | Column | Content
        # ----------------------------------------------
        is_table = False

        table_match = re.search(
            r"Row:\s*(.*?)\s*\|\s*Column:\s*(.*?)\s*\|\s*Content:\s*(.*)$",
            statement
        )

        if table_match:
            row_val = table_match.group(1).strip()
            col_val = table_match.group(2).strip()
            content_val = table_match.group(3).strip()
            statement = f"{row_val}. {col_val}. {content_val}"
            is_table = True
        elif ". " in statement and statement.count(". ") >= 2:
            # Detect new 'Row. Column. Content' format from Gemini
            is_table = True

        # ----------------------------------------------------
        # 2. Build final_statement with heading (ONLY if not table)
        # ----------------------------------------------------
        if is_table:
            final_statement = statement
        elif heading and statement:
            final_statement = f"{heading}. {statement}"
        elif statement:
            final_statement = statement
        else:
            final_statement = heading

        # ----------------------------------------------------
        # 3. Extract reference numbers if superscript_no == "Table"
        # ----------------------------------------------------
        if superscript_no == "Table":
            ref_match = re.search(r'[\s,]+([\d,\-]+)\s*$', final_statement)
            if ref_match:
                superscript_no = ref_match.group(1).strip()
                final_statement = final_statement[:ref_match.start()].strip()

        # ----------------------------------------------------
        # 4. Lookup reference text
        # ----------------------------------------------------
        ref_text = references.get(superscript_no, "")

        output.append({
            "statement": final_statement,
            "reference_no": superscript_no,
            "reference": ref_text,
            "page_no": _get_field(item, "page_number", 1)
        })

    return pd.DataFrame(output)


def build_validation_rows_image1(data_rows, references):
    """
    IMAGE 1: pH Compatibility Tables
    
    Input structure:
    {
      "page_number": int,
      "row_name": "Drug Name",
      "superscript_number": "1,2,3",
      "ph_value": "3.5-5.5",
      "column_name": "Solution A.Solution B.Solution C",
      "mark_type": "●.◆.●"
    }
    
    Output format: row_name. pH_value. column1. column2. column3.
    Example: "Amikacin. 3.5-5.5. Solution A. Solution B. Solution C."
    """
    output = []
    
    for row in data_rows:
        row_name = str(row.get("row_name") or "").strip()
        ph_value = row.get("ph_value")
        ph_value = str(ph_value).strip() if ph_value not in (None, "", "null") else ""
        
        column_name_raw = str(row.get("column_name") or "").strip()
        
        # Superscript for reference
        reference_no = str(row.get("superscript_number") or "").strip()
        
        # Split dot-separated columns
        if column_name_raw:
            columns = [col.strip() for col in column_name_raw.split('.') if col.strip()]
            columns_formatted = '. '.join(columns)
        else:
            columns_formatted = ''
        
        # Build statement: row_name. pH_value. column1. column2. column3
        if ph_value and columns_formatted:
            final_statement = f"{row_name}. {ph_value}. {columns_formatted}."
        elif ph_value:
            final_statement = f"{row_name}. {ph_value}."
        elif columns_formatted:
            final_statement = f"{row_name}. {columns_formatted}."
        else:
            final_statement = f"{row_name}."
        
        # Lookup reference text
        reference_text = references.get(reference_no, "")
        
        output.append({
            "statement": final_statement,
            "reference_no": reference_no,
            "reference": reference_text,
            "page_no": row.get("page_number", 1)
        })
    
    return output


def build_validation_rows_image2(data_rows, references):
    """
    IMAGE 2: Statement-Based Tables
    
    Input structure:
    {
      "page_number": int,
      "row_name": "Drug Name",
      "row_superscript": "1" or null,
      "statement": "Detailed instruction text",
      "statement_superscript": "2" or null,
      "column_name": "Column Header"
    }
    
    Output format: row_name. statement. column_name.
    Example: "Amikacin. Store in refrigerator. Storage Conditions."
    """
    output = []
    
    for row in data_rows:
        row_name = str(row.get("row_name") or "").strip()
        statement_text = str(row.get("statement") or "").strip()
        column_name = str(row.get("column_name") or "").strip()
        
        # Superscript priority: row_superscript > statement_superscript
        reference_no = (
            row.get("row_superscript") 
            or row.get("statement_superscript") 
            or ""
        )
        reference_no = str(reference_no).strip()
        
        # Build statement: row_name. column_name. statement
        if statement_text and column_name:
            final_statement = f"{row_name}. {column_name}. {statement_text}"
        elif statement_text:
            final_statement = f"{row_name}. {statement_text}"
        elif column_name:
            final_statement = f"{row_name}. {column_name}"
        else:
            final_statement = f"{row_name}"
        
        # Lookup reference text
        reference_text = references.get(reference_no, "")
        
        output.append({
            "statement": final_statement,
            "reference_no": reference_no,
            "reference": reference_text,
            "page_no": row.get("page_number", 1)
        })
    
    return output


def build_validation_rows_special_case(data_rows, references):
    """
    AUTO-ROUTER: Detects table type and routes to appropriate converter.
    
    Detection logic:
    - If rows have 'statement' field → IMAGE 2 (statement-based)
    - If rows have 'ph_value' field → IMAGE 1 (pH compatibility)
    - Falls back to IMAGE 1 if uncertain
    """
    if not data_rows:
        return []
    
    # Sample first row to detect type
    first_row = data_rows[0]
    
    # IMAGE 2 detection: has 'statement' field populated
    if first_row.get("statement") and str(first_row.get("statement")).strip():
        return build_validation_rows_image2(data_rows, references)
    
    # IMAGE 1 detection: has 'ph_value' or 'mark_type' fields
    elif first_row.get("ph_value") or first_row.get("mark_type"):
        return build_validation_rows_image1(data_rows, references)
    
    # Default to IMAGE 1
    else:
        return build_validation_rows_image1(data_rows, references)


def print_validation_results(validation_rows):
    """
    Print validation rows to console in a readable format.
    """
    if not validation_rows:
        print("\n[WARNING] No validation rows to display.\n")
        return
    
    print("\n" + "="*80)
    print("  VALIDATION RESULTS")
    print("="*80 + "\n")
    
    print(f"Total rows processed: {len(validation_rows)}\n")
    
    for idx, row in enumerate(validation_rows, 1):
        print(f"[ROW] Row #{idx}")
        print("-" * 80)
        print(f"   Statement:      {row.get('statement', '')}")
        print(f"   Reference No:   {row.get('reference_no', '')}")
        print(f"   Reference:      {row.get('reference', '')[:100]}..." if len(row.get('reference', '')) > 100 else f"   Reference:      {row.get('reference', '')}")
        print(f"   Page No:        {row.get('page_no', '')}")
        print()


def convert_to_excel(json_file, output_excel=None, title=""):
    """
    Convert Superscript.py JSON output to Excel file for Validation.py
    
    Args:
        json_file: Path to extracted.json from Superscript.py
        output_excel: Output Excel file path (optional)
        title: Title to prepend to statements (optional)
    
    Returns:
        Path to created Excel file
    """
    
    print(f"[READING] Reading: {json_file}")
    
    # Read JSON
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Extract data
    in_text = data.get('in_text', [])
    references = data.get('references', {})
    
    print(f"[OK] Found {len(in_text)} citations")
    print(f"[OK] Found {len(references)} references\n")
    
    # Build DataFrame
    print("[PROCESSING] Processing citations...\n")
    df = build_validation_dataframe(in_text, references, title=title)
    
    # Display all converted output on console BEFORE saving
    print_dataframe_to_console(df)
    
    # Determine output file
    if not output_excel:
        base_name = Path(json_file).stem
        output_excel = str(Path(json_file).parent / f"{base_name}_validation.xlsx")
    
    # Ask user for confirmation
    print("\n" + "="*80)
    print("  CONFIRM BEFORE SAVING")
    print("="*80)
    user_input = input("\nDoes the output look correct? (yes/no): ").strip().lower()
    
    if user_input not in ['yes', 'y']:
        print("\n[CANCELLED] Operation cancelled. Excel file not saved.\n")
        return None
    
    # Save to Excel
    print(f"\n[SAVING] Saving to Excel: {output_excel}\n")
    
    df.to_excel(output_excel, index=False, sheet_name='Statements')
    
    print(f"[OK] Successfully created validation file!")
    print(f"   [STATS] Rows: {len(df)}")
    print(f"   [COLS] Columns: {', '.join(df.columns)}")
    print(f"   [FILE] File: {output_excel}\n")
    
    return output_excel


def print_dataframe_to_console(df):
    """
    Print the entire DataFrame to console in a readable format before saving.
    """
    if df.empty:
        print("\n[WARNING] No data to display.\n")
        return
    
    print("\n" + "="*100)
    print("  CONVERTED OUTPUT (Before Saving to Excel)")
    print("="*100)
    print(f"\nTotal records: {len(df)}\n")
    
    # Print each row in a formatted way
    for idx, (_, row) in enumerate(df.iterrows(), 1):
        print(f"[RECORD] Record #{idx}")
        print("-" * 100)
        
        # Statement
        stmt = str(row.get('statement', ''))
        print(f"   [STATEMENT] Statement:")
        if len(stmt) > 95:
            # Wrap long statements
            wrapped = [stmt[i:i+95] for i in range(0, len(stmt), 95)]
            for i, line in enumerate(wrapped):
                prefix = "      " if i > 0 else "      "
                print(f"{prefix}{line}")
        else:
            print(f"      {stmt}")
        
        # Reference No
        ref_no = str(row.get('reference_no', ''))
        print(f"   [REF NO] Reference No: {ref_no}")
        
        # Reference Text
        ref_text = str(row.get('reference', ''))
        print(f"   [REFERENCE] Reference:")
        if len(ref_text) > 0:
            if len(ref_text) > 95:
                wrapped = [ref_text[i:i+95] for i in range(0, len(ref_text), 95)]
                for i, line in enumerate(wrapped):
                    prefix = "      " if i > 0 else "      "
                    print(f"{prefix}{line}")
            else:
                print(f"      {ref_text}")
        else:
            print(f"      (No reference found)")
        
        # Page No
        page_no = row.get('page_no', '')
        print(f"   [PAGE] Page No: {page_no}")
        print()
    
    print("="*100 + "\n")


# ============================================================================
# TEST FUNCTION - Run with: python conversion.py --test
# ============================================================================
def convert_superscript_output_to_validation(pdf_path):
    """
    Pipeline function: Extract from PDF → Convert to validation format.
    
    Steps:
    1. Run Superscript.py extraction on PDF at runtime
    2. Process through build_validation_rows_special_case()
    3. Display polished results on console
    4. Auto-save to Excel
    
    Args:
        pdf_path: Path to PDF file to extract from
    """
    
    print("\n" + "="*80)
    print("  PIPELINE: PDF → Superscript Extraction → Validation Format")
    print("="*80 + "\n")
    
    # Step 1: Run Superscript extraction at runtime
    print(f"[EXTRACTING] Extracting from PDF: {pdf_path}\n")
    try:
        data_rows = extract_drug_superscript_table_data(pdf_path)
    except Exception as e:
        print(f"[ERROR] Error during extraction: {str(e)}\n")
        return None
    
    print(f"[OK] Extracted {len(data_rows)} records\n")
    
    # For now, references will be empty (they come from text extraction in Superscript)
    references = {}
    
    # Step 2: Process through special case converter
    print("[PROCESSING] Processing records through validation converter...\n")
    result = build_validation_rows_special_case(data_rows, references)
    
    if not result:
        print("[WARNING] No results generated.\n")
        return None
    
    print(f"[OK] Generated {len(result)} validation rows\n")
    
    # Step 3: Display polished results
    print_validation_results(result)
    
    return result


# Example Usage
if __name__ == "__main__":
    
    if len(sys.argv) < 2 or sys.argv[1] == "--help":
        print("""


WORKFLOW:
  1. Run conversion.py with PDF file
  2. Automatically extracts data from PDF (Superscript.py at runtime)
  3. See polished results on console
  4. Auto-saves to Excel (NO confirmation needed)

Usage:
  python conversion.py <pdf_file>

Examples:
  python conversion.py "path/to/document.pdf"
  python conversion.py "Downloads/BD_Drugs_list.pdf"

Output:
  - Runs extraction at runtime
  - Displays formatted results on console
  - AUTO-SAVES to Excel file
  - Columns: statement | reference_no | reference | page_no
        """)
        sys.exit(0)
    
    pdf_path = sys.argv[1]
    
    # Verify PDF exists
    if not Path(pdf_path).exists():
        print(f"[ERROR] Error: PDF file not found - {pdf_path}\n")
        sys.exit(1)
    
    # Run pipeline (extract + convert + display)
    validation_rows = convert_superscript_output_to_validation(pdf_path)
    
    if validation_rows is None:
        print("Pipeline terminated.\n")
        sys.exit(1)
    
    # AUTO-SAVE to Excel (no confirmation needed)
    print("\n" + "="*80)
    print("  AUTO-SAVING TO EXCEL")
    print("="*80 + "\n")
    
    base_name = Path(pdf_path).stem
    output_folder = "validation_output"
    output_excel = str(Path(output_folder) / f"{base_name}_validation.xlsx")
    
    # Create folder if needed
    Path(output_folder).mkdir(exist_ok=True)
    
    df = pd.DataFrame(validation_rows)
    df.to_excel(output_excel, index=False, sheet_name='Statements')
    
    print(f"[OK] Successfully created validation file!")
    print(f"   [STATS] Rows: {len(df)}")
    print(f"   [COLS] Columns: {', '.join(df.columns)}")
    print(f"   [FILE] File: {output_excel}\n")
    
    print("[OK] Pipeline complete!\n")
    print("📌 Next steps:")
    print(f"   1. Upload '{output_excel}' to Validation.py")
    print("   2. Upload reference PDFs in Validation.py")
    print("   3. Click 'Start Validation' button\n")
