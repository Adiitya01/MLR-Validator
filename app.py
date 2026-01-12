import logging
import sys
import tempfile
import shutil
import traceback
from typing import List
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
import time
import json
from queue import Queue
from threading import Lock
from uuid import uuid4
# from sqlalchemy import text
# from db import SessionLocal
from datetime import datetime
# from mongo_db import validation_collection, retry_db, validation_collection_v2
# from mongo_schema import StorageOptimizer, ConfidenceScoringOptimizer
from dataclasses import asdict

# Auth imports disabled
# from database import SessionLocal as AuthSessionLocal, get_db
# from security import hash_password, verify_password, create_access_token
# from schemas import UserCreate, UserLogin, UserResponse, TokenResponse

# from security import get_current_user


from dotenv import load_dotenv
import os

load_dotenv()

print("DEBUG: DATABASE_URL =", os.getenv("DATABASE_URL"))


# Configure logging with custom handler for polling
class QueueHandler(logging.Handler):
    def emit(self, record):
        try:
            log_entry = {
                "timestamp": self.format(record),
                "level": record.levelname,
                "type": "info" if record.levelname == "INFO" else ("error" if record.levelname == "ERROR" else "validating")
            }
            with logs_lock:
                recent_logs.append(log_entry)
                # Keep only last 100 logs in memory
                if len(recent_logs) > 100:
                    recent_logs.pop(0)
        except Exception:
            self.handleError(record)

# Global logs list for polling from UI
recent_logs = []
logs_lock = Lock()

# Configure the root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

# Clear any existing handlers
root_logger.handlers = []

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
console_handler.stream.reconfigure(encoding='utf-8')  # Force UTF-8 encoding
formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s')
console_handler.setFormatter(formatter)
root_logger.addHandler(console_handler)

# File handler
file_handler = logging.FileHandler('app.log')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)
root_logger.addHandler(file_handler)

# Custom queue handler
queue_handler = QueueHandler()
queue_handler.setFormatter(formatter)
root_logger.addHandler(queue_handler)

# Reduce verbosity of third-party libraries
logging.getLogger('pymongo').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('google').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Test logging to verify it's working
logger = logging.getLogger(__name__)
logger.info("Logging initialized and working!")

# ==== IMPORT YOUR PIPELINE FILES ====
from Superscript import extract_footnotes, extract_drug_superscript_table_data
from conversion import build_validation_dataframe, build_validation_rows_special_case
from Gemini_version import StatementValidator
from validation_api import drug_router, research_router


app = FastAPI(title="MLR validation tool")

# Register both pipeline routers
app.include_router(drug_router)
app.include_router(research_router)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/health")
def health():
    """Simple health check"""
    return {"status": "ok"}


@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "MLR Validator Backend",
        "message": "Backend is running successfully 🚀"
    }


@app.get("/mongodb-status")
def mongodb_status():
    return {"status": "disabled", "message": "Database is currently disabled"}


# ============================================================================
# LOGS POLLING ENDPOINT
# ============================================================================

@app.get("/logs/latest")
async def get_latest_logs():
    """
    Returns all recent logs collected so far.
    The frontend polls this endpoint every 100ms to get updates.
    """
    with logs_lock:
        return {"logs": recent_logs}


# ============================================================================
# FETCH RESULTS FROM MONGODB
# ============================================================================

# ============================================================================
# FETCH VALIDATION HISTORY (ALL DATA IN ONE ENDPOINT)
# ============================================================================

@app.get("/validation-history")
def get_validation_history():
    return {"history": []}


# ============================================================================
# MAIN PIPELINE: ONE REQUEST = FULL EXECUTION
# ============================================================================

async def save_uploads(brochure_pdf: UploadFile, reference_pdfs: List[UploadFile], tmpdir: str):
    """
    STEP 1: Save all uploaded PDFs to isolated temp workspace

    IMPORTANT:
    - Matching uses ORIGINAL FILENAMES
    - Temp paths are ONLY for Gemini upload
    """
    
    # Save brochure
    brochure_path = f"{tmpdir}/brochure.pdf"
    brochure_content = await brochure_pdf.read()
    with open(brochure_path, "wb") as f:
        f.write(brochure_content)
    
    reference_paths = []
    pdf_files_dict = {}

    for ref in reference_pdfs:
        # Temp path (transport only)
        ref_path = f"{tmpdir}/{ref.filename}"
        ref_content = await ref.read()

        with open(ref_path, "wb") as f:
            f.write(ref_content)

        reference_paths.append(ref_path)

        # ✅ KEY FIX: use ORIGINAL filename as key
        pdf_files_dict[ref.filename] = {
            "temp_path": ref_path,
            "content": ref_content
        }

    return brochure_path, reference_paths, pdf_files_dict


def extract_citations(brochure_path: str):
    """
    STEP 2: Extract superscripts + statements from brochure PDF
    Returns: extraction_result with in_text[] and references[]
    """
    
    extraction_result = extract_footnotes(brochure_path)
    
    if not extraction_result.in_text:
        raise RuntimeError("No in-text citations extracted from brochure")
    
    return extraction_result


def convert_to_dataframe(extraction_result, pdf_files_dict: dict):
    """
    STEP 3: Convert extraction results to validation DataFrame
    Returns: validation_df with all necessary columns
    """
    
    validation_df = build_validation_dataframe(
        extraction_result.in_text,
        extraction_result.references
    )
    
    if validation_df.empty:
        raise RuntimeError("Conversion produced empty validation DataFrame")
    
    # Add PDF content dictionary to each row
    validation_df['pdf_files_dict'] = [pdf_files_dict] * len(validation_df)
    
    return validation_df

def validate_statements(validation_df):
    """
    STEP 4: Run Gemini validation against reference PDFs
    Returns: list of validation results
    """
    
    try:
        logger.info(f"[VALIDATE STATEMENTS] Starting validation pipeline")
        print(f"\n{'='*70}")
        print(f"VALIDATION SERVICE STARTED")
        print(f"Statements to validate: {len(validation_df)}")
        print(f"{'='*70}\n")
        
        start_time = time.time()
        validator = StatementValidator()
        
        # Test Gemini connection first
        logger.info("Testing Gemini API connection...")
        if not validator.llm.test_connection():
            logger.error("Gemini API connection failed")
            raise RuntimeError("Gemini API connection failed")
        
        logger.info("Connection successful, starting validation...")
        results = validator.validate_dataframe(validation_df)
        
        elapsed = time.time() - start_time
        logger.info(f"[VALIDATE STATEMENTS COMPLETE] Total time: {elapsed:.2f}s")
        print(f"\nValidation service completed in {elapsed:.2f} seconds")
        
        if not results:
            raise RuntimeError("No results returned from validation")
        
        return results
    except Exception as e:
        logger.error(f"Validation error: {str(e)}")
        raise



@app.post("/run-pipeline")
async def run_pipeline(
    brochure_pdf: UploadFile = File(...),
    reference_pdfs: List[UploadFile] = File(...),
    validation_type: str = Form("research")  # "research" or "drug"
):
    """
    Unified pipeline endpoint - PUBLIC (no authentication required).
    
    Args:
        brochure_pdf: PDF file to validate
        reference_pdfs: Reference PDF files
        validation_type: "research" (default) or "drug" for special case drug tables
    """

    # Clear logs from previous runs to ensure clean state
    with logs_lock:
        recent_logs.clear()

    logger.info(f"[PIPELINE START] Brochure: {brochure_pdf.filename}, References: {len(reference_pdfs)}")
    logger.info(f"  Validation Type: {validation_type}")
    
    print(f"\n{'='*70}")
    print(f"PIPELINE STARTED")
    print(f"Brochure: {brochure_pdf.filename}")
    print(f"Reference PDFs: {len(reference_pdfs)}")
    print(f"Validation Type: {validation_type.upper()}")
    print(f"{'='*70}\n")

    pipeline_start = time.time()

    # ---------- VALIDATION ----------
    if brochure_pdf.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Brochure must be PDF")

    if not reference_pdfs:
        raise HTTPException(status_code=400, detail="At least one reference PDF required")

    for ref in reference_pdfs:
        if ref.content_type != "application/pdf":
            raise HTTPException(status_code=400, detail="All references must be PDF")
    # ---------- SKIP DATABASE FOR NOW - FOCUS ON VALIDATION ----------
    brochure_id = str(uuid4())
    logger.info(f"Pipeline ID: {brochure_id}")

    # ---------- ISOLATED EXECUTION CONTEXT ----------
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            # STEP 1: Save uploads
            logger.info("Step 1: Saving uploads...")
            brochure_path, reference_paths, pdf_files_dict = await save_uploads(
                brochure_pdf, reference_pdfs, tmpdir
            )
            logger.info(f"  Saved {len(reference_paths)} reference PDFs")

            # STEP 2: Extract based on user-selected pipeline
            logger.info(f"Step 2: Extracting ({validation_type} mode)...")
            try:
                if validation_type == "drug":
                    # Drug table extraction
                    extraction_result = extract_drug_superscript_table_data(brochure_path)
                    logger.info(f"  Extracted {len(extraction_result)} drug table records")
                    
                    # DEBUG: Log first few extracted records
                    logger.info("  📋 First 3 extracted records:")
                    for i, item in enumerate(extraction_result[:3], 1):
                        logger.info(f"    Record {i}: {item}")
                else:
                    # Research paper extraction
                    extraction_result = extract_citations(brochure_path)
                    logger.info(f"  Extracted {len(extraction_result.in_text)} statements from brochure")
                    
                    # DEBUG: Log first few extracted records
                    logger.info("  📋 First 3 extracted records:")
                    for i, item in enumerate(extraction_result.in_text[:3], 1):
                        logger.info(f"    Record {i}: {item}")
                        
            except Exception as e:
                logger.error(f"Extraction failed: {str(e)}")
                raise HTTPException(status_code=400, detail=f"Extraction failed: {str(e)}")

            # STEP 3: Convert based on user-selected pipeline
            logger.info(f"Step 3: Converting to validation format ({validation_type} mode)...")
            try:
                if validation_type == "drug":
                    # Drug validation rows (list of dicts)
                    validation_rows = build_validation_rows_special_case(
                        extraction_result,
                        {}  # No references mapping for drug tables
                    )
                    logger.info(f"  Generated {len(validation_rows)} validation rows")
                    
                    # Convert to DataFrame for compatibility with validator
                    import pandas as pd
                    validation_df = pd.DataFrame(validation_rows)
                    
                    # Add pdf_files_dict column (required by validator)
                    validation_df['pdf_files_dict'] = [pdf_files_dict] * len(validation_df)
                    
                else:
                    # Research paper dataframe
                    validation_df = convert_to_dataframe(extraction_result, pdf_files_dict)
                    logger.info(f"  DataFrame created with {len(validation_df)} rows")
                
                # DEBUG: Log first few converted statements
                logger.info("  📋 First 3 converted statements:")
                for i, row in validation_df.head(3).iterrows():
                    logger.info(f"    Statement {i+1}: {row['statement']}")
                    
            except Exception as e:
                logger.error(f"Conversion failed: {str(e)}")
                raise HTTPException(status_code=400, detail=f"Conversion failed: {str(e)}")

            # STEP 4: Validate statements
            logger.info("Step 4: Starting Gemini validation...")
            try:
                results = validate_statements(validation_df)
            except Exception as e:
                logger.error(f"Validation failed: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")

            # ---------- NO DATABASE STORAGE ----------
            results_dicts = [asdict(r) for r in results]
            
            # Success Response
            pipeline_elapsed = time.time() - pipeline_start
            logger.info(f"[PIPELINE COMPLETE] Total time: {pipeline_elapsed:.2f}s, Results: {len(results)}")

            response = {
                "status": "success",
                "brochure_id": brochure_id,
                "pipeline_stages": 4,
                "total_statements": len(results),
                "results": results_dicts
            }

            return response
        except HTTPException:
            raise
        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"PIPELINE FAILED: {str(e)}\n{error_trace}")
            raise HTTPException(status_code=500, detail=str(e))


# Authentication endpoints disabled
"""
@app.post("/signup")
def signup(user: UserCreate):
    ...
"""
        