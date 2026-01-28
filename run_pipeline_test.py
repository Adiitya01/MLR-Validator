import os
import json
import pandas as pd
from Superscript import extract_footnotes
from conversion import build_validation_dataframe

def run_pipeline(pdf_path):
    print(f"Starting pipeline for: {pdf_path}")
    
    # Step 1: Extract citations and references
    print("Step 1: Extracting citations and references using Gemini...")
    extraction_result = extract_footnotes(pdf_path)
    
    # Get the raw data for conversion
    in_text = extraction_result.in_text
    references = extraction_result.references
    
    print(f"Extraction successful: found {len(in_text)} citations and {len(references)} references.")
    
    # Step 2: Convert to validation format
    print("Step 2: Converting to validation format...")
    df = build_validation_dataframe(in_text, references)
    
    # Step 3: Store results in JSON
    output_dir = "test_results"
    os.makedirs(output_dir, exist_ok=True)
    
    pdf_name = os.path.basename(pdf_path).replace(".pdf", "")
    json_path = os.path.join(output_dir, f"{pdf_name}_conversion.json")
    
    # Convert DataFrame to list of dicts and save to JSON
    results = df.to_dict(orient="records")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"Pipeline complete! Results stored in: {json_path}")
    return json_path

if __name__ == "__main__":
    pdf_path = r"C:\Users\aditya.pasare\Downloads\BD-164897 Midline compendium articles 20-25 (1).pdf"
    if os.path.exists(pdf_path):
        run_pipeline(pdf_path)
    else:
        print(f"File not found: {pdf_path}")
