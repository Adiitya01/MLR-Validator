import logging
import sys
import tempfile
import shutil
import traceback
from typing import List
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
import time
import json
from queue import Queue
from threading import Lock
from uuid import uuid4
from sqlalchemy import text
from db import SessionLocal
from datetime import datetime
from mongo_db import validation_collection, retry_db, validation_collection_v2
from mongo_schema import StorageOptimizer, ConfidenceScoringOptimizer
from db import SessionLocal
from dataclasses import asdict

# Auth imports
from database import SessionLocal as AuthSessionLocal, get_db
from security import hash_password, verify_password, create_access_token
from schemas import UserCreate, UserLogin, UserResponse, TokenResponse

# Import get_current_user dependency
from security import get_current_user


from dotenv import load_dotenv
import os

load_dotenv()

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
from Superscript import extract_footnotes
from conversion import build_validation_dataframe
from Gemini_version import StatementValidator
from validation_api import drug_router, research_router


app = FastAPI(title="MLR validation tool")

# Register both pipeline routers
app.include_router(drug_router)
app.include_router(research_router)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
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


@app.get("/mongodb-status")
def mongodb_status():
    """
    Check MongoDB setup status and collection details
    """
    try:
        from mongo_db import mongo_db as db
        
        # Check connection
        db.command('ping')
        
        # Get collection info
        validation_v2_info = {
            "name": "validation_results_v2",
            "document_count": validation_collection_v2.count_documents({}),
            "indexes": [{"name": idx["name"]} for idx in validation_collection_v2.list_indexes()]
        }
        
        legacy_info = {
            "name": "validation_results",
            "document_count": validation_collection.count_documents({})
        }
        
        return {
            "status": "ok",
            "mongodb_connected": True,
            "validation_results_v2": validation_v2_info,
            "validation_results_legacy": legacy_info,
            "schema_initialized": True
        }
    
    except Exception as e:
        logger.error(f"MongoDB status check failed: {str(e)}")
        return {
            "status": "error",
            "mongodb_connected": False,
            "error": str(e)
        }


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
def get_validation_history(authorization: str = Header(None)):
    """
    Get validation history for the logged-in user ONLY.
    Requires JWT token in Authorization header.
    """
    try:
        # Extract token from "Bearer <token>"
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
        
        token = authorization.replace("Bearer ", "")
        
        # Decode JWT to get user_id
        from security import decode_token
        payload = decode_token(token)
        
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Token missing user_id")
        
        logger.info(f"Fetching validation history for user_id: {user_id}")
        
        session = SessionLocal()
        
        # Query only THIS USER's brochures
        query = text("""
            SELECT id, brochure_path, status, created_at 
            FROM brochures 
            WHERE user_id = :user_id
            ORDER BY created_at DESC
        """)
        
        result = session.execute(query, {"user_id": user_id})
        history = []
        
        for row in result:
            brochure_id = str(row[0])
            
            # Fetch validation results from MongoDB (try v2 first, then legacy)
            doc = validation_collection_v2.find_one(
                {"brochure_id": brochure_id},
                {"_id": 0}
            )
            
            # Fallback to legacy collection if v2 not found
            if not doc:
                doc = validation_collection.find_one(
                    {"brochure_id": brochure_id},
                    {"_id": 0}
                )
            
            # Build history item
            history_item = {
                "id": brochure_id,
                "filename": row[1].split('/')[-1] if row[1] else "Unknown",
                "status": row[2],
                "created_at": row[3].isoformat() if row[3] else None,
                "results": doc.get("results", []) if doc else [],
                "total_statements": doc.get("total_statements", 0) if doc else 0
            }
            
            history.append(history_item)
        
        session.close()
        logger.info(f"Returning {len(history)} brochures for user_id: {user_id}")
        return {"history": history}
    
    
    except Exception as e:
        logger.error(f"Error fetching validation history: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch validation history")


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
    reference_pdfs: List[UploadFile] = File(...)
):
    """
    Unified pipeline endpoint - PUBLIC (no authentication required).
    """

    # Clear logs from previous runs to ensure clean state
    with logs_lock:
        recent_logs.clear()

    logger.info(f"[PIPELINE START] Brochure: {brochure_pdf.filename}, References: {len(reference_pdfs)}")
    print(f"\n{'='*70}")
    print(f"PIPELINE STARTED")
    print(f"Brochure: {brochure_pdf.filename}")
    print(f"Reference PDFs: {len(reference_pdfs)}")
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

            # STEP 2: Extract citations
            logger.info("Step 2: Extracting citations...")
            try:
                extraction_result = extract_citations(brochure_path)
                logger.info(f"  Extracted {len(extraction_result.in_text)} statements from brochure")
            except Exception as e:
                logger.error(f"Extraction failed: {str(e)}")
                raise HTTPException(status_code=400, detail=f"Extraction failed: {str(e)}")

            # STEP 3: Convert to DataFrame
            logger.info("Step 3: Converting to DataFrame...")
            try:
                validation_df = convert_to_dataframe(extraction_result, pdf_files_dict)
                logger.info(f"  DataFrame created with {len(validation_df)} rows")
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

            # ---------- SAVE RESULTS TO MONGODB ----------
            # Convert ValidationResult dataclass objects to dictionaries
            results_dicts = [asdict(r) for r in results]

            # Improve confidence scoring consistency
            logger.info("Normalizing confidence scores...")
            results_dicts = ConfidenceScoringOptimizer.normalize_confidence_scores(results_dicts)

            # Optimize storage by hashing evidence texts
            logger.info("Optimizing storage...")
            results_optimized = [StorageOptimizer.compress_result(r) for r in results_dicts]

            # Build optimized document for v2 collection
            mongo_doc = {
                "brochure_id": brochure_id,
                "brochure_name": brochure_pdf.filename,
                "total_statements": len(results_optimized),
                "results": results_optimized,
                "schema_version": 2,
                "created_at": datetime.utcnow(),
                "processing_time_seconds": time.time() - pipeline_start
            }

            # Insert with retry-safe logic and idempotency
            try:
                inserted_id = retry_db.insert_one_with_retry(
                    mongo_doc, 
                    idempotency_key=brochure_id
                )
                logger.info(f"Saved validation results to MongoDB v2: {inserted_id}")
                logger.info(f"Storage optimization: Evidence texts hashed (SHA256)")
                logger.info(f"Confidence scoring: Normalized with reasoning")
            except Exception as e:
                logger.error(f"Failed to save to MongoDB: {str(e)}")
                # Fall back to legacy collection if v2 fails
                try:
                    validation_collection.insert_one(mongo_doc)
                    logger.warning("Saved to legacy collection (fallback)")
                except Exception as fallback_error:
                    logger.error(f"Failed to save to both collections: {str(fallback_error)}")
                    raise HTTPException(status_code=500, detail="Failed to persist validation results")

            # ---------- UPDATE STATUS ----------
            db = SessionLocal()
            db.execute(
                text("""
                    UPDATE brochures
                    SET status = :status
                    WHERE id = :id
                """),
                {
                    "status": "completed",
                    "id": brochure_id
                }
            )
            db.commit()
            db.close()
            logger.info(f"Updated brochure status to completed: {brochure_id}")

            # ---------- SUCCESS RESPONSE ----------
            pipeline_elapsed = time.time() - pipeline_start
            logger.info(f"[PIPELINE COMPLETE] Total time: {pipeline_elapsed:.2f}s, Results: {len(results)}")

            print(f"\n{'='*70}")
            print(f"PIPELINE COMPLETED SUCCESSFULLY")
            print(f"Total time: {pipeline_elapsed:.2f} seconds")
            print(f"Statements validated: {len(results)}")
            print(f"{'='*70}\n")

            response = {
                "status": "success",
                "brochure_id": brochure_id,
                "pipeline_stages": 4,
                "total_statements": len(results_optimized),
                "results": results_optimized
            }

            return response
        except HTTPException:
            raise
        except Exception as e:
            # ---------- UPDATE STATUS TO FAILED ----------
            db = SessionLocal()
            db.execute(
                text("""
                    UPDATE brochures
                    SET status = :status
                    WHERE id = :id
                """),
                {
                    "status": "failed",
                    "id": brochure_id
                }
            )
            db.commit()
            db.close()
            logger.error(f"Updated brochure status to failed: {brochure_id}")

            error_trace = traceback.format_exc()
            print(f"\n{'='*70}")
            print(f"❌ PIPELINE FAILED")
            print(f"{'='*70}")
            print(f"Error: {str(e)}")
            print(f"\n📋 Traceback:")
            print(error_trace)
            print(f"{'='*70}\n")

            raise HTTPException(status_code=500, detail=str(e))


# ============================================
# 🔐 AUTHENTICATION ENDPOINTS
# ============================================

@app.post("/signup")
def signup(user: UserCreate):
    """Register a new user"""
    # DEBUG: Print database URL
    import os
    print("DEBUG: DATABASE_URL =", os.getenv("DATABASE_URL"))
    
    db = AuthSessionLocal()
    
    try:
        # Normalize email: trim whitespace and convert to lowercase
        email = user.email.strip().lower()
        print(f"DEBUG: Normalized email = {email}")
        
        # Check if email already exists
        existing = db.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": email}
        ).fetchone()
        
        # DEBUG: Print query result
        print(f"DEBUG: Existing user query result = {existing}")
        
        # Also debug: check all emails in database
        all_emails = db.execute(text("SELECT email FROM users")).fetchall()
        print(f"DEBUG: All emails in database = {[e[0] for e in all_emails]}")
        
        if existing:
            db.close()
            print(f"DEBUG: Email {email} already exists")
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Insert new user
        result = db.execute(
            text("""
                INSERT INTO users (email, password_hash, full_name, created_at)
                VALUES (:email, :password_hash, :full_name, :created_at)
                RETURNING id, email, full_name
            """),
            {
                "email": email,
                "password_hash": hash_password(user.password),
                "full_name": user.full_name or email.split("@")[0],
                "created_at": datetime.utcnow()
            }
        )
        
        new_user = result.fetchone()
        db.commit()
        db.close()
        
        # Create access token
        user_id = int(new_user[0]) if hasattr(new_user[0], '__int__') else new_user[0]
        access_token = create_access_token(data={"sub": email, "user_id": user_id})
        
        # Use UserResponse Pydantic model for proper serialization
        user_response = UserResponse(
            id=user_id,
            email=str(new_user[1]),
            full_name=str(new_user[2]) if new_user[2] else None
        )
        
        logger.info(f"✓ User registered: {email}")
        print(f"DEBUG: User registered successfully: {email}")
        
        # Return response with proper JSON serialization
        return {
            "message": "User created successfully",
            "access_token": access_token,
            "token_type": "bearer",
            "user": user_response.model_dump()
        }
        
    except HTTPException:
        db.close()
        raise
    except Exception as e:
        db.rollback()
        db.close()
        logger.error(f"Signup error: {str(e)}")
        print(f"DEBUG: Signup exception: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/login")
def login(user: UserLogin):
    """Login user and return access token"""
    db = AuthSessionLocal()
    
    try:
        # Find user by email
        db_user = db.execute(
            text("SELECT id, email, password_hash, full_name FROM users WHERE email = :email"),
            {"email": user.email}
        ).fetchone()
        
        if not db_user:
            db.close()
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        # Verify password
        if not verify_password(user.password, db_user[2]):
            db.close()
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        db.close()
        
        # Convert id to int (handle UUID type if needed)
        user_id = int(db_user[0]) if hasattr(db_user[0], '__int__') else db_user[0]
        
        # Create access token
        access_token = create_access_token(data={"sub": user.email, "user_id": user_id})
        
        # Use UserResponse Pydantic model for proper serialization
        user_response = UserResponse(
            id=user_id,
            email=str(db_user[1]),
            full_name=str(db_user[3]) if db_user[3] else None
        )
        
        logger.info(f"✓ User logged in: {user.email}")
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": user_response.model_dump()
        }
        
    except HTTPException:
        db.close()
        raise
    except Exception as e:
        db.close()
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
        db.close()


@app.post("/init-db")
def init_db():
    """Initialize users table (run once)"""
    db = AuthSessionLocal()
    
    try:
        # Create users table if not exists
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                full_name VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # Create index on email
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)
        """))
        
        db.commit()
        logger.info("✓ Database tables initialized")
        
        return {"message": "Database initialized successfully"}
        
    except Exception as e:
        db.rollback()
        logger.error(f"DB init error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
        