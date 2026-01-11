# ============================================================================
# CORRECTED validation_api.py - TWO SEPARATE PIPELINES
# ============================================================================

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Optional
from dataclasses import asdict
import json
import tempfile
import os
from pathlib import Path
import logging

from Superscript import extract_drug_superscript_table_data, extract_footnotes
from conversion import (
    build_validation_rows_special_case, 
    build_validation_rows_image1,
    build_validation_rows_image2,
    build_validation_dataframe
)
from Gemini_version import StatementValidator, ValidationResult

# Get logger
logger = logging.getLogger(__name__)

# Create routers for both pipelines
drug_router = APIRouter(prefix="/api/drugs", tags=["drugs"])
research_router = APIRouter(prefix="/api/research", tags=["research"])

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

# DRUG MODELS
class DrugExtractResponse(BaseModel):
    """Response model for drug extraction"""
    success: bool
    total_records: int
    records: List[Dict]
    message: str


class DrugConvertRequest(BaseModel):
    """Request model for drug conversion"""
    records: List[Dict]
    references: Dict[str, str] = {}


class DrugConvertResponse(BaseModel):
    """Response model for drug conversion"""
    success: bool
    total_rows: int
    validation_rows: List[Dict]
    message: str


class ValidationResponseItem(BaseModel):
    """Single validation result"""
    matched_paper: str
    validation_result: str
    matched_evidence: str
    page_location: str
    confidence_score: float
    matching_method: str


class DrugValidateResponse(BaseModel):
    """Response model for drug validation"""
    success: bool
    statement: str
    total_results: int
    results: List[ValidationResponseItem]
    summary: Dict[str, int]
    message: str


# ============================================================================
# DRUG PIPELINE ENDPOINTS
# ============================================================================

@drug_router.post("/extract", response_model=DrugExtractResponse)
async def extract_drug_pdf(file: UploadFile = File(...)):
    """
    Extract drug compatibility table data from PDF
    
    Uses: extract_drug_superscript_table_data()
    Returns: List of drug rows with superscript numbers and column data
    """
    temp_path = None
    try:
        logger.info(f"[DRUG EXTRACT] Processing: {file.filename}")
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            contents = await file.read()
            tmp.write(contents)
            temp_path = tmp.name
        
        # Extract using drug-specific function
        records = extract_drug_superscript_table_data(temp_path)
        
        if not records:
            logger.warning("[DRUG EXTRACT] No records extracted")
            return DrugExtractResponse(
                success=False,
                total_records=0,
                records=[],
                message="No drug table records extracted from PDF"
            )
        
        logger.info(f"[DRUG EXTRACT] ✅ Extracted {len(records)} drug records")
        return DrugExtractResponse(
            success=True,
            total_records=len(records),
            records=records,
            message=f"✅ Successfully extracted {len(records)} drug records"
        )
        
    except Exception as e:
        logger.error(f"[DRUG EXTRACT] ❌ Error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Drug extraction failed: {str(e)}")
    
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@drug_router.post("/convert", response_model=DrugConvertResponse)
async def convert_drug_records(request: DrugConvertRequest):
    """
    Convert drug extraction records to validation format (AUTO-DETECT)
    
    Uses: build_validation_rows_special_case() which auto-detects IMAGE 1 vs IMAGE 2
    Returns: Formatted statements ready for drug validation
    """
    try:
        logger.info(f"[DRUG CONVERT] Processing {len(request.records)} records")
        
        if not request.records:
            raise ValueError("No records provided")
        
        # Convert using auto-detection function
        validation_rows = build_validation_rows_special_case(
            request.records,
            request.references
        )
        
        if not validation_rows:
            logger.warning("[DRUG CONVERT] No rows generated")
            return DrugConvertResponse(
                success=False,
                total_rows=0,
                validation_rows=[],
                message="No rows generated after conversion"
            )
        
        logger.info(f"[DRUG CONVERT] ✅ Generated {len(validation_rows)} validation rows")
        return DrugConvertResponse(
            success=True,
            total_rows=len(validation_rows),
            validation_rows=validation_rows,
            message=f"✅ Successfully converted {len(validation_rows)} rows"
        )
        
    except Exception as e:
        logger.error(f"[DRUG CONVERT] ❌ Error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Drug conversion failed: {str(e)}")


@drug_router.post("/convert/image1", response_model=DrugConvertResponse)
async def convert_drug_records_image1(request: DrugConvertRequest):
    """
    Convert IMAGE 1 drug extraction records (pH compatibility tables)
    
    Uses: build_validation_rows_image1()
    Format: row_name. pH_value. column1. column2. column3.
    Returns: Formatted statements for pH compatibility validation
    """
    try:
        logger.info(f"[DRUG CONVERT IMAGE1] Processing {len(request.records)} records")
        
        if not request.records:
            raise ValueError("No records provided")
        
        # Convert using IMAGE 1 specific function
        validation_rows = build_validation_rows_image1(
            request.records,
            request.references
        )
        
        if not validation_rows:
            logger.warning("[DRUG CONVERT IMAGE1] No rows generated")
            return DrugConvertResponse(
                success=False,
                total_rows=0,
                validation_rows=[],
                message="No rows generated after IMAGE 1 conversion"
            )
        
        logger.info(f"[DRUG CONVERT IMAGE1] ✅ Generated {len(validation_rows)} validation rows")
        return DrugConvertResponse(
            success=True,
            total_rows=len(validation_rows),
            validation_rows=validation_rows,
            message=f"✅ Successfully converted {len(validation_rows)} IMAGE 1 rows"
        )
        
    except Exception as e:
        logger.error(f"[DRUG CONVERT IMAGE1] ❌ Error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"IMAGE 1 conversion failed: {str(e)}")


@drug_router.post("/convert/image2", response_model=DrugConvertResponse)
async def convert_drug_records_image2(request: DrugConvertRequest):
    """
    Convert IMAGE 2 drug extraction records (statement-based tables)
    
    Uses: build_validation_rows_image2()
    Format: row_name. statement. column_name.
    Returns: Formatted statements for statement-based validation
    """
    try:
        logger.info(f"[DRUG CONVERT IMAGE2] Processing {len(request.records)} records")
        
        if not request.records:
            raise ValueError("No records provided")
        
        # Convert using IMAGE 2 specific function
        validation_rows = build_validation_rows_image2(
            request.records,
            request.references
        )
        
        if not validation_rows:
            logger.warning("[DRUG CONVERT IMAGE2] No rows generated")
            return DrugConvertResponse(
                success=False,
                total_rows=0,
                validation_rows=[],
                message="No rows generated after IMAGE 2 conversion"
            )
        
        logger.info(f"[DRUG CONVERT IMAGE2] ✅ Generated {len(validation_rows)} validation rows")
        return DrugConvertResponse(
            success=True,
            total_rows=len(validation_rows),
            validation_rows=validation_rows,
            message=f"✅ Successfully converted {len(validation_rows)} IMAGE 2 rows"
        )
        
    except Exception as e:
        logger.error(f"[DRUG CONVERT IMAGE2] ❌ Error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"IMAGE 2 conversion failed: {str(e)}")


@drug_router.post("/validate", response_model=DrugValidateResponse)
async def validate_drug_statement(
    files: List[UploadFile] = File(...),
    statement: str = Query(..., description="Drug statement to validate"),
    reference_no: str = Query(..., description="Reference number(s)"),
    reference_text: str = Query(default="", description="Reference text"),
    page_no: Optional[str] = Query(None, description="Page number")
):
    """
    Validate drug statement against reference PDFs
    
    Uses: validate_statement_with_reference() (pharmaceutical mode)
    Returns: Validation results showing support/contradiction/not found
    """
    temp_paths = []
    try:
        logger.info(f"[DRUG VALIDATE] Validating: {statement[:50]}... against {len(files)} PDFs")
        
        if not files or len(files) == 0:
            raise ValueError("No reference PDFs provided")
        if not statement:
            raise ValueError("No statement provided")
        if not reference_no:
            raise ValueError("No reference number provided")
        
        # Save all uploaded files
        pdf_files_dict = {}
        for file in files:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                contents = await file.read()
                tmp.write(contents)
                temp_path = tmp.name
                temp_paths.append(temp_path)
                
                pdf_files_dict[file.filename] = {
                    "content": contents,
                    "path": temp_path
                }
        
        # Initialize validator
        validator = StatementValidator()
        
        # Validate using PHARMACEUTICAL mode (for drug statements)
        validation_results = validator.validate_statement_against_all_papers(
            statement=statement,
            reference_no=reference_no,
            reference=reference_text or "",
            pdf_files_dict=pdf_files_dict,
            page_no=page_no,
            validation_type="pharmaceutical"  # ✅ CORRECT - Drug validation
        )
        
        # Convert to response format
        results = [
            ValidationResponseItem(
                matched_paper=result.matched_paper,
                validation_result=result.validation_result,
                matched_evidence=result.matched_evidence,
                page_location=result.page_location,
                confidence_score=result.confidence_score,
                matching_method=result.matching_method
            )
            for result in validation_results
        ]
        
        # Calculate summary
        summary = {
            "total": len(results),
            "supported": sum(1 for r in results if r.validation_result == "Supported"),
            "contradicted": sum(1 for r in results if r.validation_result == "Contradicted"),
            "not_found": sum(1 for r in results if r.validation_result == "Not Found"),
            "errors": sum(1 for r in results if r.validation_result == "Error")
        }
        
        logger.info(f"[DRUG VALIDATE] ✅ Results: {summary['supported']} supported, {summary['contradicted']} contradicted")
        
        return DrugValidateResponse(
            success=True,
            statement=statement,
            total_results=len(results),
            results=results,
            summary=summary,
            message=f"✅ Validated against {len(files)} PDFs"
        )
        
    except Exception as e:
        logger.error(f"[DRUG VALIDATE] ❌ Error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Drug validation failed: {str(e)}")
    
    finally:
        for temp_path in temp_paths:
            if os.path.exists(temp_path):
                os.remove(temp_path)


@drug_router.post("/pipeline")
async def drug_pipeline(
    pdf_file: UploadFile = File(...),
    reference_files: List[UploadFile] = File(...)
):
    """
    Complete drug compatibility validation pipeline
    
    Step 1: Extract table data (extract_drug_superscript_table_data)
    Step 2: Convert to statements (build_validation_rows_special_case)
    Step 3: Validate statements (pharmaceutical mode)
    
    Returns: Full report with extraction, conversion, and validation results
    """
    temp_paths = []
    try:
        logger.info(f"[DRUG PIPELINE] Starting with {pdf_file.filename} + {len(reference_files)} references")
        
        # Step 1: Extract
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            contents = await pdf_file.read()
            tmp.write(contents)
            extract_path = tmp.name
            temp_paths.append(extract_path)
        
        logger.info("[DRUG PIPELINE] Step 1: Extracting...")
        extracted_records = extract_drug_superscript_table_data(extract_path)
        
        if not extracted_records:
            raise ValueError("No drug table records extracted from PDF")
        
        logger.info(f"[DRUG PIPELINE] ✅ Extracted {len(extracted_records)} records")
        
        # Step 2: Convert
        logger.info("[DRUG PIPELINE] Step 2: Converting...")
        validation_rows = build_validation_rows_special_case(extracted_records, {})
        
        if not validation_rows:
            raise ValueError("No validation rows generated")
        
        logger.info(f"[DRUG PIPELINE] ✅ Generated {len(validation_rows)} validation rows")
        
        # Step 3: Validate
        logger.info("[DRUG PIPELINE] Step 3: Validating...")
        pdf_files_dict = {}
        for file in reference_files:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                contents = await file.read()
                tmp.write(contents)
                temp_path = tmp.name
                temp_paths.append(temp_path)
                pdf_files_dict[file.filename] = {
                    "content": contents,
                    "path": temp_path
                }
        
        validator = StatementValidator()
        all_validation_results = []
        
        for idx, row in enumerate(validation_rows, 1):
            logger.info(f"[DRUG PIPELINE] Validating row {idx}/{len(validation_rows)}")
            
            results = validator.validate_statement_against_all_papers(
                statement=row["statement"],
                reference_no=row["reference_no"],
                reference=row["reference"],
                pdf_files_dict=pdf_files_dict,
                validation_type="pharmaceutical"  # ✅ CORRECT - Drug validation
            )
            all_validation_results.extend(results)
        
        logger.info(f"[DRUG PIPELINE] ✅ Validated {len(all_validation_results)} results")
        
        return JSONResponse({
            "success": True,
            "pipeline_type": "DRUG",
            "pipeline_status": "complete",
            "extraction": {
                "total_records": len(extracted_records),
                "records": extracted_records
            },
            "conversion": {
                "total_rows": len(validation_rows),
                "rows": validation_rows
            },
            "validation": {
                "total_results": len(all_validation_results),
                "results": [asdict(r) if hasattr(r, '__dataclass_fields__') else r.__dict__ for r in all_validation_results]
            },
            "message": "✅ Drug pipeline completed successfully"
        })
        
    except Exception as e:
        logger.error(f"[DRUG PIPELINE] ❌ Failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Drug pipeline failed: {str(e)}")
    
    finally:
        for temp_path in temp_paths:
            if os.path.exists(temp_path):
                os.remove(temp_path)


# ============================================================================
# RESEARCH PIPELINE ENDPOINTS
# ============================================================================

@research_router.post("/extract")
async def extract_research_pdf(file: UploadFile = File(...)):
    """
    Extract citations from research PDF
    
    Uses: extract_footnotes()
    Returns: List of citations with superscript numbers
    """
    temp_path = None
    try:
        logger.info(f"[RESEARCH EXTRACT] Processing: {file.filename}")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            contents = await file.read()
            tmp.write(contents)
            temp_path = tmp.name
        
        # Extract using research-specific function
        extraction_result = extract_footnotes(temp_path)
        
        if not extraction_result.in_text:
            logger.warning("[RESEARCH EXTRACT] No citations extracted")
            return JSONResponse({
                "success": False,
                "total_records": 0,
                "records": [],
                "message": "No citations extracted from PDF"
            })
        
        logger.info(f"[RESEARCH EXTRACT] ✅ Extracted {len(extraction_result.in_text)} citations")
        
        return JSONResponse({
            "success": True,
            "total_records": len(extraction_result.in_text),
            "records": [
                {
                    "page_number": c.page_number,
                    "superscript_number": c.superscript_number,
                    "heading": c.heading,
                    "statement": c.statement
                }
                for c in extraction_result.in_text
            ],
            "references": extraction_result.references,
            "message": f"✅ Successfully extracted {len(extraction_result.in_text)} citations"
        })
        
    except Exception as e:
        logger.error(f"[RESEARCH EXTRACT] ❌ Error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Research extraction failed: {str(e)}")
    
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@research_router.post("/validate")
async def validate_research_statement(
    files: List[UploadFile] = File(...),
    statement: str = Query(..., description="Research statement to validate"),
    reference_no: str = Query(..., description="Reference number(s)"),
    reference_text: str = Query(default="", description="Reference text"),
    page_no: Optional[str] = Query(None, description="Page number")
):
    """
    Validate research statement against reference papers
    
    Uses: validate_with_full_paper() (research mode)
    Returns: Validation results with paper analysis
    """
    temp_paths = []
    try:
        logger.info(f"[RESEARCH VALIDATE] Validating: {statement[:50]}... against {len(files)} papers")
        
        if not files or len(files) == 0:
            raise ValueError("No reference PDFs provided")
        if not statement:
            raise ValueError("No statement provided")
        if not reference_no:
            raise ValueError("No reference number provided")
        
        # Save all uploaded files
        pdf_files_dict = {}
        for file in files:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                contents = await file.read()
                tmp.write(contents)
                temp_path = tmp.name
                temp_paths.append(temp_path)
                
                pdf_files_dict[file.filename] = {
                    "content": contents,
                    "path": temp_path
                }
        
        validator = StatementValidator()
        
        # Validate using RESEARCH mode
        validation_results = validator.validate_statement_against_all_papers(
            statement=statement,
            reference_no=reference_no,
            reference=reference_text or "",
            pdf_files_dict=pdf_files_dict,
            page_no=page_no,
            validation_type="research"  # ✅ CORRECT - Research validation
        )
        
        # Convert to response format
        results = [
            ValidationResponseItem(
                matched_paper=result.matched_paper,
                validation_result=result.validation_result,
                matched_evidence=result.matched_evidence,
                page_location=result.page_location,
                confidence_score=result.confidence_score,
                matching_method=result.matching_method
            )
            for result in validation_results
        ]
        
        # Calculate summary
        summary = {
            "total": len(results),
            "supported": sum(1 for r in results if r.validation_result == "Supported"),
            "contradicted": sum(1 for r in results if r.validation_result == "Contradicted"),
            "not_found": sum(1 for r in results if r.validation_result == "Not Found"),
            "errors": sum(1 for r in results if r.validation_result == "Error")
        }
        
        logger.info(f"[RESEARCH VALIDATE] ✅ Results: {summary}")
        
        return JSONResponse({
            "success": True,
            "statement": statement,
            "total_results": len(results),
            "results": [
                {
                    "matched_paper": r.matched_paper,
                    "validation_result": r.validation_result,
                    "matched_evidence": r.matched_evidence,
                    "page_location": r.page_location,
                    "confidence_score": r.confidence_score,
                    "matching_method": r.matching_method
                }
                for r in results
            ],
            "summary": summary,
            "message": f"✅ Validated against {len(files)} research papers"
        })
        
    except Exception as e:
        logger.error(f"[RESEARCH VALIDATE] ❌ Error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Research validation failed: {str(e)}")
    
    finally:
        for temp_path in temp_paths:
            if os.path.exists(temp_path):
                os.remove(temp_path)


# ============================================================================
# HEALTH CHECKS
# ============================================================================

@drug_router.get("/health")
async def drug_health():
    """Drug pipeline health check"""
    return {
        "status": "🟢 Drug Pipeline is running",
        "pipeline_type": "DRUG",
        "endpoints": {
            "extract": "POST /api/drugs/extract",
            "convert": "POST /api/drugs/convert",
            "validate": "POST /api/drugs/validate",
            "pipeline": "POST /api/drugs/pipeline"
        }
    }


@research_router.get("/health")
async def research_health():
    """Research pipeline health check"""
    return {
        "status": "🟢 Research Pipeline is running",
        "pipeline_type": "RESEARCH",
        "endpoints": {
            "extract": "POST /api/research/extract",
            "validate": "POST /api/research/validate"
        }
    }
