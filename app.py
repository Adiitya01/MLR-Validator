import logging
import sys
import tempfile
import shutil
import traceback
from typing import List
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header, Form, BackgroundTasks
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
from dataclasses import asdict

# Auth imports
from database import SessionLocal as AuthSessionLocal, get_db
from security import hash_password, verify_password, create_access_token, get_current_user
from schemas import UserCreate, UserLogin, UserResponse, TokenResponse


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

# CORS Middleware - Added BEFORE routers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register both pipeline routers
app.include_router(drug_router)
app.include_router(research_router)


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
    """Check MongoDB connection status"""
    try:
        # PING MongoDB
        client = validation_collection.database.client
        client.admin.command('ping')
        
        # Get collection counts
        v1_count = validation_collection.count_documents({})
        v2_count = validation_collection_v2.count_documents({})
        
        return {
            "status": "connected",
            "message": "✓ MongoDB connection is healthy",
            "collections": {
                "validation_results": v1_count,
                "validation_results_v2": v2_count
            }
        }
    except Exception as e:
        logger.error(f"MongoDB status check failed: {str(e)}")
        return {
            "status": "error",
            "message": f"✗ MongoDB connection failed: {str(e)}"
        }


@app.post("/init-db")
def init_db(db=Depends(get_db)):
    """Initialize PostgreSQL database tables"""
    try:
        if db is None:
            raise HTTPException(status_code=500, detail="Database session not available")
            
        # Create users table if it doesn't exist
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id UUID PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                full_name VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # Ensure columns exist (in case table was created with an older version)
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name VARCHAR(255)"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_email_verified BOOLEAN DEFAULT FALSE"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMP"))
        
        # Create OTP Audit Table
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS user_otp_audit (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) NOT NULL,
                action VARCHAR(50) NOT NULL, -- 'SENT', 'VERIFIED', 'FAILED'
                ip_address VARCHAR(45),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        db.commit()
        return {"status": "success", "message": "✓ User database tables initialized and updated"}
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


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

# FETCH RESULTS FROM MONGODB
# FETCH VALIDATION HISTORY (ALL DATA IN ONE ENDPOINT)

@app.get("/validation-history")
def get_validation_history(current_user: dict = Depends(get_current_user)):
    """Fetch recent validation history from MongoDB for the current user"""
    try:
        user_id = current_user.get("user_id")
        
        # Fetch 20 most recent brochures from V2 collection for this user
        cursor = validation_collection_v2.find(
            {"user_id": user_id}, 
            {"_id": 0, "results": 0} # Exclude full results to keep list light
        ).sort("created_at", -1).limit(20)
        
        history = list(cursor)
        
        # If no history in v2, check legacy
        if not history:
            cursor_legacy = validation_collection.find(
                {}, 
                {"_id": 0, "results": 0}
            ).sort("created_at", -1).limit(10)
            history = list(cursor_legacy)
            
        return {"status": "success", "history": history}
    except Exception as e:
        logger.error(f"Failed to fetch history: {str(e)}")
        # Return empty list on failure but don't crash
        return {"status": "error", "message": str(e), "history": []}


@app.get("/validation-results/{brochure_id}")
def get_brochure_results(brochure_id: str, current_user: dict = Depends(get_current_user)):
    """Fetch all validation statements for a specific brochure (owner only)"""
    try:
        user_id = current_user.get("user_id")
        result = validation_collection_v2.find_one(
            {"brochure_id": brochure_id, "user_id": user_id},
            {"_id": 0}
        )
        
        # If not found in v2, check v1
        if not result:
            result = validation_collection.find_one(
                {"brochure_id": brochure_id, "user_id": user_id},
                {"_id": 0}
            )
            
        if not result:
            raise HTTPException(status_code=404, detail="Validation results not found")
            
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch results: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/job-status/{job_id}")
def get_job_status(job_id: str, current_user: dict = Depends(get_current_user)):
    """Check the status of a background validation job"""
    try:
        user_id = current_user.get("user_id")
        job = validation_collection_v2.find_one(
            {"brochure_id": job_id, "user_id": user_id},
            {"_id": 0, "results": 0} # Don't return results in status check
        )
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
            
        return {
            "status": "success",
            "job_id": job_id,
            "state": job.get("status", "unknown"),
            "filename": job.get("filename"),
            "created_at": job.get("created_at"),
            "message": "Job is " + job.get("status", "unknown")
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Status check failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch results for {brochure_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


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



async def process_validation_job(
    job_id: str,
    brochure_path: str,
    reference_paths: List[str],
    pdf_files_dict: dict,
    validation_type: str,
    brochure_filename: str,
    user_id: str,
    user_email: str,
    tmpdir: str
):
    """Heavy lifting background task for validation"""
    try:
        logger.info(f"🚀 [BACKGROUND JOB] Starting {job_id} ({validation_type})")
        
        # STEP 2: Extract
        if validation_type == "drug":
            extraction_result = extract_drug_superscript_table_data(brochure_path)
        else:
            extraction_result = extract_citations(brochure_path)

        if not extraction_result:
            raise RuntimeError("Extraction failed or produced no results")

        # STEP 3: Convert
        # This part needs to handle both research and drug types correctly
        if validation_type == "drug":
            validation_rows = build_validation_rows_special_case(
                extraction_result,
                {}  # No references mapping for drug tables
            )
            import pandas as pd
            validation_df = pd.DataFrame(validation_rows)
            validation_df['pdf_files_dict'] = [pdf_files_dict] * len(validation_df)
        else:
            validation_df = convert_to_dataframe(extraction_result, pdf_files_dict)
        
        # STEP 4: Validate
        results = validate_statements(validation_df)
        results_dicts = [asdict(r) for r in results]

        # Optimize & Score
        results_optimized = [StorageOptimizer.compress_result(r.copy()) for r in results_dicts]
        results_with_scoring = ConfidenceScoringOptimizer.normalize_confidence_scores(results_optimized)
        
        avg_conf = 0
        if results_with_scoring:
            avg_conf = sum(r.get('confidence_score', 0) for r in results_with_scoring) / len(results_with_scoring)

        # STEP 5: Update MongoDB with Results
        validation_collection_v2.update_one(
            {"brochure_id": job_id},
            {
                "$set": {
                    "status": "completed",
                    "total_statements": len(results),
                    "avg_confidence": avg_conf,
                    "results": results_with_scoring,
                    "completed_at": datetime.utcnow()
                }
            }
        )
        logger.info(f"✅ [JOB COMPLETE] {job_id}")

    except Exception as e:
        logger.error(f"❌ [JOB FAILED] {job_id}: {str(e)}")
        validation_collection_v2.update_one(
            {"brochure_id": job_id},
            {
                "$set": {
                    "status": "failed",
                    "error_message": str(e),
                    "failed_at": datetime.utcnow()
                }
            }
        )
    finally:
        # Cleanup temporary files
        try:
            shutil.rmtree(tmpdir)
            logger.info(f"🧹 [CLEANUP] Deleted temp dir for {job_id}")
        except Exception as e:
            logger.warning(f"⚠️ [CLEANUP FAILED] Could not delete temp dir {tmpdir} for {job_id}: {e}")

@app.post("/run-pipeline")
async def run_pipeline(
    background_tasks: BackgroundTasks,
    brochure_pdf: UploadFile = File(...),
    reference_pdfs: List[UploadFile] = File(...),
    validation_type: str = Form("research"),  # "research" or "drug"
    current_user: dict = Depends(get_current_user)
):
    """
    Unified pipeline endpoint - Starts a background job and returns Job ID.
    """

    # Clear logs from previous runs to ensure clean state
    with logs_lock:
        recent_logs.clear()

    job_id = str(uuid4())
    logger.info(f"[PIPELINE START] Job ID: {job_id}, User: {current_user.get('email')}")
    logger.info(f"  Brochure: {brochure_pdf.filename}, References: {len(reference_pdfs)}")
    logger.info(f"  Validation Type: {validation_type}")
    
    print(f"\n{'='*70}")
    print(f"PIPELINE STARTED (Job ID: {job_id})")
    print(f"Brochure: {brochure_pdf.filename}")
    print(f"Reference PDFs: {len(reference_pdfs)}")
    print(f"Validation Type: {validation_type.upper()}")
    print(f"{'='*70}\n")

    # Initial Validation
    if brochure_pdf.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Brochure must be PDF")

    if not reference_pdfs:
        raise HTTPException(status_code=400, detail="At least one reference PDF required")

    for ref in reference_pdfs:
        if ref.content_type != "application/pdf":
            raise HTTPException(status_code=400, detail="All references must be PDF")
    
    # Create "Processing" record in MongoDB immediately
    mongo_doc = {
        "brochure_id": job_id,
        "user_id": current_user.get("user_id"),
        "user_email": current_user.get("email"),
        "brochure_name": brochure_pdf.filename,
        "filename": brochure_pdf.filename,
        "pipeline_type": validation_type,
        "status": "processing",
        "created_at": datetime.utcnow(),
        "schema_version": 2
    }
    try:
        validation_collection_v2.insert_one(mongo_doc)
        logger.info(f"✓ Initial job record created in MongoDB for {job_id}")
    except Exception as e:
        logger.error(f"Failed to create initial MongoDB record for {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to initialize job: {str(e)}")

    # Prepare files in a temporary directory that stays until background task finishes
    job_tmp_dir = tempfile.mkdtemp()
    
    # Save files to this temp dir
    try:
        logger.info(f"Step 1: Saving uploads to temporary directory {job_tmp_dir}...")
        brochure_path, reference_paths, pdf_files_dict = await save_uploads(
            brochure_pdf, reference_pdfs, job_tmp_dir
        )
        logger.info(f"  Saved {len(reference_paths)} reference PDFs for {job_id}")
        
        # Add background task
        background_tasks.add_task(
            process_validation_job,
            job_id=job_id,
            brochure_path=brochure_path,
            reference_paths=reference_paths, # This parameter is not used in process_validation_job, but kept for consistency if needed later
            pdf_files_dict=pdf_files_dict,
            validation_type=validation_type,
            brochure_filename=brochure_pdf.filename,
            user_id=current_user.get("user_id"),
            user_email=current_user.get("email"),
            tmpdir=job_tmp_dir
        )
        
        logger.info(f"✓ Background task for {job_id} added successfully.")
        return {
            "status": "success",
            "message": "Validation job started in background",
            "job_id": job_id,
            "filename": brochure_pdf.filename
        }
    except HTTPException:
        # If setup fails, delete temp dir and mark job as failed
        shutil.rmtree(job_tmp_dir, ignore_errors=True)
        validation_collection_v2.update_one(
            {"brochure_id": job_id},
            {"$set": {"status": "failed", "error_message": "HTTP Exception during setup", "failed_at": datetime.utcnow()}}
        )
        raise
    except Exception as e:
        # If setup fails, delete temp dir and mark job as failed
        error_trace = traceback.format_exc()
        logger.error(f"PIPELINE SETUP FAILED for {job_id}: {str(e)}\n{error_trace}")
        shutil.rmtree(job_tmp_dir, ignore_errors=True)
        validation_collection_v2.update_one(
            {"brochure_id": job_id},
            {"$set": {"status": "failed", "error_message": str(e), "failed_at": datetime.utcnow()}}
        )
        raise HTTPException(status_code=500, detail=f"Failed to start validation job: {str(e)}")


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@app.post("/signup", response_model=TokenResponse)
async def signup(user: UserCreate, db=Depends(get_db)):
    """Create a new user account"""
    try:
        if db is None:
            raise HTTPException(status_code=500, detail="Database connection failed")
            
        # Check if user already exists
        result = db.execute(
            text("SELECT email FROM users WHERE email = :email"),
            {"email": user.email}
        ).fetchone()
        
        if result:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Create new user
        new_id = str(uuid4())
        hashed_pwd = hash_password(user.password)
        
        db.execute(
            text("""
                INSERT INTO users (id, email, password_hash, full_name, created_at, updated_at)
                VALUES (:id, :email, :password_hash, :full_name, :created_at, :updated_at)
            """),
            {
                "id": new_id,
                "email": user.email,
                "password_hash": hashed_pwd,
                "full_name": user.full_name,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        )
        db.commit()
        
        # Create access token
        access_token = create_access_token(data={"user_id": new_id, "email": user.email})
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": new_id,
                "email": user.email,
                "full_name": user.full_name
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Signup failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Signup failed: {str(e)}")


@app.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin, db=Depends(get_db)):
    """Authenticate user and return token"""
    try:
        if db is None:
            raise HTTPException(status_code=500, detail="Database connection failed")
            
        # Find user
        row = db.execute(
            text("SELECT id, email, password_hash, full_name FROM users WHERE email = :email"),
            {"email": credentials.email}
        ).fetchone()
        
        if not row or not verify_password(credentials.password, row[2]):
            raise HTTPException(status_code=401, detail="Incorrect email or password")
        
        # Update last login time or similar if needed...
        
        # Create token
        access_token = create_access_token(data={"user_id": str(row[0]), "email": row[1]})
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": str(row[0]),
                "email": row[1],
                "full_name": row[3]
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")


@app.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user), db=Depends(get_db)):
    """Get current logged in user profile"""
    try:
        user_id = current_user.get("user_id")
        row = db.execute(
            text("SELECT id, email, full_name, is_email_verified FROM users WHERE id = :id"),
            {"id": user_id}
        ).fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
            
        return {
            "id": str(row[0]),
            "email": row[1],
            "full_name": row[2],
            "is_email_verified": row[3]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Auth check failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Auth verification failed")

# ============================================================================
# OTP AUTHENTICATION (NEW)
# ============================================================================
from otp_service import generate_otp, store_otp, send_otp_email, check_resend_cooldown, verify_otp_hash
from fastapi import Request

@app.post("/auth/send-otp")
async def send_otp(request: Request, payload: dict, db=Depends(get_db)):
    """Step 8: Send OTP to email"""
    email = payload.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    
    # Check if user exists
    user = db.execute(text("SELECT id FROM users WHERE email = :email"), {"email": email}).fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check cooldown
    if check_resend_cooldown(email):
        raise HTTPException(status_code=429, detail="Please wait 60 seconds before resending")
    
    otp = generate_otp()
    
    # Store in Redis
    store_otp(email, otp)
    
    # Send Email
    success = send_otp_email(email, otp)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send email. Check SendGrid config.")
    
    # Audit Row
    db.execute(text("""
        INSERT INTO user_otp_audit (email, action, ip_address)
        VALUES (:email, 'SENT', :ip)
    """), {"email": email, "ip": request.client.host})
    db.commit()
    
    return {"status": "success", "message": "OTP sent to your email"}

@app.post("/auth/verify-otp")
async def verify_otp(request: Request, payload: dict, db=Depends(get_db)):
    """Step 9: Verify OTP and mark user as verified"""
    email = payload.get("email")
    otp = payload.get("otp")
    
    if not email or not otp:
        raise HTTPException(status_code=400, detail="Email and OTP are required")
    
    verified, message = verify_otp_hash(email, otp)
    
    if not verified:
        db.execute(text("""
            INSERT INTO user_otp_audit (email, action, ip_address)
            VALUES (:email, 'FAILED', :ip)
        """), {"email": email, "ip": request.client.host})
        db.commit()
        raise HTTPException(status_code=400, detail=message)
    
    # Step 10: Mark user verified
    db.execute(text("""
        UPDATE users 
        SET is_email_verified = TRUE, 
            email_verified_at = :now
        WHERE email = :email
    """), {"email": email, "now": datetime.utcnow()})
    
    db.execute(text("""
        INSERT INTO user_otp_audit (email, action, ip_address)
        VALUES (:email, 'VERIFIED', :ip)
    """), {"email": email, "ip": request.client.host})
    
    db.commit()
    
    return {"status": "success", "message": "Email verified successfully"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
        