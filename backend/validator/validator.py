
import logging
import os
import json
import shutil
import tempfile
import time
from datetime import datetime
from uuid import uuid4
from typing import List, Dict, Any, Optional

# --- Django Imports ---
from django.conf import settings

# --- External Logic Imports ---
# Assuming these are in the root directory and discoverable path
# You might need to adjust sys.path or move these files
import sys
BASE_DIR_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR_PATH not in sys.path:
    sys.path.append(BASE_DIR_PATH)

try:
    from Superscript import extract_footnotes, extract_drug_superscript_table_data
    from conversion import build_validation_dataframe, build_validation_rows_special_case
    from Gemini_version import StatementValidator
    from mongo_db import validation_collection, validation_collection_v2
    from mongo_schema import StorageOptimizer, ConfidenceScoringOptimizer
except ImportError as e:
    import traceback
    # Fallback/Error logging if imports fail (during setup)
    print(f"CRITICAL: Failed to import pipeline dependencies: {e}") 
    traceback.print_exc()

logger = logging.getLogger(__name__)

class ValidatorPipeline:
    """
    Encapsulates the MLR Validation Logic.
    Handles both 'drug' and 'research' pipelines.
    """

    def __init__(self, job_id, user_id=None, user_email=None):
        self.job_id = job_id
        self.user_id = user_id
        self.user_email = user_email
        self.status_lock = None # Not using threading lock here as this should run in celery
        self.tmpdir = tempfile.mkdtemp()
        
    def cleanup(self):
        try:
            shutil.rmtree(self.tmpdir)
            logger.info(f"[CLEANUP] Deleted temp dir for {self.job_id}")
        except Exception as e:
            logger.warning(f"[CLEANUP FAILED] Could not delete temp dir {self.tmpdir} for {self.job_id}: {e}")

    async def save_uploads_django(self, brochure_file, reference_files):
        """
        Saves uploaded files (Django UploadedFile objects) to tempdir.
        Returns brochure_path, reference_paths, pdf_files_dict
        """
        # Save brochure
        brochure_path = os.path.join(self.tmpdir, "brochure.pdf")
        with open(brochure_path, "wb") as f:
            for chunk in brochure_file.chunks():
                f.write(chunk)
        
        reference_paths = []
        pdf_files_dict = {}

        for ref_file in reference_files:
            ref_path = os.path.join(self.tmpdir, ref_file.name)
            
            # Read content for dictionary
            ref_content = b""
            with open(ref_path, "wb") as f:
                for chunk in ref_file.chunks():
                    ref_content += chunk
                    f.write(chunk)

            reference_paths.append(ref_path)
            
            # Use ORIGINAL filename as key
            pdf_files_dict[ref_file.name] = {
                "temp_path": ref_path,
                "content": ref_content 
            }

        return brochure_path, reference_paths, pdf_files_dict

    def run_validation(self, brochure_path, pdf_files_dict, validation_type, brochure_filename):
        """
        Main execution logic handling the Conditional Pipeline (Drug vs Research)
        """
        status = "processing"
        
        try:
            logger.info(f"[JOB START] Starting {self.job_id} ({validation_type})")
            
            # Update MongoDB to processing
            try:
                 validation_collection_v2.update_one(
                    {"brochure_id": self.job_id},
                    {"$set": {"status": "processing"}}
                )
            except Exception as e:
                logger.error(f"Failed to update MongoDB status: {e}")

            # ==========================
            # STEP 1: EXTRACTION
            # ==========================
            extraction_result = None
            if validation_type == "drug":
                extraction_result = extract_drug_superscript_table_data(brochure_path)
            else:
                # Default to Research logic
                extraction_result = extract_footnotes(brochure_path)

            if not extraction_result:
                 raise RuntimeError("Extraction failed or produced no results")
            
            # Save debug output
            self._save_debug_json("superscript_output.json", extraction_result)

            # ==========================
            # STEP 2: CONVERSION
            # ==========================
            validation_df = None
            
            if validation_type == "drug":
                validation_rows = build_validation_rows_special_case(extraction_result, {})
                import pandas as pd
                validation_df = pd.DataFrame(validation_rows)
                validation_df['pdf_files_dict'] = [pdf_files_dict] * len(validation_df)
            else:
                validation_df = build_validation_dataframe(
                    extraction_result.in_text,
                    extraction_result.references
                )
                if validation_df.empty:
                    raise RuntimeError("Conversion produced empty validation DataFrame")
                # Add PDF content dictionary to each row
                validation_df['pdf_files_dict'] = [pdf_files_dict] * len(validation_df)

            # Save debug output
            try:
                # Convert DF to list of dicts for JSON saving
                 conv_data = validation_df.drop(columns=['pdf_files_dict'], errors='ignore').to_dict(orient='records')
                 self._save_debug_json("conversion_output.json", conv_data)
            except Exception:
                pass

            # ==========================
            # STEP 3: VALIDATION (Gemini)
            # ==========================
            logger.info(f"[VALIDATE] Starting validation pipeline for {len(validation_df)} statements")
            
            validator = StatementValidator()
            if not validator.llm.test_connection():
                 raise RuntimeError("Gemini API connection failed")

            results = validator.validate_dataframe(validation_df)
            
            if not results:
                 raise RuntimeError("No results returned from validation")

            # ==========================
            # STEP 4: SCORING & FINALIZING
            # ==========================
            from dataclasses import asdict
            results_dicts = [asdict(r) for r in results]
            
            # Normalize scores
            results_optimized = [r.copy() for r in results_dicts]
            results_with_scoring = ConfidenceScoringOptimizer.normalize_confidence_scores(results_optimized)
            
            avg_conf = 0
            if results_with_scoring:
                avg_conf = sum(r.get('confidence_score', 0) for r in results_with_scoring) / len(results_with_scoring)

            # ==========================
            # STEP 5: SAVE RESULTS TO DB
            # ==========================
            validation_collection_v2.update_one(
                {"brochure_id": self.job_id},
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
            
            # Save local debug output
            self._save_debug_json("validation_output.json", results_with_scoring)
            
            # Save legacy local fallback
            fallback_path = os.path.join(BASE_DIR_PATH, "test_results", f"{self.job_id}_results.json")
            result_payload = {
                "job_id": self.job_id,
                "brochure_id": self.job_id,
                "brochure_name": brochure_filename,
                "status": "completed",
                "results": results_with_scoring,
                "created_at": datetime.utcnow().isoformat()
            }
            with open(fallback_path, "w") as f:
                json.dump(result_payload, f)

            logger.info(f"[JOB SUCCESS] {self.job_id}")
            return True, results_with_scoring

        except Exception as e:
            logger.exception(f"[JOB FAILED] {self.job_id}")
            try:
                validation_collection_v2.update_one(
                    {"brochure_id": self.job_id},
                    {"$set": {"status": "failed", "error_message": str(e), "failed_at": datetime.utcnow()}}
                )
            except Exception:
                pass
            return False, str(e)
            
        finally:
            self.cleanup()

    def _save_debug_json(self, filename, data):
        output_dir = os.path.join(BASE_DIR_PATH, "output")
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, filename)
        
        try:
             # Handle Pydantic/Dataclass objects
            if hasattr(data, "model_dump"):
                raw_data = data.model_dump()
            elif hasattr(data, "__dict__"):
                raw_data = data.__dict__
            else:
                raw_data = data
                
            with open(path, "w", encoding="utf-8") as f:
                json.dump(raw_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to save debug file {filename}: {e}")
