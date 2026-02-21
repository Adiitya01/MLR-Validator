import os
import uuid
import shutil
import logging
import tempfile
from typing import List, Dict, Any, Tuple
from django.conf import settings
from django.utils import timezone


from core.Gemini_version import StatementValidator, PDFProcessor
from core.conversion import build_validation_dataframe
from core.Superscript import extract_footnotes, extract_drug_superscript_table_data
from core.Manual_Review import validate_manual_review, validate_manual_review_multi

logger = logging.getLogger(__name__)


def _use_s3():
    """Check if S3 storage is enabled (AWS deployment)."""
    return getattr(settings, 'USE_S3_STORAGE', False)


def _get_s3():
    """Get S3 storage service instance (lazy import to avoid issues in dev)."""
    from .s3_storage import S3StorageService
    return S3StorageService()


class PipelineService:
    """
    Orchestrates file storage and validation pipeline execution.
    
    Storage modes:
      - LOCAL (dev):  Files stored via tempfile.mkdtemp() on local filesystem
      - S3 (AWS):     Files uploaded to S3, Celery workers download them for processing
    
    The mode is controlled by USE_S3_STORAGE in settings.py.
    """

    # =========================================================================
    # FILE STORAGE — S3 or Local depending on environment
    # =========================================================================

    @staticmethod
    def create_workspace() -> str:
        """
        Create a workspace for a pipeline job.
        
        LOCAL mode: Creates a temp directory on disk.
        S3 mode: Returns a unique job prefix (no local directory needed at upload time).
        """
        if _use_s3():
            # For S3 mode, workspace_path is just a unique ID prefix.
            # Files are uploaded directly to S3 — no local workspace needed.
            workspace_id = f"mlr_s3_{uuid.uuid4().hex[:12]}"
            logger.info(f"S3 mode: workspace ID = {workspace_id}")
            return workspace_id
        else:
            # Local mode: create actual temp directory
            workspace = tempfile.mkdtemp(prefix="mlr_job_")
            os.makedirs(os.path.join(workspace, "uploads"), exist_ok=True)
            os.makedirs(os.path.join(workspace, "output"), exist_ok=True)
            return workspace

    @staticmethod
    def cleanup_workspace(workspace_path: str):
        """
        Clean up workspace files after job completes.
        
        LOCAL mode: Removes the temp directory.
        S3 mode: workspace_path is just an ID — S3 cleanup is handled separately
                 by the task via S3StorageService.delete_job_files().
        """
        if _use_s3():
            # S3 cleanup is handled by the task (delete_job_files)
            logger.info(f"S3 mode: local workspace cleanup for {workspace_path}")
            # Still clean up any temp files the Celery worker downloaded
            if workspace_path and os.path.exists(workspace_path):
                try:
                    shutil.rmtree(workspace_path)
                except Exception as e:
                    logger.error(f"Failed to cleanup local temp: {e}")
        else:
            if workspace_path and os.path.exists(workspace_path):
                try:
                    shutil.rmtree(workspace_path)
                    logger.info(f"Cleaned up workspace: {workspace_path}")
                except Exception as e:
                    logger.error(f"Failed to cleanup workspace {workspace_path}: {e}")

    @staticmethod
    def save_upload(file_obj, workspace_path: str, subfolder: str = "uploads") -> str:
        """
        Save a Django UploadedFile.
        
        LOCAL mode: Writes to workspace directory on disk, returns local path.
        S3 mode: Uploads to S3, returns S3 key.
        """
        if _use_s3():
            # In S3 mode, workspace_path is treated as the job_id
            s3 = _get_s3()
            category = "brochure" if subfolder == "uploads" else "references"
            s3_key = s3.upload_django_file(file_obj, job_id=workspace_path, category=category)
            return s3_key
        else:
            # Local mode: write to disk
            target_dir = os.path.join(workspace_path, subfolder)
            os.makedirs(target_dir, exist_ok=True)
            file_path = os.path.join(target_dir, file_obj.name)
            
            with open(file_path, 'wb+') as destination:
                for chunk in file_obj.chunks():
                    destination.write(chunk)
            
            return file_path

    @staticmethod
    def save_upload_to_s3(file_obj, job_id: str, category: str = "brochure") -> str:
        """
        Directly upload a Django file to S3 (AWS-specific convenience method).
        
        Args:
            file_obj: Django UploadedFile
            job_id: UUID of the ValidationJob
            category: 'brochure' or 'references'
        
        Returns:
            S3 object key
        """
        s3 = _get_s3()
        return s3.upload_django_file(file_obj, job_id=job_id, category=category)

    # =========================================================================
    # PIPELINE EXECUTION
    # =========================================================================

    @classmethod
    def run_validation(
        cls, 
        brochure_path: str, 
        reference_paths: List[str], 
        validation_type: str = "research"
    ) -> Dict[str, Any]:
        """
        Orchestrate the full validation pipeline.
        
        In S3 mode, brochure_path and reference_paths are S3 keys.
        The worker downloads them to temp files, runs the pipeline, then cleans up.
        
        In Local mode, they are local file paths (original behavior).
        """
        local_temp_dirs = []  # Track temp dirs for cleanup
        
        try:
            # ---- STEP 0: Resolve file paths (download from S3 if needed) ----
            if _use_s3():
                s3 = _get_s3()
                
                # Download brochure from S3 to local temp
                brochure_local = s3.download_to_temp(brochure_path)
                local_temp_dirs.append(os.path.dirname(brochure_local))
                
                # Download references from S3 to local temp
                local_reference_paths = []
                for ref_key in reference_paths:
                    ref_local = s3.download_to_temp(ref_key)
                    local_temp_dirs.append(os.path.dirname(ref_local))
                    local_reference_paths.append(ref_local)
                
                # Use local paths for the rest of the pipeline
                effective_brochure = brochure_local
                effective_references = local_reference_paths
            else:
                effective_brochure = brochure_path
                effective_references = reference_paths

            # ---- STEP 1: Extraction phase ----
            logger.info(f"Starting extraction for {effective_brochure}")
            
            with open(effective_brochure, "rb") as f:
                brochure_bytes = f.read()
            
            if validation_type == "drug":
                extraction_result = extract_drug_superscript_table_data(brochure_bytes)
            else:
                extraction_result = extract_footnotes(brochure_bytes)
            
            # ---- STEP 2: Preparation phase ----
            pdf_files_dict = {}
            for path in effective_references:
                filename = os.path.basename(path)
                with open(path, "rb") as f:
                    pdf_files_dict[filename] = f.read()
            
            validation_df = build_validation_dataframe(extraction_result, pdf_files_dict)
            
            if validation_df.empty:
                return {
                    "status": "completed",
                    "results": [],
                    "message": "No claims found for validation"
                }

            # ---- STEP 3: Validation phase ----
            validator = StatementValidator()
            results = validator.validate_dataframe(validation_df)
            
            # ---- STEP 4: Format results ----
            formatted_results = [
                {
                    "statement": res.statement,
                    "reference_no": res.reference_no,
                    "reference": res.reference,
                    "matched_paper": res.matched_paper,
                    "matched_evidence": res.matched_evidence,
                    "validation_result": res.validation_result,
                    "page_location": res.page_location,
                    "confidence_score": res.confidence_score,
                    "matching_method": res.matching_method,
                    "analysis_summary": res.analysis_summary
                }
                for res in results
            ]
            
            return {
                "status": "completed",
                "results": formatted_results,
                "brochure_name": os.path.basename(effective_brochure)
            }
            
        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}", exc_info=True)
            raise
            
        finally:
            # Clean up any temp files downloaded from S3
            for temp_dir in local_temp_dirs:
                try:
                    if os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp dir {temp_dir}: {e}")


class ManualReviewService:
    @staticmethod
    def run_manual_review(statement: str, pdf_files_data: List[Tuple[str, bytes]], reference_no: str = None) -> Dict[str, Any]:
        """
        Run a single statement validation against provided PDFs.
        """
        from core.Gemini_version import GeminiClient
        
        client = GeminiClient()
        if not client.client:
            raise Exception("Gemini client failed to initialize")
            
        gemini_files = []
        ref_labels = []
        
        try:
            for filename, content in pdf_files_data:
                logger.info(f"Uploading {filename} to Gemini for manual review")
                gemini_file = client.upload_pdf_to_gemini(content, filename)
                gemini_files.append(gemini_file)
                
                if reference_no and len(pdf_files_data) == 1:
                    ref_labels.append(reference_no)
                else:
                    ref_labels.append(filename)
            
            if len(gemini_files) == 1:
                result = validate_manual_review(statement, gemini_files[0], ref_labels[0])
            else:
                result = validate_manual_review_multi(statement, gemini_files, ref_labels)
                
            return result
        except Exception as e:
            logger.error(f"Manual review failed: {e}")
            raise
