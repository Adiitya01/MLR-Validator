# 📚 Research Paper Citation Validation Pipeline

Complete end-to-end system for extracting, validating, and verifying citations in research papers.

## 🎯 Overview


Research Paper (PDF)
    ↓
[Superscript.py] → Extracts citations & references using Gemini Vision AI
   # Research Paper Citation Validation Pipeline

   This repository implements a reproducible pipeline to extract citation-bearing statements from research PDFs, map those statements to bibliographic references, and validate the statements against the referenced documents using a local large language model (LLM).

   The pipeline has three primary stages:

   - Extract: identify in-text citation statements and the reference list from a PDF.
   - Convert: transform extraction output into a tabular format suitable for batch validation.
   - Validate: use an LLM to compare each statement with the referenced documents and produce a labeled verdict and supporting evidence.

   ## Architecture

   Research paper (PDF) → `Superscript.py` → `extracted.json` → `ConvertToValidation.py` → `validation.xlsx` → `Validation.py` → validation report (Excel/JSON/CSV)

   ## Components

   ### `Superscript.py`
   Purpose: Extract superscript citations (in-text statements) and the references section from a PDF file.

   Inputs:
   - PDF file containing the research paper.

   Outputs:
   - `extracted.json`: JSON document containing an `in_text` array of statements and a `references` dictionary mapping citation numbers to reference strings.

   Usage:
   ```
   python Superscript.py "research_paper.pdf"
   ```

   Notes: this component may call an OCR or vision-based API (for example, a configured Gemini Vision API) when PDFs are scanned images.

   ### `ConvertToValidation.py`
   Purpose: Convert the extraction JSON into a validation-ready spreadsheet.

   Inputs:
   - `extracted.json` produced by `Superscript.py`.

   Outputs:
   - `validation.xlsx` with at minimum the columns: `statement`, `reference_no`, `reference`, `heading`, `page_no`.

   Usage:
   ```
   python ConvertToValidation.py "research_paper_extracted.json"
   ```

   ### `Validation.py`
   Purpose: Validate each statement in the spreadsheet against the corresponding reference document(s) using an LLM and return labels and evidence.

   Inputs:
   - `validation.xlsx` (from `ConvertToValidation.py`).
   - One or more reference PDF files that contain the cited sources.
   - Configuration for the local LLM server (LM Studio or equivalent).

   Outputs:
   - Validation results exported as Excel, JSON, or CSV. Each record contains: verdict (Supported / Contradicted / Not Found), evidence text, confidence score, and metadata about the matching method.

   Usage (development):
   ```
   streamlit run Validation.py
   ```
   This starts a local Streamlit UI (default at `http://localhost:8501`) to run and monitor validations.

   ### `Pipeline.py`
   Purpose: Orchestrate the full extraction → conversion → validation workflow.

   Usage:
   ```
   python Pipeline.py "research_paper.pdf"

   # To run extraction and conversion only
   python Pipeline.py "research_paper.pdf" --no-ui

   # Provide a directory of reference PDFs
   python Pipeline.py "research_paper.pdf" "C:\\path\\to\\reference_pdfs"
   ```


   Stepwise:
   1. Extract: `python Superscript.py "research_paper.pdf"` → produces `*_extracted.json`.
   2. Convert: `python ConvertToValidation.py "*_extracted.json"` → produces `validation.xlsx`.
   3. Validate: `streamlit run Validation.py` and upload `validation.xlsx` and reference PDFs in the UI, or run programmatically.

   ## Input / output specifications

   `Superscript.py` input: a PDF file. Prefer text-based PDFs; if scanned, ensure acceptable OCR quality.

   `Superscript.py` output: JSON with the following fields:
   - `in_text`: array of objects with `page_number`, `superscript_number`, `heading`, and `statement`.
   - `references`: mapping from citation number (string) to reference text.

   `ConvertToValidation.py` output: `validation.xlsx` with columns `statement`, `reference_no`, `reference`, `heading`, `page_no`.

   `Validation.py` outputs: labeled validation records with `verdict`, `evidence`, `confidence_score`, and other metadata; export formats: Excel, JSON, CSV.

   ## Configuration

   LM (LM Studio) configuration:
   - Install and run a local LLM server (LM Studio or equivalent).
   - Default server URL used by the project may be configured in a settings file or environment variable (example default previously used: `http://10.168.30.159:1234`).

   Gemini / Vision API (optional for `Superscript.py`):
   - If a cloud vision API is required, set the API key in a `.env` file as `GEMINI_API_KEY=...` and ensure the code reads it via `python-dotenv` or equivalent.

   ## Dependencies

   Install Python dependencies in the project environment. Example:
   ```
   pip install -r requirements.txt
   ```
   If a `requirements.txt` is not present or incomplete, the following packages are typically required:
   ```
   pip install streamlit pandas openpyxl pymupdf python-dotenv requests
   ```

   ## File structure (representative)

   ```
   Final_pipeline/
   ├── Superscript.py
   ├── ConvertToValidation.py
   ├── Validation.py
   ├── Pipeline.py
   ├── Reference_Extractor.py
   ├── README.md
   ├── requirements.txt
   └── .env (not tracked; create locally for API keys)
   ```

   ## Troubleshooting (common issues)

   1. API key missing
   - Create `.env` in the repository root and add `GEMINI_API_KEY=your_api_key_here`.

   2. LM Studio reports no available models
   - Ensure a model is installed and the LM Studio server is running. Verify server URL and port.

   3. References not found in provided PDFs
   - Confirm the correct reference PDFs were supplied and that they are text-searchable. Improve matching by providing accurate filenames and page numbers.

   4. Low validation accuracy
   - Use a stronger or better-configured LLM, confirm reference-document mapping accuracy in `validation.xlsx`, and sample-check low-confidence items manually.

   ## Examples

   Run the pipeline for a single PDF:
   ```
   python Pipeline.py "oncology_review.pdf"
   ```

   Expected outputs include `*_extracted.json` and `*_validation.xlsx` and a set of validation reports.

   ## License

   Internal use only.

   ## Version history

   - v1.0 — Initial release (Dec 2024)

   **Last updated:** December 8, 2025
