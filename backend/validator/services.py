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

class PipelineService:
    @staticmethod
    def create_workspace() -> str:
        """Create a unique temporary directory for a pipeline job."""
        workspace = tempfile.mkdtemp(prefix=f"mlr_job_")
        os.makedirs(os.path.join(workspace, "uploads"), exist_ok=True)
        os.makedirs(os.path.join(workspace, "output"), exist_ok=True)
        return workspace

    @staticmethod
    def cleanup_workspace(workspace_path: str):
        """Safely remove a temporary workspace."""
        if workspace_path and os.path.exists(workspace_path):
            try:
                shutil.rmtree(workspace_path)
                logger.info(f"Cleaned up workspace: {workspace_path}")
            except Exception as e:
                logger.error(f"Failed to cleanup workspace {workspace_path}: {e}")

    @staticmethod
    def save_upload(file_obj, workspace_path: str, subfolder: str = "uploads") -> str:
        """Save a Django UploadedFile to the workspace."""
        target_dir = os.path.join(workspace_path, subfolder)
        file_path = os.path.join(target_dir, file_obj.name)
        
        with open(file_path, 'wb+') as destination:
            for chunk in file_obj.chunks():
                destination.write(chunk)
        
        return file_path

    @classmethod
    def run_validation(
        cls, 
        brochure_path: str, 
        reference_paths: List[str], 
        validation_type: str = "research"
    ) -> Dict[str, Any]:
        """
        Orchestrate the full validation pipeline.
        This is the core logic moved out of views/app.py.
        """
        try:
            # 1. Extraction phase
            logger.info(f"Starting extraction for {brochure_path}")
            
            # Read brochure bytes for fitz
            with open(brochure_path, "rb") as f:
                brochure_bytes = f.read()
            
            if validation_type == "drug":
                # Drug pipeline
                extraction_result = extract_drug_superscript_table_data(brochure_bytes)
            else:
                # Research pipeline
                extraction_result = extract_footnotes(brochure_bytes)
            
            # 2. Preparation phase
            # Create pdf_files_dict for conversion
            pdf_files_dict = {}
            for path in reference_paths:
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

            # 3. Validation phase
            validator = StatementValidator()
            results = validator.validate_dataframe(validation_df)
            
            # 4. Format results
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
                "brochure_name": os.path.basename(brochure_path)
            }
            
        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}", exc_info=True)
            raise

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
