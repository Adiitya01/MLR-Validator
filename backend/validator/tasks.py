import logging
import os
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.utils import timezone
from .models import ValidationJob
from .services import PipelineService

logger = logging.getLogger(__name__)


@shared_task(
    name="validator.tasks.run_validation_task",
    bind=True,
    acks_late=True,                # Acknowledge AFTER completion (crash-safe)
    reject_on_worker_lost=True,    # Re-queue if worker dies mid-task
    max_retries=1,                 # Retry once on unexpected failure
    default_retry_delay=30,        # Wait 30s before retry
    time_limit=600,                # Hard kill at 10 minutes
    soft_time_limit=480,           # Soft warning at 8 minutes
    track_started=True,            # Track when task actually starts running
)
def run_validation_task(self, job_id, brochure_path, reference_paths, workspace_path, validation_type):
    """
    Celery task to run the validation pipeline asynchronously.
    
    This runs on a SEPARATE Celery worker process — NOT inside the Django web server.
    Key behaviors:
      - acks_late: If the worker crashes, the task is re-delivered to another worker.
      - soft_time_limit: Raises SoftTimeLimitExceeded at 8 min, giving us a chance
        to save partial results before the hard kill at 10 min.
      - max_retries=1: If the task fails unexpectedly, retry once after 30 seconds.
    """
    try:
        # 1. Update status to processing
        job = ValidationJob.objects.get(id=job_id)
        job.status = 'processing'
        job.save()
        
        logger.info(
            f"[Worker: {self.request.hostname}] Starting pipeline task for Job {job_id} "
            f"(type={validation_type}, attempt={self.request.retries + 1})"
        )
        
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
        
        logger.info(f"Successfully completed Job {job_id} on worker {self.request.hostname}")
    
    except SoftTimeLimitExceeded:
        # Task is about to be hard-killed. Save what we can.
        logger.error(f"Job {job_id} hit SOFT TIME LIMIT (8 min). Saving partial state...")
        try:
            job = ValidationJob.objects.get(id=job_id)
            job.status = 'failed'
            job.error_message = (
                "Validation timed out after 8 minutes. "
                "The document may be too large or the AI service is slow. "
                "Try again with fewer reference documents."
            )
            job.completed_at = timezone.now()
            job.save()
        except Exception:
            pass
    
    except Exception as e:
        logger.exception(f"Job {job_id} failed: {str(e)}")
        
        # Retry once for transient errors (API timeouts, network blips)
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying Job {job_id} in {self.default_retry_delay}s...")
            try:
                job = ValidationJob.objects.get(id=job_id)
                job.status = 'uploaded'  # Reset to uploaded so retry picks it up clean
                job.error_message = f"Retrying after error: {str(e)}"
                job.save()
            except Exception:
                pass
            raise self.retry(exc=e)
        
        # Final failure — no more retries
        try:
            job = ValidationJob.objects.get(id=job_id)
            job.status = 'failed'
            job.error_message = str(e)
            job.completed_at = timezone.now()
            job.save()
        except Exception:
            pass
            
    finally:
        # 4. STRICT CLEANUP: Always remove the temporary workspace
        PipelineService.cleanup_workspace(workspace_path)
        logger.info(f"Cleaned up workspace for Job {job_id}")
