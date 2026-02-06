import logging
import sys
import tempfile
import shutil
import traceback
from typing import List
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header, Form, BackgroundTasks, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
import time
import json
from queue import Queue
from threading import Lock
from uuid import uuid4
from sqlalchemy import text
from dataclasses import asdict
from datetime import datetime
from db import SessionLocal
from mongo_db import validation_collection, retry_db, validation_collection_v2
from mongo_schema import StorageOptimizer, ConfidenceScoringOptimizer

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

# In-memory job status tracker (since DB is bypassed)
jobs_status = {}
status_lock = Lock()

# ============================================================================
# WEBSOCKET CONNECTION MANAGER (for real-time status updates)
# ============================================================================
class ConnectionManager:
    """Manages WebSocket connections for real-time job status updates"""
    def __init__(self):
        self.active_connections: dict = {}  # job_id -> list of WebSocket connections
        self.lock = Lock()

    async def connect(self, job_id: str, websocket: WebSocket):
        await websocket.accept()
        with self.lock:
            if job_id not in self.active_connections:
                self.active_connections[job_id] = []
            self.active_connections[job_id].append(websocket)
        logger.info(f"[WS] Client connected to job {job_id}")

    def disconnect(self, job_id: str, websocket: WebSocket):
        with self.lock:
            if job_id in self.active_connections:
                if websocket in self.active_connections[job_id]:
                    self.active_connections[job_id].remove(websocket)
                if not self.active_connections[job_id]:
                    del self.active_connections[job_id]
        logger.info(f"[WS] Client disconnected from job {job_id}")

    async def broadcast_status(self, job_id: str, status: dict):
        """Broadcast status update to all connected clients for a job"""
        with self.lock:
            connections = self.active_connections.get(job_id, []).copy()
        
        for websocket in connections:
            try:
                await websocket.send_json(status)
            except Exception as e:
                logger.warning(f"[WS] Failed to send to client: {e}")

    def get_connection_count(self, job_id: str) -> int:
        with self.lock:
            return len(self.active_connections.get(job_id, []))

# Global WebSocket manager instance
ws_manager = ConnectionManager()

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
logging.getLogger("python_multipart").setLevel(logging.WARNING) # Silence multipart noise
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
os.makedirs("test_results", exist_ok=True)
os.makedirs("output", exist_ok=True)

# Test logging to verify it's working
logger = logging.getLogger(__name__)
logger.info("Logging initialized and working!")

# ==== IMPORT YOUR PIPELINE FILES ====
from Superscript import extract_footnotes, extract_drug_superscript_table_data
from conversion import build_validation_dataframe, build_validation_rows_special_case
from Gemini_version import StatementValidator
from validation_api import drug_router, research_router

app = FastAPI(title="MLR validation tool")

# CORS Middleware - Permissive configuration for POC
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# FORCE CORS ON EVERYTHING (Safety Net)
@app.middleware("http")
async def add_cors_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "*"
    return response

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
        "message": "Backend is running successfully"
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
            "message": "[OK] MongoDB connection is healthy",
            "collections": {
                "validation_results": v1_count,
                "validation_results_v2": v2_count
            }
        }
    except Exception as e:
        logger.error(f"MongoDB status check failed: {str(e)}")
        return {
            "status": "error",
            "message": f"[ERROR] MongoDB connection failed: {str(e)}"
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
        return {"status": "success", "message": "[OK] User database tables initialized and updated"}
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

# ============================================================================
# WEBSOCKET ENDPOINT (Real-time job status updates)
# ============================================================================

@app.websocket("/ws/job/{job_id}")
async def websocket_job_status(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint for real-time job status updates.
    
    Clients can connect to receive instant status updates instead of polling.
    The connection stays open until the job completes or fails.
    
    Usage: ws://localhost:8000/ws/job/{job_id}
    """
    import asyncio
    
    await ws_manager.connect(job_id, websocket)
    
    try:
        while True:
            # Get current status from in-memory tracker
            with status_lock:
                status = jobs_status.get(job_id, {}).copy()
            
            if not status:
                # Try MongoDB if not in memory
                try:
                    mongo_status = validation_collection_v2.find_one(
                        {"brochure_id": job_id},
                        {"_id": 0, "results": 0}  # Exclude large fields
                    )
                    if mongo_status:
                        status = {
                            "status": mongo_status.get("status", "unknown"),
                            "filename": mongo_status.get("filename", ""),
                            "created_at": str(mongo_status.get("created_at", "")),
                            "total_statements": mongo_status.get("total_statements", 0)
                        }
                except Exception:
                    pass
            
            # Send status update
            if status:
                await websocket.send_json({
                    "job_id": job_id,
                    "status": status.get("status", "unknown"),
                    "filename": status.get("filename", ""),
                    "created_at": status.get("created_at", ""),
                    "message": f"Job is {status.get('status', 'unknown')}"
                })
                
                # If job completed or failed, close the connection
                if status.get("status") in ["completed", "failed"]:
                    await websocket.send_json({
                        "job_id": job_id,
                        "status": status.get("status"),
                        "final": True,
                        "message": f"Job {status.get('status')}. Connection closing."
                    })
                    break
            else:
                await websocket.send_json({
                    "job_id": job_id,
                    "status": "not_found",
                    "message": "Job not found"
                })
            
            # Wait before next update (1 second interval)
            await asyncio.sleep(1)
            
    except WebSocketDisconnect:
        ws_manager.disconnect(job_id, websocket)
        logger.info(f"[WS] Client disconnected from job {job_id}")
    except Exception as e:
        logger.error(f"[WS] Error in WebSocket for job {job_id}: {e}")
        ws_manager.disconnect(job_id, websocket)

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
    """Fetch results from MongoDB with local JSON fallback"""
    try:
        user_id = current_user.get("user_id")
        
        # 1. Try MongoDB V2 first
        result = validation_collection_v2.find_one(
            {"brochure_id": brochure_id, "user_id": user_id},
            {"_id": 0}
        )
        
        if result:
            return result
            
        # 2. Try MongoDB Legacy fallback
        result = validation_collection.find_one(
            {"brochure_id": brochure_id, "user_id": user_id},
            {"_id": 0}
        )
        
        if result:
            return result
            
        # 3. Last resort: Fetch from local JSON file (bypass mode fallback)
        file_path = f"test_results/{brochure_id}_results.json"
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                return json.load(f)
                
        raise HTTPException(status_code=404, detail="Validation results not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch results for {brochure_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/job-status/{job_id}")
def get_job_status(job_id: str, current_user: dict = Depends(get_current_user)):
    """Check the status of a background validation job"""
    try:
        # Check in-memory status tracker first
        with status_lock:
            if job_id in jobs_status:
                job = jobs_status[job_id]
                return {
                    "status": "success",
                    "job_id": job_id,
                    "state": job.get("status", "unknown"),
                    "filename": job.get("filename"),
                    "created_at": job.get("created_at"),
                    "message": "Job is " + job.get("status", "unknown")
                }
        
        # Try MongoDB
        user_id = current_user.get("user_id")
        job = validation_collection_v2.find_one(
            {"brochure_id": job_id, "user_id": user_id},
            {"_id": 0, "results": 0}
        )
        
        if job:
            return {
                "status": "success",
                "job_id": job_id,
                "state": job.get("status", "unknown"),
                "filename": job.get("filename"),
                "created_at": job.get("created_at"),
                "message": "Job is " + job.get("status", "unknown")
            }
        raise HTTPException(status_code=404, detail="Job not found")
            
        # return {
        #     "status": "success",
        #     "job_id": job_id,
        #     "state": job.get("status", "unknown"),
        #     "filename": job.get("filename"),
        #     "created_at": job.get("created_at"),
        #     "message": "Job is " + job.get("status", "unknown")
        # }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Status check failed for {job_id}: {str(e)}")
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
    async def _cleanup():
        try:
            shutil.rmtree(tmpdir)
            logger.info(f"[CLEANUP] Deleted temp dir for {job_id}")
        except Exception:
            logger.warning(f"[CLEANUP FAILED] Could not delete temp dir {tmpdir} for {job_id}")

    # Explicit phase management
    status = "UNKNOWN"
    try:
        logger.info(f"[JOB START] Starting {job_id} ({validation_type})")
        with status_lock:
            if job_id in jobs_status:
                jobs_status[job_id]["status"] = "processing"
        
        # STEP 2: Extract
        if validation_type == "drug":
            extraction_result = extract_drug_superscript_table_data(brochure_path)
        else:
            extraction_result = extract_citations(brochure_path)

        if not extraction_result:
            raise RuntimeError("Extraction failed or produced no results")

        # SAVE STEP 2: Superscript Output
        os.makedirs("output", exist_ok=True)
        try:
            # Handle DocumentExtraction object or list
            if hasattr(extraction_result, "model_dump"):
                raw_data = extraction_result.model_dump()
            elif hasattr(extraction_result, "__dict__"):
                raw_data = extraction_result.__dict__
            else:
                raw_data = extraction_result
            with open("output/superscript_output.json", "w", encoding="utf-8") as f:
                json.dump(raw_data, f, indent=2, ensure_ascii=False)
            logger.info("[DEBUG] Saved output/superscript_output.json")
        except Exception as e:
            logger.warning(f"Failed to save superscript_output: {e}")

        # STEP 3: Convert
        if validation_type == "drug":
            validation_rows = build_validation_rows_special_case(extraction_result, {})
            import pandas as pd
            validation_df = pd.DataFrame(validation_rows)
            validation_df['pdf_files_dict'] = [pdf_files_dict] * len(validation_df)
        else:
            validation_df = convert_to_dataframe(extraction_result, pdf_files_dict)
        
        # SAVE STEP 3: Conversion Output
        try:
            # Convert DF to list of dicts for JSON saving
            conv_data = validation_df.drop(columns=['pdf_files_dict'], errors='ignore').to_dict(orient='records')
            with open("output/conversion_output.json", "w", encoding="utf-8") as f:
                json.dump(conv_data, f, indent=2, ensure_ascii=False)
            logger.info("[DEBUG] Saved output/conversion_output.json")
        except Exception as e:
            logger.warning(f"Failed to save conversion_output: {e}")
        
        # STEP 4: Validate
        results = validate_statements(validation_df)
        results_dicts = [asdict(r) for r in results]

        # Optimize & Score
        # SKIP StorageOptimizer to keep full matched_evidence for UI display
        results_optimized = [r.copy() for r in results_dicts]
        results_with_scoring = ConfidenceScoringOptimizer.normalize_confidence_scores(results_optimized)
        
        avg_conf = 0
        if results_with_scoring:
            avg_conf = sum(r.get('confidence_score', 0) for r in results_with_scoring) / len(results_with_scoring)

        # STEP 5: Update MongoDB with Results
        try:
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
            logger.info(f"[OK] MongoDB updated with results for {job_id}")
        except Exception as e:
            logger.error(f"Failed to update MongoDB for {job_id}: {str(e)}")

        # SAVE STEP 4: Validation Output
        try:
            with open("output/validation_output.json", "w", encoding="utf-8") as f:
                json.dump(results_with_scoring, f, indent=2, ensure_ascii=False)
            logger.info("[DEBUG] Saved output/validation_output.json")
        except Exception as e:
            logger.warning(f"Failed to save validation_output: {e}")
        
        # Save results to local JSON for bypass fallback
        result_payload = {
            "job_id": job_id,
            "brochure_id": job_id,
            "brochure_name": brochure_filename,
            "status": "completed",
            "results": results_with_scoring,
            "created_at": datetime.utcnow().isoformat()
        }
        with open(f"test_results/{job_id}_results.json", "w") as f:
            json.dump(result_payload, f)
            
        logger.info(f"[JOB SUCCESS] {job_id}")
        status = "completed"

    except Exception as e:
        logger.exception(f"[JOB FAILED] {job_id}")
        status = "failed"
        try:
            validation_collection_v2.update_one(
                {"brochure_id": job_id},
                {"$set": {"status": "failed", "error_message": str(e), "failed_at": datetime.utcnow()}}
            )
        except Exception as mongo_err:
            logger.error(f"Failed to update MongoDB failure status for {job_id}: {mongo_err}")
    finally:
        with status_lock:
            if job_id in jobs_status:
                jobs_status[job_id]["status"] = status
        await _cleanup()
        logger.info(f"[JOB FINALIZED] {job_id} ({status})")

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
    job_id = str(uuid4())
    logger.info(f"[PIPELINE START] Job ID: {job_id}, User: {current_user.get('email')}")
    
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
        logger.info(f"[OK] Initial job record created in MongoDB for {job_id}")
    except Exception as e:
        logger.error(f"Failed to create initial MongoDB record for {job_id}: {str(e)}")
        # If DB fails, we still continue with in-memory status for resilience
    
    # Clear logs from previous runs to ensure clean state
    with logs_lock:
        recent_logs.clear()
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
    # ... (Moved above to catch start)

    # Add to in-memory status tracker
    with status_lock:
        jobs_status[job_id] = {
            "status": "queued",
            "filename": brochure_pdf.filename,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

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
        
        logger.info(f"[OK] Background task for {job_id} added successfully.")
        return {
            "status": "success",
            "message": "Validation job started in background",
            "job_id": job_id,
            "filename": brochure_pdf.filename
        }
    except HTTPException:
        # If setup fails, delete temp dir and mark job as failed
        shutil.rmtree(job_tmp_dir, ignore_errors=True)
        try:
            validation_collection_v2.update_one(
                {"brochure_id": job_id},
                {"$set": {"status": "failed", "error_message": "HTTP Exception during setup", "failed_at": datetime.utcnow()}}
            )
        except Exception:
            pass
        raise
    except Exception as e:
        # If setup fails, delete temp dir and mark job as failed
        error_trace = traceback.format_exc()
        logger.error(f"PIPELINE SETUP FAILED for {job_id}: {str(e)}\n{error_trace}")
        shutil.rmtree(job_tmp_dir, ignore_errors=True)
        try:
            validation_collection_v2.update_one(
                {"brochure_id": job_id},
                {"$set": {"status": "failed", "error_message": str(e), "failed_at": datetime.utcnow()}}
            )
        except Exception:
            pass
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
# OTP AUTHENTICATION
# ============================================================================
from otp_service import generate_otp, store_otp, send_otp_email, check_resend_cooldown, verify_otp_hash

@app.post("/auth/send-otp")
async def send_otp(request: Request, payload: dict, db=Depends(get_db)):
    """Send OTP to email"""
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
    
    # Store in storage (Mock Redis)
    store_otp(email, otp)
    
    # Send Email
    success = send_otp_email(email, otp)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send email. Check SendGrid config.")
    
    # Audit trail
    db.execute(text("""
        INSERT INTO user_otp_audit (email, action, ip_address)
        VALUES (:email, 'SENT', :ip)
    """), {"email": email, "ip": request.client.host})
    db.commit()
    
    return {"status": "success", "message": "OTP sent to your email"}

@app.post("/auth/verify-otp")
async def verify_otp(request: Request, payload: dict, db=Depends(get_db)):
    """Verify OTP and mark user as verified"""
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
    
    # Mark user verified
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
        