import logging
import os
from celery import shared_task
from django.utils import timezone
from .models import ValidationJob
from .services import PipelineService

logger = logging.getLogger(__name__)

@shared_task(name="validator.tasks.run_validation_task")
def run_validation_task(job_id, brochure_path, reference_paths, workspace_path, validation_type):
    """
    Celery task to run the validation pipeline asynchronously.
    """
    try:
        # 1. Update status to processing
        job = ValidationJob.objects.get(id=job_id)
        job.status = 'processing'
        job.save()
        
        logger.info(f"Starting pipeline task for Job {job_id}")
        
        # 2. Run the pipeline service
        result = PipelineService.run_validation(
            brochure_path=brochure_path,
            reference_paths=reference_paths,
            validation_type=validation_type
        )
        
        # 3. Save results and update status
        job.status = 'completed'
        job.result_json = result
        job.completed_at = timezone.now()
        job.save()
        
        logger.info(f"Successfully completed Job {job_id}")
        
    except Exception as e:
        logger.exception(f"Job {job_id} failed: {str(e)}")
        try:
            job = ValidationJob.objects.get(id=job_id)
            job.status = 'failed'
            job.error_message = str(e)
            job.save()
        except:
            pass
            
    finally:
        # 4. STRICT CLEANUP: Always remove the temporary workspace
        PipelineService.cleanup_workspace(workspace_path)
        logger.info(f"Cleaned up workspace for Job {job_id}")
