import os
import json
from Superscript import client, types

with open(r"C:\Users\aditya.pasare\Downloads\BD_Drugs list - ICC (All Antibiotics)_20250911 (1).pdf", "rb") as f:
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

print("Querying Gemini...")
try:
    if hasattr(client, "models"):
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                prompt
            ],
            config=types.GenerateContentConfig(temperature=0.0)
        )
        text = response.text
    else:
        model = client.GenerativeModel(model_name="gemini-2.0-flash")
        response = model.generate_content([
            {"mime_type": "application/pdf", "data": pdf_bytes},
            prompt
        ])
        text = response.text

    print("RAW RESPONSE START")
    print(text)
    print("RAW RESPONSE END")
except Exception as e:
    print(f"Error: {e}")
